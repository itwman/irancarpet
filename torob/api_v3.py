"""Torob Product API v3 (https://github.com/Torob/Torob-Sync/blob/main/product_api_v3.md).

ترب خودش به POST /torob_api/v3/products درخواست می‌دهد و شناسه، قیمت و موجودی دقیق هر فرش را از سایت می‌گیرد؛
دیگر لازم نیست خزنده‌اش قیمت را از صفحه حدس بزند. درخواست‌ها با توکن JWT (EdDSA) امضای ترب بررسی می‌شوند.

- page_unique: شناسهٔ ثابت فرش (همان شناسهٔ ووکامرس قدیم؛ فرش‌های تازه ۱۰۰۰۰۰۰۰۰۰+شناسه) — مثل فید قبلی.
- قیمت: همان قاعدهٔ فید ترب و تنظیمات پنل (کاهش، مالیات، گرد کردن)؛ فرش متری: ارزان‌ترین تختهٔ ممکن.
- فرشی که نباید در ترب باشد (پیش‌نویس، مستثنی، بی‌آلبوم وقتی «فقط آلبومی» روشن است) نمی‌آید.
"""
import json
import logging

from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import feed
from .jwt_ed25519 import InvalidToken, decode, public_from_pem
from .models import TorobSettings

log = logging.getLogger(__name__)
PAGE = 100
SORTS = {"date_added_desc": ("-published_at", "-pk"), "date_updated_desc": ("-modified_at", "-pk"), "product_id_desc": ("-pk",)}
TOROB_PUBLIC_KEY = public_from_pem("""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAt6Mu4T0pBORY11W+QeM35UsmLO3vsf+6yKpFDEImFk0=
-----END PUBLIC KEY-----""")
LAST_KEY = "torob_api_v3_last"


def _bad(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def _authorized(request):
    token = request.headers.get("X-Torob-Token", "")
    if not token:
        return False
    key = "torob_jwt_ok:" + token[-40:]
    if cache.get(key):
        return True
    host = request.get_host()
    bare = host.split(":")[0].removeprefix("www.")
    for aud in dict.fromkeys([host, host.split(":")[0], bare, "www." + bare]):
        try:
            payload = decode(token, TOROB_PUBLIC_KEY, aud)
        except InvalidToken:
            continue
        ttl = int(float(payload.get("exp", 0)) - timezone.now().timestamp())
        if ttl > 0:
            cache.set(key, 1, min(ttl, 3600))
        return True
    return False


def _item(p, s):
    r = feed.format_row(p, s, keep_unavailable=True)
    if not r:
        return None
    avail = r["availability"] == "instock" and r["current_price"] > 0
    out = {
        "page_unique": str(r["page_unique"]), "page_url": r["page_url"][:1500], "title": r["title"][:500],
        "subtitle": (r["subtitle"] or "")[:500], "current_price": int(r["current_price"]) if avail else 0,
        "availability": avail, "category_name": (r["category_name"].split(" > ")[-1] if r["category_name"] else "")[:200],
        "image_links": [u[:1000] for u in r["image_links"]][:10], "short_desc": (r["short_desc"] or "")[:500],
        "spec": {str(k)[:100]: str(v)[:300] for k, v in (r["spec"] or {}).items()},
        "guarantee": (r["guarantee"] or "")[:200],
        "date_added": timezone.localtime(p.published_at).isoformat() if p.published_at else timezone.localtime().isoformat(),
        "date_updated": timezone.localtime(p.modified_at).isoformat() if p.modified_at else None,
    }
    if avail and r["old_price"] and r["old_price"] > r["current_price"]:
        out["old_price"] = int(r["old_price"])
    return out


def _response(items, total, page=None, max_pages=None, next_cursor=None):
    data = {"api_version": "torob_api_v3", "total": total, "max_pages": max_pages, "products": items}
    if page is not None:
        data["current_page"] = page
    if next_cursor is not None or page is None:
        data["next_cursor"] = next_cursor
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})


def _note(kind, n):
    cache.set(LAST_KEY, {"at": timezone.now().isoformat(), "kind": kind, "n": n,
                         "count": (cache.get(LAST_KEY) or {}).get("count", 0) + 1}, 30 * 24 * 3600)


@csrf_exempt
def products(request):
    if request.method != "POST":
        return _bad("method not allowed", 405)
    s = TorobSettings.load()
    if not s.enabled:
        return _bad("disabled", 404)
    if not _authorized(request):
        return _bad("unauthorized", 401)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return _bad("invalid json")
    if not isinstance(body, dict) or not body:
        return _bad("empty request")
    base = feed.base_queryset(s).select_related("album", "image", "primary_category__parent__parent") \
        .prefetch_related("variations__size", "categories")

    if "page_urls" in body or "page_uniques" in body:
        found = []
        if "page_urls" in body:
            urls = body.get("page_urls")
            if not isinstance(urls, list) or not urls:
                return _bad("page_urls must be a non-empty list")
            found = [feed.product_by_url(str(u)) for u in urls[:100]]
        else:
            ids = body.get("page_uniques")
            if not isinstance(ids, list) or not ids:
                return _bad("page_uniques must be a non-empty list")
            found = [feed.product_by_unique(int(str(u).split("_")[0])) for u in ids[:100] if str(u).split("_")[0].isdigit()]
        pks = [p.pk for p in found if p]
        by = {p.pk: p for p in base.filter(pk__in=pks)}
        items = [x for x in (_item(by[pk], s) for pk in dict.fromkeys(pks) if pk in by) if x]
        _note("single", len(items))
        return _response(items, len(items), page=1, max_pages=1)

    sort = body.get("sort")
    if sort not in SORTS:
        return _bad("sort parameter is not provided" if not sort else "invalid sort")
    qs = base.order_by(*SORTS[sort])
    if "cursor" in body or ("page" not in body and sort == "product_id_desc"):
        if "page" in body or "limit" in body or "size" in body:
            return _bad("cursor pagination does not accept page")
        cur = str(body.get("cursor") or "")
        if cur:
            if not cur.isdigit():
                return _bad("invalid cursor")
            qs = qs.filter(pk__lt=int(cur))
        chunk = list(qs[:PAGE + 1])
        nxt = str(chunk[PAGE - 1].pk) if len(chunk) > PAGE else None
        items = [x for x in (_item(p, s) for p in chunk[:PAGE]) if x]
        _note("cursor", len(items))
        return _response(items, None, next_cursor=nxt)

    page = body.get("page")
    if not isinstance(page, int) or page < 1:
        return _bad("page must be a positive integer")
    total = qs.count()
    chunk = list(qs[(page - 1) * PAGE: page * PAGE])
    items = [x for x in (_item(p, s) for p in chunk) if x]
    _note("page", len(items))
    return _response(items, total, page=page, max_pages=max(1, -(-total // PAGE)))


def last_request():
    return cache.get(LAST_KEY)
