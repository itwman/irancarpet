"""صف بازنویسی مقاله‌ها: برنامهٔ اولویت، دریافت متن تازه (گیت‌هاب یا پوشهٔ مخزن)، انتشار روزانه و بازگرداندن نسخهٔ قبلی.

مسیر کار:
  ۱. content/rewrites/plan.json ترتیب مقاله‌ها را می‌گوید (بیشترین فرصت در گوگل اول).
  ۲. نویسنده هر روز یک فایل content/rewrites/posts/NNNN.json می‌سازد و در مخزن می‌گذارد.
  ۳. سایت هر ساعت پوشه را از گیت‌هاب می‌خواند (اگر گیت‌هاب در دسترس نبود، با update.sh از همان مخزن روی سرور).
  ۴. متن «آماده» تا پایان مهلت بررسی صبر می‌کند و بعد سر ساعت تعیین‌شده، روزانه به تعداد تنظیم‌شده روی همان نشانی منتشر می‌شود.
"""
import base64
import hashlib
import json
import logging
import os
import re
import urllib.request
from urllib.parse import quote, unquote

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from . import rewrite_rules
from .models import Post, PostRewrite

log = logging.getLogger(__name__)
S = PostRewrite.Status
SHORTCODE_RE = re.compile(r"\[([a-z_]+)[^\]]*\]")


def _settings():
    from seo.models import SeoSettings

    return SeoSettings.load()


def _post(slug):
    slug = unquote((slug or "").strip().strip("/"))
    return Post.objects.filter(slug=slug).first()


# ------------------------------------------------------------------ برنامه
def load_plan(items):
    """[{rank, slug, kind, reason, keyword, merge_into}] ← ردیف‌های صف؛ متن‌های رسیده دست نمی‌خورند.
    ردیف‌های «در صف نوشتن» که دیگر در برنامه نیستند پاک می‌شوند."""
    n, keep = 0, set()
    for it in items:
        post = _post(it.get("slug"))
        if not post:
            continue
        rw, _ = PostRewrite.objects.get_or_create(post=post)
        rw.rank = int(it.get("rank") or rw.rank)
        rw.kind = (it.get("kind") or rw.kind)[:20]
        rw.reason = (it.get("reason") or rw.reason)[:150]
        rw.keyword = (it.get("keyword") or rw.keyword)[:200]
        rw.merge_into = (it.get("merge_into") or rw.merge_into)[:300]
        if rw.merge_into and rw.status == S.QUEUED:
            rw.status, rw.ready_at = S.READY, timezone.now()  # ادغام نوشتن نمی‌خواهد؛ همراه مقالهٔ مقصد انجام می‌شود
        rw.save(update_fields=["rank", "kind", "reason", "keyword", "merge_into", "status", "ready_at"])
        keep.add(rw.pk)
        n += 1
    if keep:
        PostRewrite.objects.filter(status=S.QUEUED, content="").exclude(pk__in=keep).delete()
    return n


def load_gsc_csv(text):
    """خروجی «صفحه‌ها»ی سرچ کنسول (Pages.csv): آمار پیش از انتشار، و برای منتشرشده‌ها آمار بعد از انتشار."""
    import csv
    import io

    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows or len(rows[0]) < 5:
        return 0
    agg = {}
    for r in rows[1:]:
        try:
            url, c, i, p = r[0], int(r[1]), int(r[2]), float(r[4])
        except (ValueError, IndexError):
            continue
        slug = unquote(url.split("#")[0].split("?")[0]).rstrip("/").rsplit("/", 1)[-1]
        a = agg.setdefault(slug, [0, 0, 0.0])
        a[2] = (a[2] * a[1] + p * i) / (a[1] + i) if a[1] + i else p
        a[0] += c
        a[1] += i
    n = 0
    today = timezone.localdate().isoformat()
    for rw in PostRewrite.objects.select_related("post"):
        a = agg.get(rw.post.slug)
        if not a:
            continue
        if rw.status == S.PUBLISHED:
            rw.gsc_after = {"date": today, "clicks": a[0], "impressions": a[1], "position": round(a[2], 1)}
            rw.save(update_fields=["gsc_after"])
        else:
            rw.gsc_clicks, rw.gsc_impressions, rw.gsc_position = a[0], a[1], round(a[2], 1)
            rw.save(update_fields=["gsc_clicks", "gsc_impressions", "gsc_position"])
        n += 1
    return n


# ------------------------------------------------------------------ دریافت متن
def _site_paths():
    from .models import Page

    paths = cache.get("rw:paths")
    if paths is None:
        paths = {f"/{s}/" for s in Post.objects.published().values_list("slug", flat=True)}
        paths |= {p.get_absolute_url() for p in Page.objects.filter(status="publish").select_related("parent__parent")}
        cache.set("rw:paths", paths, 600)
    return paths


def _link_warnings(content):
    out, paths = [], _site_paths()
    for href in re.findall(r'href="([^"]+)"', content or ""):
        h = unquote(href.replace("https://irancarpet.net", "").replace("https://www.irancarpet.net", ""))
        if not (h.startswith("/") and h.count("/") == 2) or h in paths:
            continue
        try:
            from django.urls import Resolver404, resolve

            match = resolve(h)
            if match.func.__module__ != "core.views":  # مسیر ثابت سایت (فرش‌یاب، سبد، …)
                continue
        except Resolver404:
            pass
        out.append(f"پیوند {h} مقاله یا برگهٔ منتشرشده‌ای نیست؛ پیش از انتشار بررسی کنید")
    return out


def import_data(data, sha=""):
    """یک فایل نویسنده ← ردیف صف. خروجی: پیام کوتاه."""
    post = _post(data.get("slug"))
    if not post and data.get("new") and (data.get("title") or "").strip():
        post = Post.objects.create(title=data["title"][:300], slug=unquote(data["slug"]).strip("/")[:255], status="draft",
                                   author_name="ایران کارپت")
    if not post:
        return f"مقاله‌ای با نامک «{data.get('slug')}» نیست"
    rw, _ = PostRewrite.objects.get_or_create(post=post)
    if sha and rw.source_sha == sha:
        return "تکراری"
    if rw.status in (S.PUBLISHED, S.MERGED) and not data.get("revise"):
        return "قبلاً منتشر شده"
    if data.get("action") == "merge":
        into = "/" + unquote(data.get("into") or "").strip("/") + "/"
        if into == "//" or into.strip("/") == post.slug:
            return "مقصد ادغام نامعتبر است"
        rw.merge_into, rw.status, rw.source_sha = into, S.READY, sha
        rw.notes = (data.get("notes") or f"ادغام در {into}")[:2000]
        rw.ready_at = timezone.now()
        rw.save(update_fields=["merge_into", "status", "source_sha", "notes", "ready_at"])
        return "ادغام آماده"
    if data.get("action") == "skip":
        rw.status, rw.notes, rw.source_sha = S.SKIPPED, (data.get("skip_reason") or "")[:2000], sha
        rw.save(update_fields=["status", "notes", "source_sha"])
        return "کنار گذاشته شد"
    errors, warns = rewrite_rules.check(data, None, rw.kind)
    old_codes, new_codes = set(SHORTCODE_RE.findall(post.content or "")), set(SHORTCODE_RE.findall(data.get("content") or ""))
    lost = (old_codes - new_codes) & rewrite_rules.SHORTCODES
    if lost:
        warns.append("بلوک‌های زندهٔ متن قبلی در متن تازه نیست: " + "، ".join(sorted(lost)))
    warns += _link_warnings(data.get("content"))
    rw.title = (data.get("title") or "")[:300]
    rw.seo_title = (data.get("seo_title") or "")[:300]
    rw.seo_description = data.get("seo_description") or ""
    rw.focus_keyword = (data.get("focus_keyword") or "")[:300]
    rw.excerpt = data.get("excerpt") or ""
    rw.content = data.get("content") or ""
    rw.notes = (data.get("notes") or "")[:4000]
    rw.source_sha = sha
    rw.warnings = "\n".join([f"خطا: {e}" for e in errors] + warns)
    now = timezone.now()
    if errors:
        rw.status = S.QUEUED  # تا اصلاح، منتشر نمی‌شود
    else:
        if rw.status != S.APPROVED:
            rw.status = S.READY
        rw.ready_at = now
        rw.publish_after = now + timezone.timedelta(days=_settings().rewrite_review_days)
    rw.save()
    return "دارای خطا؛ منتشر نمی‌شود" if errors else "آماده"


def git_sha(raw):
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def import_dir(path):
    """پوشهٔ content/rewrites روی همین سرور (بعد از update.sh)."""
    done = {}
    plan = os.path.join(path, "plan.json")
    if os.path.exists(plan):
        raw = open(plan, "rb").read()
        if cache.get("rw:plan_sha") != git_sha(raw):
            done["plan"] = load_plan(json.loads(raw))
            cache.set("rw:plan_sha", git_sha(raw), None)
    folder = os.path.join(path, "posts")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.endswith(".json"):
                raw = open(os.path.join(folder, name), "rb").read()
                try:
                    msg = import_data(json.loads(raw), git_sha(raw))
                except ValueError as e:
                    msg = f"JSON خراب: {e}"
                if msg != "تکراری":
                    done[name] = msg
    return done


def _gh(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "irancarpet-site"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def sync_github(force=False):
    """هر ساعت: فایل‌های تازهٔ content/rewrites از گیت‌هاب. خروجی: {فایل: نتیجه}."""
    s = _settings()
    if not s.rewrite_repo or (not force and not cache.add("rw:sync", 1, 3600)):
        return {}
    base = f"https://api.github.com/repos/{s.rewrite_repo}/contents/content/rewrites"
    ref = f"?ref={quote(s.rewrite_branch or 'main')}"
    done, status = {}, ""
    try:
        known = set(PostRewrite.objects.exclude(source_sha="").values_list("source_sha", flat=True))
        for item in _gh(base + ref):
            if item.get("name") == "plan.json" and cache.get("rw:plan_sha") != item.get("sha"):
                raw = base64.b64decode(_gh(item["url"])["content"])
                done["plan"] = load_plan(json.loads(raw))
                cache.set("rw:plan_sha", item["sha"], None)
        for item in _gh(base + "/posts" + ref):
            if not item.get("name", "").endswith(".json") or item.get("sha") in known:
                continue
            raw = base64.b64decode(_gh(item["url"])["content"])
            try:
                done[item["name"]] = import_data(json.loads(raw), item["sha"])
            except ValueError as e:
                done[item["name"]] = f"JSON خراب: {e}"
        status = f"درست؛ {len([k for k in done if k != 'plan'])} فایل تازه"
    except Exception as e:  # noqa: BLE001
        log.warning("rewrite sync: %s", e)
        status = f"خطا: {str(e)[:200]} — متن‌ها با اجرای update.sh هم وارد می‌شوند"
    type(s).objects.filter(pk=s.pk).update(rewrite_last_sync=timezone.now(), rewrite_last_status=status[:300])
    return done


# ------------------------------------------------------------------ انتشار
FIELDS = ("title", "seo_title", "seo_description", "focus_keyword", "excerpt", "content")


@transaction.atomic
def publish(rw):
    post = Post.objects.select_for_update().get(pk=rw.post_id)
    if rw.status == S.PUBLISHED or not rw.content.strip():
        return False
    rw.old = {f: getattr(post, f) for f in FIELDS} | {"modified_at": post.modified_at.isoformat()}
    for f in FIELDS:
        val = getattr(rw, f)
        if val:
            setattr(post, f, val)
    now = timezone.now()
    post.modified_at = now
    if post.status != "publish":  # مقالهٔ تازه
        rw.old["status"] = post.status
        post.status, post.published_at = "publish", now
    post.save()  # IndexNow خودکار
    rw.status, rw.published_at = S.PUBLISHED, now
    rw.save(update_fields=["old", "status", "published_at"])
    cache.delete("rw:paths")
    for m in PostRewrite.objects.filter(merge_into=post.get_absolute_url(), status__in=[S.READY, S.APPROVED]):
        merge(m)
    return True


def merge(rw):
    """صفحهٔ تکراری ← ریدایرکت ۳۰۱ به مقالهٔ اصلی و خارج شدن از انتشار."""
    from seo.models import Redirect

    if rw.status == S.MERGED or not rw.merge_into:
        return False
    post = rw.post
    Redirect.objects.update_or_create(source=post.slug, defaults={"target": rw.merge_into, "status_code": 301, "is_active": True})
    rw.old = {"status": post.status}
    post.status = "draft"
    post.save(update_fields=["status"])
    rw.status, rw.published_at = S.MERGED, timezone.now()
    rw.save(update_fields=["old", "status", "published_at"])
    cache.delete("rw:paths")
    return True


@transaction.atomic
def rollback(rw):
    if rw.status == S.MERGED:
        from seo.models import Redirect

        Redirect.objects.filter(source=rw.post.slug, target=rw.merge_into).delete()
        Post.objects.filter(pk=rw.post_id).update(status=(rw.old or {}).get("status") or "publish")
        rw.status = S.REJECTED
        rw.save(update_fields=["status"])
        return True
    if rw.status != S.PUBLISHED or not rw.old:
        return False
    post = Post.objects.select_for_update().get(pk=rw.post_id)
    if rw.old.get("status"):
        post.status = rw.old["status"]
    for f in FIELDS:
        if f in rw.old:
            setattr(post, f, rw.old[f])
    post.modified_at = timezone.now()
    post.save()
    rw.status = S.REJECTED
    rw.notes = (rw.notes + "\n[نسخهٔ قبلی برگردانده شد]").strip()
    rw.save(update_fields=["status", "notes"])
    return True


def next_up(limit=10):
    now = timezone.now()
    approved = list(PostRewrite.objects.filter(status=S.APPROVED).order_by("rank")[:limit])
    ready = list(PostRewrite.objects.filter(status=S.READY).order_by("publish_after", "rank")[:limit])
    return approved, [r for r in ready if r.publish_after and r.publish_after <= now], ready


def schedule(now=None, horizon_days=400):
    """زمان تقریبی انتشار هر متن آماده/تأییدشده، با همان قاعدهٔ publish_due: {pk: datetime}.
    کار زمان‌بندی هر ۱۰ دقیقه اجرا می‌شود؛ پس زمان واقعی تا چند دقیقه بعد از عدد برآوردی است."""
    s = _settings()
    if not s.rewrite_enabled or s.rewrite_per_day <= 0:
        return {}
    now = now or timezone.now()
    local = timezone.localtime(now)
    rows = list(PostRewrite.objects.filter(status__in=[S.READY, S.APPROVED], merge_into="").order_by("rank")
                .values("pk", "status", "rank", "publish_after"))
    approved = [r for r in rows if r["status"] == S.APPROVED]
    ready = sorted((r for r in rows if r["status"] == S.READY), key=lambda r: r["rank"])
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    used = PostRewrite.objects.filter(status=S.PUBLISHED, published_at__gte=start).count()
    out = {}
    for d in range(horizon_days):
        if not approved and not ready:
            break
        day = start + timezone.timedelta(days=d)
        t = day.replace(hour=s.rewrite_hour)
        if d == 0:
            t = max(t, local)
        end = day + timezone.timedelta(days=1)
        left = s.rewrite_per_day - (used if d == 0 else 0)
        while left > 0 and t < end:
            if approved:
                r = approved.pop(0)
            else:
                due = [r for r in ready if r["publish_after"] is None or r["publish_after"] <= t]
                if not due:
                    later = [r["publish_after"] for r in ready if r["publish_after"] and r["publish_after"] < end]
                    if not later:
                        break
                    t = timezone.localtime(min(later))
                    continue
                r = due[0]
                ready.remove(r)
            out[r["pk"]] = t
            left -= 1
    return out


def publish_due(now=None):
    s = _settings()
    if not s.rewrite_enabled:
        return 0
    now = now or timezone.now()
    local = timezone.localtime(now)
    if local.hour < s.rewrite_hour:
        return 0
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    for m in PostRewrite.objects.filter(status__in=[S.READY, S.APPROVED]).exclude(merge_into=""):
        target = PostRewrite.objects.filter(post__slug=unquote(m.merge_into).strip("/")).first()
        if target is None or target.status == S.PUBLISHED:
            merge(m)  # ادغام جای انتشار روزانه را نمی‌گیرد
    left = s.rewrite_per_day - PostRewrite.objects.filter(status=S.PUBLISHED, published_at__gte=start).count()
    if left <= 0:
        return 0
    approved = list(PostRewrite.objects.filter(status=S.APPROVED, merge_into="").order_by("rank")[:left])
    due = list(PostRewrite.objects.filter(status=S.READY, publish_after__lte=now, merge_into="").order_by("rank")[:left - len(approved)]) \
        if left > len(approved) else []
    n = 0
    for rw in approved + due:
        try:
            n += publish(rw)
        except Exception:  # noqa: BLE001
            log.exception("rewrite publish %s", rw.pk)
    return n


def run():
    done = {}
    try:
        got = sync_github()
        if got:
            done["دریافت بازنویسی"] = len(got)
    except Exception:  # noqa: BLE001
        log.exception("rewrite sync")
    try:
        n = publish_due()
        if n:
            done["انتشار بازنویسی"] = n
    except Exception:  # noqa: BLE001
        log.exception("rewrite publish")
    return done
