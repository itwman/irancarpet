"""فید ایمالز — سازگار با افزونهٔ رسمی «Emalls Extraction API» ووکامرس.

ایمالز به POST /wp-json/emalls_ext/v1/products با token، page و limit درخواست می‌دهد و
توکن را از emalls.ir/swservice/wp_plugin.ashx تأیید می‌کند. قیمت‌ها و ردیف‌ها همان فید ترب است.
"""
import json
import logging
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from . import feed
from .models import TorobSettings

log = logging.getLogger(__name__)
VERSION = "1.3.0"
VERIFY = "https://emalls.ir/swservice/wp_plugin.ashx"


def _domain():
    return urllib.parse.urlparse(settings.SITE_URL).netloc.replace("www.", "")


def verify(token):
    if not token:
        return False
    key = "emalls:tok"
    if cache.get(key) == token:
        return True
    body = urllib.parse.urlencode({"token": token, "shop_domain": _domain(), "version": VERSION}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(VERIFY, data=body, method="POST"), timeout=6) as r:
            res = json.loads(r.read().decode() or "{}")
    except Exception as e:  # noqa: BLE001
        log.warning("emalls verify failed: %s", e)
        return False
    ok = bool(res.get("success")) and res.get("message") == "the token is valid"
    if ok:
        cache.set(key, token, 3600)
    return ok


def _row(p, s):
    r = feed.format_row(p, s)
    if not r:
        return None
    spec = dict(r["spec"])
    if p.sku and "شناسه کالا" not in spec:
        spec["شناسه کالا"] = p.sku
    return {
        "title": r["title"], "subtitle": p.english_name or "", "parent_id": 0, "page_unique": r["page_unique"],
        "current_price": r["current_price"], "old_price": r["old_price"] or r["current_price"],
        "availability": r["availability"], "image_links": r["image_links"], "category_name": r["category_name"].split(" > ")[-1],
        "image_link": r["image_link"] or None, "page_url": r["page_url"], "short_desc": r["short_desc"],
        "spec": [spec] if spec else [],
        "date_added": timezone.localtime(p.published_at).isoformat() if p.published_at else None,
        "date_updated": timezone.localtime(p.modified_at).isoformat() if p.modified_at else None,
        "product_type": "simple", "registry": r["registry"], "guarantee": r["guarantee"],
    }


@csrf_exempt
def products(request):
    s = TorobSettings.load()
    params = request.POST if request.method == "POST" else request.GET
    if request.content_type == "application/json":
        try:
            params = json.loads(request.body or b"{}")
        except ValueError:
            params = {}
    if not s.emalls_enabled:
        return JsonResponse({"Error": "disabled"}, status=404)
    token = str(params.get("token") or "")
    if not verify(token):
        return JsonResponse({"Error": "Invalid token", "plugin_version": VERSION}, status=401)
    try:
        limit = max(1, min(int(params.get("limit") or 100), 100))
        page = max(1, int(params.get("page") or 1))
    except (TypeError, ValueError):
        limit, page = 100, 1
    ids = feed.rows(s)
    chunk = ids[(page - 1) * limit: page * limit]
    items = [r for r in (_row(p, s) for p in feed._load(chunk)) if r]
    return JsonResponse({
        "count": len(ids), "max_pages": -(-len(ids) // limit), "products": items,
        "Version": VERSION, "NeedSession": False, "TokenSendByEmalls": token, "SignedBy": "irancarpet.net",
        "metadata": {"plugin_version": VERSION, "platform": "django", "time": int(time.time())},
    }, json_dumps_params={"ensure_ascii": False})
