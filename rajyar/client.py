"""ارتباط با API رج‌یار و ساخت متن پست هر فرش."""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

from core.templatetags.fa import fa_num, toman

from .models import RajyarPost, RajyarSettings

log = logging.getLogger(__name__)


class RajyarError(Exception):
    pass


def _call(s, method, path, body=None, timeout=20):
    if not s.api_key:
        raise RajyarError("کلید API رج‌یار وارد نشده است.")
    url = s.url.rstrip("/") + "/" + path.lstrip("/")
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {s.api_key}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "irancarpet.net"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}")
            msg = msg.get("error") or msg.get("detail") or msg.get("message") or str(msg)
        except Exception:  # noqa: BLE001
            msg = ""
        raise RajyarError({401: "کلید API پذیرفته نشد.", 403: "این کلید به آن کانال دسترسی ندارد."}.get(e.code, f"خطای {e.code}")
                          + (f" — {msg}" if msg else ""))
    except Exception as e:  # noqa: BLE001
        raise RajyarError(f"اتصال به رج‌یار برقرار نشد ({e.__class__.__name__}).")


def ping(s=None):
    """آزمایش کلید؛ فهرست کانال‌های مجاز در تنظیمات ذخیره می‌شود."""
    s = s or RajyarSettings.load()
    try:
        data = _call(s, "GET", "channels/")
        rows = data.get("channels", data.get("results", data)) if isinstance(data, dict) else data
        chans = [{"id": c.get("id"), "name": c.get("name") or c.get("title", ""),
                  "platform": c.get("platform") or c.get("messenger") or c.get("type", "")} for c in (rows or [])]
        s.channels_cache, s.last_check = chans, f"اتصال برقرار است — {len(chans)} کانال"
        ok = True
    except RajyarError as e:
        s.last_check, ok = str(e)[:300], False
    s.save(update_fields=["channels_cache", "last_check"])
    return ok, s.last_check


# ------------------------------------------------------------------ متن پست
def _spec(p, *keys):
    for t in p.specs.all():
        if any(k in (t.attribute.label or "").replace("‌", " ") for k in keys):
            return t.name
    return ""


def _abs(url):
    return url if url.startswith("http") else settings.SITE_URL + url


def _date_label(dt):
    import jdatetime

    d = jdatetime.date.fromgregorian(date=timezone.localtime(dt).date())
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return fa_num(f"{d.day} {months[d.month - 1]} {d.year}")


def price_lines(p, s, when):
    """قیمت‌ها با تاریخ روز انتشار؛ بر اساس تنظیم «قیمت در پست»."""
    if s.price_mode == "none":
        return []
    date = _date_label(when)
    if s.price_mode == "from":
        return [f"💰 قیمت از {toman(p.min_price)} تومان (قیمت {date})"] if p.min_price else []
    qs = p.variations.filter(is_available=True, final_price__gt=0, size__isnull=False).select_related("size")
    chosen = list(s.price_sizes.values_list("pk", flat=True)) if s.pk else []
    if chosen:
        rows = sorted(qs.filter(size_id__in=chosen), key=lambda v: chosen.index(v.size_id) if v.size_id in chosen else 99)
    else:
        rows = list(qs.order_by("-size__area")[:2])
    out, seen = [], set()
    for v in rows:
        lbl = (v.size.label or "").split("(")[0].strip()
        if lbl and lbl not in seen:
            seen.add(lbl)
            out.append(f"▫️ {fa_num(lbl)}: {toman(v.price)} تومان")
    if not out:
        return []
    return [f"💰 قیمت روز {date}:"] + out


def build_payload(p, s, publish_at=None, force_new=False):
    reeds, picks, pile, color = _spec(p, "شانه"), _spec(p, "تراکم"), _spec(p, "خاب"), _spec(p, "رنگ")
    if len(pile) > 22:  # «100% آکریلیک هیت ست شده با ضمانت» ← «100% آکریلیک»
        pile = " ".join(pile.split()[:2])
    blocks = []
    if s.show_specs:
        specs = [(f"{fa_num(reeds)} شانه" if reeds else ""), (f"تراکم {fa_num(picks)}" if picks else ""),
                 fa_num(pile), (f"زمینهٔ {color}" if color else "")]
        specs = [x for x in specs if x]
        if specs:
            blocks.append(" | ".join(specs))
    prices = price_lines(p, s, publish_at or timezone.now())
    if prices:
        blocks.append("\n".join(prices))
    if s.show_summary:
        from content.render import summary_text

        summary = summary_text(p)
        if summary:
            blocks.append(fa_num(summary[:400]))
    if s.footer:
        blocks.append(s.footer)
    url = f"{settings.SITE_URL}/p/{p.pk}/"  # پیوند کوتاه؛ نشانی فارسی در پیام‌رسان‌ها خیلی بلند و ناخوانا می‌شود
    tags = [t.strip() for t in (s.tags or "").replace("،", ",").split(",") if t.strip()]
    if reeds:
        tags.append(f"فرش {reeds} شانه")
    if color:
        tags.append(f"فرش {color}")
    if p.primary_category_id:
        tags.append(p.primary_category.name)
    body = {
        "title": fa_num(p.title),
        # متن ساده؛ هر بخش با یک خط خالی جدا می‌شود (برچسب HTML در بعضی پیام‌رسان‌ها شکستن خط را از بین می‌برد)
        "content": "\n\n".join(blocks) or fa_num(p.title),
        "url": url,
        "tags": list(dict.fromkeys(tags))[:8],
        "external_id": f"product-{p.pk}",
        "channels": s.channel_ids,
        "language": "fa",
    }
    if s.button_text:
        body["buttons"] = [{"text": s.button_text, "url": url}]
    if p.image_id and p.image.file:
        body["image_url"] = _abs(p.image.url)
    if getattr(p, "video_url", "") and p.video_url.lower().split("?")[0].endswith((".mp4", ".mov", ".webm")):
        body["video_url"] = _abs(p.video_url)
    if publish_at:
        body["publish_at"] = timezone.localtime(publish_at).isoformat(timespec="minutes")
    if force_new:
        body["force_new"] = True
    return body


def send(p, publish_at=None, force_new=False, s=None):
    """یک فرش را به رج‌یار می‌فرستد؛ خروجی: RajyarPost"""
    s = s or RajyarSettings.load()
    if not s.enabled:
        raise RajyarError("اتصال رج‌یار غیرفعال است.")
    if not s.channel_ids:
        raise RajyarError("کانال‌ها در تنظیمات رج‌یار انتخاب نشده‌اند.")
    post = RajyarPost(product=p, publish_at=publish_at)
    try:
        data = _call(s, "POST", "posts/", build_payload(p, s, publish_at, force_new))
        remote = (data or {}).get("post") or {}
        post.remote_id = remote.get("id")
        post.status = RajyarPost.Status.SCHEDULED if publish_at and publish_at > timezone.now() else RajyarPost.Status.SENT
        _apply_status(post, remote)
    except RajyarError as e:
        post.status, post.error = RajyarPost.Status.FAILED, str(e)[:300]
    post.save()
    return post


def _apply_status(post, remote):
    pubs = remote.get("publications") or []
    links = [x.get("url") or x.get("link") for x in pubs if x.get("url") or x.get("link")]
    states = {str(x.get("status", "")).lower() for x in pubs}
    if links:
        post.links = links
    if pubs and states <= {"published", "sent", "done"}:
        post.status = RajyarPost.Status.PUBLISHED
    elif links:
        post.status = RajyarPost.Status.PARTIAL
    elif states & {"failed", "error"}:
        post.status = RajyarPost.Status.FAILED
        post.error = "; ".join(str(x.get("error", "")) for x in pubs if x.get("error"))[:300]
    elif states & {"cancelled", "canceled"}:
        post.status = RajyarPost.Status.CANCELLED


def refresh(limit=40):
    """وضعیت ارسال‌های هنوز منتشرنشده را از رج‌یار می‌خواند (در کارهای دوره‌ای)."""
    s = RajyarSettings.load()
    if not (s.enabled and s.api_key):
        return 0
    n = 0
    for post in RajyarPost.objects.filter(status__in=["sent", "scheduled", "partial"], remote_id__isnull=False)[:limit]:
        try:
            data = _call(s, "GET", f"posts/{post.remote_id}/")
        except RajyarError:
            continue
        _apply_status(post, (data or {}).get("post") or data or {})
        post.checked_at = timezone.now()
        post.save(update_fields=["status", "links", "error", "checked_at"])
        n += 1
    return n
