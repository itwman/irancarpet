"""سفارش‌های فرشستان در پنل ایران کارپت.

مقصد (فرشستان): هر سفارش ثبت‌شده (پرداخت‌شده، بیعانه، در انتظار بررسی اقساط و…) به منبع فرستاده می‌شود؛
هر بار که وضعیتش عوض شود دوباره.
منبع (ایران کارپت): سفارش با منبع «فرشستان» ساخته می‌شود؛ اقلام به تنوع و فرصت ویژهٔ خود ایران کارپت وصل‌اند
تا موجودی فرصت‌ها کم شود. پیامک ثبت سفارش ایران کارپت برای این سفارش‌ها فرستاده نمی‌شود (مشتری مال فرشستان است).
"""
import logging

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .client import MirrorError, get_json
from .models import MirrorLink, MirrorOrder, MirrorSettings

log = logging.getLogger(__name__)
SRC = "farshestan"


# ---------------------------------------------------------------- مقصد: فرستادن
def payload(order):
    vback, oback = {}, {}
    for lk in MirrorLink.objects.filter(product__in=[i.product_id for i in order.items.all() if i.product_id]):
        vback.update({v: int(k) for k, v in (lk.vmap or {}).items()})
        oback.update({v: int(k) for k, v in (lk.omap or {}).items()})
    return {
        "ref": str(order.number), "status": order.status, "payment_mode": order.payment_mode,
        "first_name": order.first_name, "last_name": order.last_name, "mobile": order.mobile, "email": order.email,
        "province": order.province, "city": order.city, "address": order.address, "postal_code": order.postal_code,
        "note": order.note, "items_total": order.items_total, "discount": order.discount, "paid_amount": order.paid_amount,
        "online_amount": order.online_amount, "coupon": order.coupon_code, "tracking_code": order.tracking_code,
        "created_at": order.created_at.isoformat(), "paid_at": order.paid_at.isoformat() if order.paid_at else "",
        "items": [{"v": vback.get(i.variation_id), "offer": oback.get(i.offer_id), "title": i.title, "size": i.size_label,
                   "unit_price": i.unit_price, "qty": i.quantity} for i in order.items.all()],
    }


def push_all(out=None):
    from shop.coupons import PLACED
    from shop.models import Order

    say = out or (lambda m: None)
    s = MirrorSettings.load()
    if not (s.is_target and s.live and s.push_orders):
        return 0
    since = s.orders_since or s.last_sync_at
    if since is None:
        return 0
    if s.orders_since is None:
        MirrorSettings.objects.filter(pk=s.pk).update(orders_since=since)
    sent = 0
    qs = (Order.objects.filter(created_at__gte=since).exclude(status="pending").select_related("mirror")
          .prefetch_related("items").order_by("pk")[:50])
    for o in qs:
        m = getattr(o, "mirror", None)
        if m and m.last_status == o.status and not m.error:
            continue
        if not m and o.status not in PLACED:
            continue  # لغوشده پیش از پرداخت: لازم نیست
        m = m or MirrorOrder(role="out", order=o)
        try:
            r = get_json("/api/mirror/v1/orders/", body=payload(o), timeout=30)
            m.remote_ref, m.last_status, m.error, m.pushed_at = str(r.get("number") or ""), o.status, "", timezone.now()
            sent += 1
        except MirrorError as e:
            m.error = str(e)[:300]
            log.warning("mirror order %s: %s", o.number, e)
        m.save()
    if sent:
        say(f"{sent} سفارش به سایت منبع فرستاده شد")
    return sent


# ---------------------------------------------------------------- منبع: دریافت
@transaction.atomic
def receive(d):
    from catalog.models import Variation
    from shop.models import Order, OrderItem, SpecialOffer

    ref = str(d["ref"])[:40]
    m = MirrorOrder.objects.select_related("order").filter(role="in", remote_ref=ref).first()
    status = d.get("status") if d.get("status") in dict(Order.Status.choices) else "processing"
    if m:  # به‌روزرسانی وضعیت
        o = m.order
        o.status, o.paid_amount = status, int(d.get("paid_amount") or 0)
        o.tracking_code = (d.get("tracking_code") or o.tracking_code)[:100]
        o.updated_at = timezone.now()
        o.save(update_fields=["status", "paid_amount", "tracking_code", "updated_at"])
        m.last_status = status
        m.save(update_fields=["last_status"])
        return o.number
    o = Order(
        first_name=d["first_name"][:100], last_name=d["last_name"][:100], mobile=d["mobile"][:11], email=(d.get("email") or "")[:254],
        province=(d.get("province") or "")[:60], city=(d.get("city") or "")[:80], address=d.get("address") or "",
        postal_code=(d.get("postal_code") or "")[:10], note=d.get("note") or "", status=status,
        payment_mode=d.get("payment_mode") or "full", items_total=int(d.get("items_total") or 0),
        discount=int(d.get("discount") or 0), paid_amount=int(d.get("paid_amount") or 0),
        online_amount=int(d.get("online_amount") or 0), coupon_code="",
        src=SRC, src_name="فرشستان",
        admin_note=f"سفارش فرشستان شمارهٔ {ref}. پول در درگاه فرشستان دریافت شده" + (f"؛ کد تخفیف فرشستان: {d['coupon']}" if d.get("coupon") else "") + ".",
    )
    if d.get("created_at"):
        o.created_at = parse_datetime(d["created_at"]) or o.created_at
    if d.get("paid_at"):
        o.paid_at = parse_datetime(d["paid_at"])
    o.save()
    items = []
    for it in d.get("items") or []:
        v = Variation.objects.filter(pk=it.get("v")).select_related("product").first() if it.get("v") else None
        offer = SpecialOffer.objects.filter(pk=it.get("offer")).first() if it.get("offer") else None
        items.append(OrderItem(order=o, product=v.product if v else None, variation=v, title=(it.get("title") or "")[:300],
                               size_label=(it.get("size") or "")[:150], unit_price=int(it.get("unit_price") or 0),
                               quantity=max(1, int(it.get("qty") or 1)), offer=offer))
    OrderItem.objects.bulk_create(items)
    if any(i.offer_id for i in items):
        from shop.offers import clear

        clear()
    MirrorOrder.objects.create(role="in", order=o, remote_ref=ref, last_status=status, pushed_at=timezone.now())
    return o.number
