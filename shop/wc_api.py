"""API سفارش‌ها با همان شکل ووکامرس (wp-json/wc/v3) برای مانیکس پلاس.

چرا شکل ووکامرس: مانیکس پلاس برای سایت‌های وردپرسی هم همین همگام‌ساز را دارد؛ ایران کارپت
هم مثل یک فروشگاه ووکامرس دیده می‌شود و یک کد برای همه کار می‌کند.

امنیت: کلید و رمز را مدیر در «تنظیمات ← مانیکس پلاس» می‌سازد (رمز فقط یک بار نشان داده می‌شود و
فقط هش آن ذخیره می‌شود). احراز هویت مثل ووکامرس: Basic Auth روی HTTPS یا consumer_key/consumer_secret.
فقط سفارش‌های پس از «تاریخ شروع» داده می‌شوند. تنها نوشتن: manix/orders (فاکتور تلفنی مانیکس ← سفارش سایت،
با لینک پرداخت) که پیش‌نویس فرش تازه هم می‌تواند بسازد (shop/manix.py).

پرداخت‌ها: ووکامرس پرداخت جزئی ندارد؛ پرداخت‌های تأییدشده (بیعانه، تسویه، ثبت دستی) در
meta_data با کلید «_manix_payments» می‌آیند تا هر کدام با تاریخ خودش «دریافت» شود.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, time
from datetime import timezone as dt_timezone

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

STATUS = {"pending": "pending", "on_hold": "on-hold", "deposit_paid": "processing", "paid": "processing",
          "processing": "processing", "shipped": "completed", "completed": "completed",
          "cancelled": "cancelled", "refunded": "refunded"}
WC_TO_LOCAL = {}
for _k, _v in STATUS.items():
    WC_TO_LOCAL.setdefault(_v, []).append(_k)
MAX_PER_PAGE = 100


def hash_secret(secret):
    return hashlib.sha256(("manix:" + (secret or "")).encode()).hexdigest()


def new_keys():
    """(کلید، رمز) تازه؛ فقط هش رمز ذخیره می‌شود."""
    from .models import ShopSettings

    key, secret = "ck_" + secrets.token_hex(20), "cs_" + secrets.token_hex(20)
    s = ShopSettings.load()
    s.manix_key, s.manix_secret_hash = key, hash_secret(secret)
    s.save(update_fields=["manix_key", "manix_secret_hash"])
    return key, secret


def _err(code, message, status):
    return JsonResponse({"code": code, "message": message, "data": {"status": status}}, status=status,
                        json_dumps_params={"ensure_ascii": False})


def _creds(request):
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.lower().startswith("basic "):
        try:
            k, _, s = base64.b64decode(auth[6:]).decode().partition(":")
            return k, s
        except Exception:  # noqa: BLE001
            return "", ""
    return request.GET.get("consumer_key", ""), request.GET.get("consumer_secret", "")


def _authorized(request):
    from .models import ShopSettings

    s = ShopSettings.load()
    if not s.manix_enabled or not s.manix_key or not s.manix_secret_hash:
        return None, _err("woocommerce_rest_cannot_view", "اتصال مانیکس پلاس در تنظیمات فروشگاه خاموش است.", 401)
    key, secret = _creds(request)
    if not (hmac.compare_digest(key, s.manix_key) and hmac.compare_digest(hash_secret(secret), s.manix_secret_hash)):
        return None, _err("woocommerce_rest_authentication_error", "کلید یا رمز نادرست است.", 401)
    from stats.track import _ip, _limited

    if _limited("manix:" + _ip(request), 120):
        return None, _err("rest_too_many", "درخواست بیش از حد؛ یک دقیقه بعد دوباره امتحان کنید.", 429)
    if not s.manix_last_access or timezone.now() - s.manix_last_access > timezone.timedelta(minutes=5):
        type(s).objects.filter(pk=s.pk).update(manix_last_access=timezone.now())
    return s, None


def _iso(dt):
    if not dt:
        return None
    return timezone.localtime(dt).replace(tzinfo=None, microsecond=0).isoformat()


def _iso_gmt(dt):
    if not dt:
        return None
    return dt.astimezone(dt_timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()


def _parse_dt(v):
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


def variation_sku(v, product=None):
    """کد کالای هر سایز: کد خود سایز، وگرنه «کد فرش-نامک سایز» (ثابت و یکتا)."""
    if v is not None and v.sku:
        return v.sku
    p = product if product is not None else (v.product if v is not None else None)
    base = (p.sku if p is not None else "") or (f"P{p.pk}" if p is not None else "")
    size = v.size.slug if v is not None and v.size_id else ""
    return f"{base}-{size}" if base and size else base


def item_sku(item):
    if item.variation is not None:
        return variation_sku(item.variation, item.product)
    return variation_sku(None, item.product) if item.product is not None else ""


def item_name(item):
    size = (item.size_label or "").strip()
    return f"{item.title} - {size}" if size and size not in item.title else item.title


def serialize(o):
    from .gateways import GATEWAY_NAMES

    items = []
    for it in o.items.all():
        line = it.unit_price * it.quantity
        items.append({
            "id": it.pk, "name": item_name(it), "product_id": it.product_id or 0, "variation_id": it.variation_id or 0,
            "quantity": it.quantity, "subtotal": str(line), "total": str(line), "price": it.unit_price,
            "sku": item_sku(it), "meta_data": [{"key": "size", "value": it.size_label or ""}],
        })
    pays = [{"id": p.pk, "amount": p.amount, "date": _iso(p.verified_at or p.created_at),
             "date_gmt": _iso_gmt(p.verified_at or p.created_at), "gateway": p.gateway,
             "gateway_title": GATEWAY_NAMES.get(p.gateway, p.gateway), "ref": p.ref_id or ""}
            for p in o.payments.all() if p.status == "ok" and p.gateway != "manix"]  # پرداخت‌های خود مانیکس برنمی‌گردند
    return {
        "id": o.number, "number": str(o.number), "status": STATUS.get(o.status, o.status), "local_status": o.status,
        "local_status_label": o.status_label, "currency": "IRT",
        "date_created": _iso(o.created_at), "date_created_gmt": _iso_gmt(o.created_at),
        "date_modified": _iso(o.updated_at), "date_modified_gmt": _iso_gmt(o.updated_at),
        "date_paid": _iso(o.paid_at), "date_paid_gmt": _iso_gmt(o.paid_at),
        "discount_total": str(o.discount or 0), "shipping_total": "0", "total_tax": "0",
        "total": str(o.items_total), "customer_id": o.user_id or 0, "customer_note": o.note or "",
        "payment_method": o.payment_mode, "payment_method_title": o.get_payment_mode_display(),
        "billing": {"first_name": o.first_name, "last_name": o.last_name, "company": "", "address_1": o.address,
                    "address_2": "", "city": o.city, "state": o.province, "postcode": o.postal_code, "country": "IR",
                    "email": o.email or "", "phone": o.mobile},
        "shipping": {"first_name": o.first_name, "last_name": o.last_name, "address_1": o.address, "city": o.city,
                     "state": o.province, "postcode": o.postal_code, "country": "IR"},
        "line_items": items,
        "meta_data": [{"key": "_manix_payments", "value": pays}, {"key": "_manix_ref", "value": o.manix_ref or ""}, {"key": "_paid_amount", "value": o.paid_amount},
                      {"key": "_payable_total", "value": o.grand_total}],
    }


def _qs(s):
    from .models import Order

    start = timezone.make_aware(datetime.combine(s.manix_start, time.min)) if s.manix_start else None
    qs = Order.objects.all()
    if start:
        qs = qs.filter(created_at__gte=start)
    return qs.prefetch_related("items__variation__size", "items__product", "payments")


@require_GET
def orders(request):
    s, err = _authorized(request)
    if err:
        return err
    g = request.GET
    qs = _qs(s)
    if g.get("after"):
        dt = _parse_dt(g["after"])
        if dt:
            qs = qs.filter(created_at__gt=dt)
    if g.get("before"):
        dt = _parse_dt(g["before"])
        if dt:
            qs = qs.filter(created_at__lt=dt)
    if g.get("modified_after"):
        dt = _parse_dt(g["modified_after"])
        if dt:
            qs = qs.filter(updated_at__gt=dt)
    st = [x.strip() for x in (g.get("status") or "").split(",") if x.strip() and x.strip() != "any"]
    if st:
        local = [y for x in st for y in WC_TO_LOCAL.get(x, [x.replace("-", "_")])]
        qs = qs.filter(status__in=local)
    try:
        per = max(1, min(int(g.get("per_page") or 10), MAX_PER_PAGE))
        page = max(1, int(g.get("page") or 1))
    except ValueError:
        return _err("rest_invalid_param", "page یا per_page نامعتبر است.", 400)
    field = {"date": "created_at", "modified": "updated_at", "id": "number"}.get(g.get("orderby") or "date", "created_at")
    qs = qs.order_by(field if (g.get("order") or "desc").lower() == "asc" else "-" + field, "number")
    total = qs.count()
    rows = [serialize(o) for o in qs[(page - 1) * per: page * per]]
    resp = JsonResponse(rows, safe=False, json_dumps_params={"ensure_ascii": False})
    resp["X-WP-Total"] = str(total)
    resp["X-WP-TotalPages"] = str(max(1, -(-total // per)))
    resp["Cache-Control"] = "no-store"
    return resp


@require_GET
def order_detail(request, number):
    s, err = _authorized(request)
    if err:
        return err
    o = _qs(s).filter(number=number).first()
    if o is None:
        return _err("woocommerce_rest_shop_order_invalid_id", "شناسه نامعتبر است.", 404)
    resp = JsonResponse(serialize(o), json_dumps_params={"ensure_ascii": False})
    resp["Cache-Control"] = "no-store"
    return resp


@require_GET
def index(request):
    """آزمون اتصال (مانیکس پلاس دکمهٔ «آزمون اتصال» دارد)."""
    s, err = _authorized(request)
    if err:
        return err
    return JsonResponse({"namespace": "wc/v3", "store": "irancarpet", "orders_since": str(s.manix_start or ""),
                         "routes": ["/wc/v3/orders", "/wc/v3/orders/<id>", "/wc/v3/manix/catalog", "/wc/v3/manix/orders"]},
                        json_dumps_params={"ensure_ascii": False})


@require_GET
def catalog(request):
    """فرش‌های منتشرشده × سایزها با قیمت روز (برای انتخاب کالا در فاکتور مانیکس)."""
    from .manix import catalog_rows

    s, err = _authorized(request)
    if err:
        return err
    rows = catalog_rows()
    try:
        per = max(1, min(int(request.GET.get("per_page") or 500), 1000))
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        return _err("rest_invalid_param", "page یا per_page نامعتبر است.", 400)
    resp = JsonResponse(rows[(page - 1) * per: page * per], safe=False, json_dumps_params={"ensure_ascii": False})
    resp["X-WP-Total"] = str(len(rows))
    resp["X-WP-TotalPages"] = str(max(1, -(-len(rows) // per)))
    resp["Cache-Control"] = "no-store"
    return resp


@csrf_exempt
@require_POST
def manix_order(request):
    """فاکتور مانیکس ← سفارش تلفنی سایت (+ لینک پرداخت و پیامک آن، اگر خواسته شده)."""
    import json

    from .manix import ManixError, pay_urls, send_pay_sms, upsert_order

    s, err = _authorized(request)
    if err:
        return err
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except ValueError:
        return _err("rest_invalid_json", "بدنهٔ درخواست JSON نیست.", 400)
    try:
        order, lines = upsert_order(data)
    except ManixError as e:
        return _err("manix_invalid", str(e), 400)
    out = {"id": order.number, "status": STATUS.get(order.status, order.status), "local_status": order.status,
           "local_status_label": order.status_label, "paid": order.paid_amount, "total": order.items_total, "items": lines,
           "pay_url": "", "short_url": "", "sms": False}
    if data.get("pay_link") is not None and order.can_pay:
        out["pay_url"], out["short_url"] = pay_urls(order)
        if data.get("send_sms"):
            out["sms"] = bool(send_pay_sms(order))
    return JsonResponse(out, json_dumps_params={"ensure_ascii": False})

