"""موتور همگام‌سازی محصولات با فرش پلاس.

جریان کار (معادل افزونهٔ ووکامرس):
- scan(): تغییر محصولات (قیمت، موجودی، عنوان، تصویر و...) را با «اثر انگشت» تشخیص می‌دهد و در صف می‌گذارد.
- run(): موارد صف را با رعایت سقف روزانه (۴۲۹ → توقف سراسری)، تلاش مجدد و حذف/پنهان‌سازی پردازش می‌کند.
- در نسخهٔ آزمایشی (STAGING) هیچ درخواستی به فرش پلاس فرستاده نمی‌شود.
"""
import hashlib
import json
import logging
import os
import re
from datetime import timedelta
from html import unescape

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import iri_to_uri
from django.utils.html import strip_tags

from catalog.models import Category, Product, ProductImage

from .client import ApiError, Client
from .models import FarshPlusItem, FarshPlusSettings

log = logging.getLogger(__name__)
MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 1800]
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


class Paused(Exception):
    pass


def inactive_reason(s=None):
    s = s or FarshPlusSettings.load()
    if settings.STAGING and not getattr(settings, "FARSHPLUS_ON_STAGING", False):
        return "در نسخهٔ آزمایشی، ارسال به فرش پلاس خاموش است (فقط روی سایت اصلی کار می‌کند)."
    if not s.enabled:
        return "اتصال فرش پلاس در تنظیمات خاموش است."
    if not s.api_key:
        return "کلید API فرش پلاس وارد نشده است."
    return ""


def client(s=None):
    s = s or FarshPlusSettings.load()
    return Client(s.url, s.api_key)


# ------------------------------------------------------------------ داده‌ها
def plain_text(html, limit=2000):
    t = re.sub(r"\[/?[a-zA-Z_][^\]]*\]", "", html or "")
    t = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>|</div>", "\n", t)
    t = unescape(strip_tags(t))
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if limit and len(t) > limit:
        t = t[:limit - 1].rstrip() + "…"
    return t


def allowed_category_ids(s):
    ids = set(s.categories.values_list("pk", flat=True))
    if not ids:
        return None
    frontier = set(ids)
    while frontier:
        kids = set(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)) - ids
        ids |= kids
        frontier = kids
    return ids


def image_medias(product, limit):
    medias, seen = [], set()
    if product.image_id and product.image:
        medias.append(product.image)
        seen.add(product.image_id)
    for pi in ProductImage.objects.filter(product=product).select_related("media").order_by("order"):
        if pi.media_id not in seen:
            medias.append(pi.media)
            seen.add(pi.media_id)
    medias = [m for m in medias if os.path.splitext(m.file.name or "")[1].lower() in IMAGE_TYPES]
    return medias[:max(0, limit)]


def images_hash(medias):
    return hashlib.md5("|".join(f"{m.pk}:{m.file.name}" for m in medias).encode()).hexdigest()


def max_images(s):
    return max(0, min(max(1, min(5, s.max_images)), int(s.limits.get("max_images") or 5)))


def hashtags(product):
    names = [c.name for c in product.categories.all()] + [t.name for t in product.tags.all()]
    out = []
    for n in names:
        n = unescape(n).replace(",", " ").strip()
        if n and n not in out:
            out.append(n)
    return out


def resolve_in_feed(item, s, mode):
    if item.in_feed is not None:
        return item.in_feed
    if mode == "bulk":
        return False
    return s.default_in_feed


def build_fields(product, item, s, mode, img_hash):
    vs = [v for v in product.variations.all() if v.is_available and (v.sale_price or v.final_price)]
    price = min((v.sale_price or v.final_price for v in vs), default=product.min_price)
    regular = min((v.final_price for v in vs if v.final_price), default=price)
    desc = product.short_description if plain_text(product.short_description) else product.content
    f = {
        "external_id": item.external_id,
        "title": plain_text(product.title, 0),
        "description": plain_text(desc, 2000),
        "url": iri_to_uri(settings.SITE_URL + product.get_absolute_url()),
        "price": str(price) if price else None,
        "regular_price": str(regular) if regular else None,
        "currency": "IRT",
        "stock": product.stock_status if product.stock_status in ("instock", "outofstock", "onbackorder") else "instock",
        "in_feed": "1" if resolve_in_feed(item, s, mode) else "0",
        "images_hash": img_hash,
    }
    if s.hashtags:
        tags = hashtags(product)
        if tags:
            f["hashtags"] = ",".join(tags)
    return f


def fingerprint(fields):
    data = {k: v for k, v in fields.items() if k != "in_feed"}
    return hashlib.md5(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def current_fingerprint(product, item, s, cats=None):
    medias = image_medias(product, max_images(s))
    fields = build_fields(product, item, s, item.mode, images_hash(medias))
    fields["_skip"] = skip_reason(product, item, s, cats)
    return fingerprint(fields)


def skip_reason(product, item, s, cats=None):
    if product.status != "publish":
        return "not_published"
    enabled = item.enabled if item.enabled is not None else s.auto_sync
    if not enabled:
        return "disabled"
    cats = allowed_category_ids(s) if cats is None else cats
    if cats is not None and not ({c.pk for c in product.categories.all()} & cats):
        return "category"
    if s.hide_out_of_stock and product.stock_status == "outofstock":
        return "out_of_stock"
    return ""


def get_item(product):
    item = FarshPlusItem.objects.filter(product=product).first()
    if item is None:
        item = FarshPlusItem(product=product, external_id=FarshPlusItem.external_id_for(product))
    return item


def queue(item, mode="auto", save=True):
    item.queued = True
    item.mode = mode if not (item.queued and item.mode == "manual") else "manual"
    item.attempts = 0
    item.next_try_at = None
    if not item.has_remote and item.status in ("", "ERROR"):
        item.status = "QUEUED"
    if save:
        item.save()


# --------------------------------------------------------------- پردازش
def _read_images(medias, max_bytes):
    files, complete = [], True
    for i, m in enumerate(medias, start=1):
        path = os.path.join(str(settings.MEDIA_ROOT), m.file.name)
        ext = os.path.splitext(path)[1].lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            complete = False
            continue
        if size > max_bytes:
            continue
        with open(path, "rb") as fh:
            files.append({"filename": f"product-{m.pk}-{i}{'.jpg' if ext == '.jpeg' else ext}", "type": IMAGE_TYPES[ext], "data": fh.read()})
    return files, complete


def process(item, s=None, interactive=False):
    """یک محصول را ارسال/به‌روز/حذف می‌کند. خروجی: متن نتیجه برای نمایش."""
    s = s or FarshPlusSettings.load()
    product = Product.objects.select_related("image").prefetch_related("variations", "categories", "tags").get(pk=item.product_id)
    if s.paused and not interactive:
        raise Paused()
    reason = skip_reason(product, item, s)
    try:
        if reason:
            if item.has_remote:
                client(s).delete_product(item.external_id)
                item.status = "HIDDEN" if reason == "out_of_stock" else "REMOVED"
                item.images_hash = ""
                msg = "محصول ناموجود شد و در فرش پلاس پنهان شد." if reason == "out_of_stock" else "محصول از فرش پلاس برداشته شد."
            else:
                if item.status == "QUEUED":
                    item.status = ""
                msg = "ارسال نشد: " + {"not_published": "محصول منتشر نشده است", "disabled": "ارسال این محصول خاموش است",
                                       "category": "دستهٔ محصول در فهرست ارسال نیست", "out_of_stock": "محصول ناموجود است"}[reason]
            item.queued, item.attempts, item.error = False, 0, ""
            item.synced_at = timezone.now()
            item.fingerprint = current_fingerprint(product, item, s)
            item.save()
            return msg
        medias = image_medias(product, max_images(s))
        h = images_hash(medias)
        files, complete = [], True
        if h != item.images_hash and medias:
            files, complete = _read_images(medias, int(float(s.limits.get("max_image_mb") or 8) * 1024 * 1024))
        if not item.post_id and not files:
            raise ApiError("برای ارسال محصول تازه دست‌کم یک تصویر لازم است.", 400)
        fields = build_fields(product, item, s, item.mode, h)
        res = client(s).upsert_product(fields, files)
        if not res.get("id"):
            raise ApiError("پاسخ نامعتبر از فرش پلاس دریافت شد.", 200, True)
    except ApiError as e:
        _failure(item, s, e)
        raise
    item.post_id = int(res["id"])
    item.post_url = (res.get("url") or item.post_url or "")[:500]
    item.status = re.sub(r"[^A-Z_]", "", str(res.get("status") or "PUBLISHED").upper())[:32]
    item.synced_at = timezone.now()
    item.error = ""
    if files and complete:
        item.images_hash = h
    item.fingerprint = current_fingerprint(product, item, s)
    item.queued, item.attempts, item.next_try_at = False, 0, None
    item.save()
    return f"در فرش پلاس {'ایجاد' if res.get('created') else 'به‌روزرسانی'} شد ({len(files)} تصویر، وضعیت: {item.get_status_display()})."


def _failure(item, s, e):
    now = timezone.now()
    if e.status == 429:
        delay = max(3600, e.retry_after or 0)
        s.rate_limited_until = now + timedelta(seconds=delay)
        s.save(update_fields=["rate_limited_until"])
        item.next_try_at = s.rate_limited_until
        item.error = (str(e) + " (تلاش مجدد حدود یک ساعت دیگر)")[:500]
    elif e.retryable and item.attempts < MAX_RETRIES:
        item.next_try_at = now + timedelta(seconds=RETRY_DELAYS[min(item.attempts, len(RETRY_DELAYS) - 1)])
        item.attempts += 1
        item.error = f"{e} (تلاش مجدد {item.attempts} از {MAX_RETRIES})"[:500]
    else:
        item.error = str(e)[:500]
        item.queued = False
        if not item.has_remote:
            item.status = "ERROR"
    item.synced_at = now
    item.save()


# -------------------------------------------------------------- اسکن و اجرا
def scan(s=None):
    """تغییرات محصولات را پیدا می‌کند و در صف می‌گذارد."""
    s = s or FarshPlusSettings.load()
    baseline = s.last_scan_at or timezone.now()
    cats = allowed_category_ids(s)
    n = 0
    items = {i.product_id: i for i in FarshPlusItem.objects.all()}
    qs = Product.objects.filter(Q(pk__in=[pid for pid, i in items.items() if i.post_id]) |
                                Q(modified_at__gt=baseline, status="publish"))
    qs = qs.select_related("image").prefetch_related("variations", "categories", "tags")
    for p in qs.iterator(chunk_size=200):
        item = items.get(p.pk)
        if item is None:
            if not s.auto_sync:
                continue
            item = get_item(p)
        if item.queued:
            continue
        if not item.post_id:
            # محصولی که هنوز در فرش پلاس نیست فقط وقتی در پنل ویرایش/ساخته شود ارسال می‌شود (مثل افزونه)
            if p.modified_at and p.modified_at > baseline and (item.enabled if item.enabled is not None else s.auto_sync):
                queue(item, "auto")
                n += 1
            continue
        if current_fingerprint(p, item, s, cats) != item.fingerprint:
            queue(item, "auto")
            n += 1
    s.last_scan_at = timezone.now()
    s.save(update_fields=["last_scan_at"])
    return n


def refresh_statuses(s=None):
    s = s or FarshPlusSettings.load()
    items = list(FarshPlusItem.objects.filter(status__in=["PROCESSING", "PENDING_REVIEW"])[:100])
    if items:
        try:
            res = client(s).get_statuses([i.external_id for i in items]).get("results") or {}
        except ApiError as e:
            log.warning("farshplus refresh: %s", e)
            return
        for i in items:
            row = res.get(i.external_id) or {}
            if row.get("status"):
                i.status = re.sub(r"[^A-Z_]", "", str(row["status"]).upper())[:32]
            if row.get("url"):
                i.post_url = row["url"][:500]
            if row.get("id"):
                i.post_id = int(row["id"])
            i.save()
    s.last_refresh_at = timezone.now()
    s.save(update_fields=["last_refresh_at"])


def check_connection(s=None):
    s = s or FarshPlusSettings.load()
    me = client(s).me()
    s.connection = {"page": me.get("page") or {}, "shop": me.get("shop") or {}, "limits": me.get("limits") or {}}
    s.checked_at = timezone.now()
    s.save(update_fields=["connection", "checked_at"])
    return me


def run(limit=40, out=print):
    s = FarshPlusSettings.load()
    why = inactive_reason(s)
    if why:
        out(why)
        return 0
    if not cache.add("farshplus-run", 1, 900):
        out("اجرای قبلی هنوز تمام نشده است.")
        return 0
    done = 0
    try:
        if not s.checked_at or s.checked_at < timezone.now() - timedelta(hours=12):
            try:
                check_connection(s)
            except ApiError as e:
                out(f"بررسی اتصال: {e}")
        queued = scan(s)
        if queued:
            out(f"{queued} محصول برای ارسال/به‌روزرسانی در صف قرار گرفت.")
        if s.paused:
            out(f"سقف روزانه پر است؛ ارسال تا {timezone.localtime(s.rate_limited_until):%H:%M} متوقف است.")
            return 0
        now = timezone.now()
        due = (FarshPlusItem.objects.filter(queued=True).filter(Q(next_try_at__isnull=True) | Q(next_try_at__lte=now))
               .order_by("-mode", "next_try_at", "pk"))  # manual و auto پیش از bulk
        for item in due[:limit]:
            try:
                out(f"#{item.external_id}: {process(item, s)}")
                done += 1
            except Paused:
                out("سقف روزانه پر شد؛ ادامه بعداً.")
                break
            except ApiError as e:
                out(f"#{item.external_id}: خطا — {e}")
                if e.status == 429:
                    break
        if not s.last_refresh_at or s.last_refresh_at < timezone.now() - timedelta(hours=1):
            refresh_statuses(s)
    finally:
        cache.delete("farshplus-run")
    return done


def queue_all_unsent(s=None):
    """ارسال گروهی همهٔ محصولات منتشرشده‌ای که هنوز در فرش پلاس نیستند (بی‌صدا، بدون نمایش در فید)."""
    s = s or FarshPlusSettings.load()
    cats = allowed_category_ids(s)
    items = {i.product_id: i for i in FarshPlusItem.objects.all()}
    n = 0
    for p in Product.objects.filter(status="publish").exclude(stock_status="outofstock" if s.hide_out_of_stock else "-").prefetch_related("categories"):
        item = items.get(p.pk) or get_item(p)
        if item.has_remote or item.queued:
            continue
        if skip_reason(p, item, s, cats):
            continue
        queue(item, "bulk")
        n += 1
    return n
