"""سفارش فروشندگان: تقسیم سفارش مشتری، کمیسیون، موجودی، وضعیت‌ها و تسویه."""
import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from .models import CategoryCommission, MarketSettings, Seller, SellerOrder, SellerPayout

log = logging.getLogger(__name__)
S = SellerOrder.Status
_SYNCING = set()


def _money(x):
    return int(Decimal(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def commission_percent(product, seller=None, s=None):
    """کمیسیون: درصد اختصاصی فروشنده ← دستهٔ کالا (یا دستهٔ بالاتر) ← پیش‌فرض."""
    seller = seller or product.seller
    if seller and seller.commission_percent is not None:
        return Decimal(seller.commission_percent)
    cats = []
    if product.primary_category_id:
        cats.append(product.primary_category)
    cats += [c for c in product.categories.all() if c.pk != product.primary_category_id]
    rates = dict(CategoryCommission.objects.values_list("category_id", "percent"))
    if rates:
        for c in cats:
            node, seen = c, set()
            while node is not None and node.pk not in seen:
                seen.add(node.pk)
                if node.pk in rates:
                    return Decimal(rates[node.pk])
                node = node.parent
    return Decimal((s or MarketSettings.load()).default_commission)


# ------------------------------------------------------------------ ثبت سفارش
def split(order):
    """بعد از ثبت سفارش: اقلام هر فروشنده یک «سفارش فروشنده» می‌شوند."""
    s = MarketSettings.load()
    groups = defaultdict(list)
    for it in order.items.select_related("product__seller", "product__primary_category"):
        if it.product_id and it.product.seller_id:
            groups[it.product.seller].append(it)
    out = []
    for seller, items in groups.items():
        so, _ = SellerOrder.objects.get_or_create(order=order, seller=seller)
        total = comm = 0
        for it in items:
            pct = commission_percent(it.product, seller, s)
            it.seller_order, it.commission_percent = so, pct
            it.save(update_fields=["seller_order", "commission_percent"])
            line = it.unit_price * it.quantity
            total += line
            comm += _money(Decimal(line) * pct / 100)
        so.items_total, so.commission, so.seller_amount = total, comm, total - comm
        so.save(update_fields=["items_total", "commission", "seller_amount"])
        out.append(so)
    if out:
        sync(order)
    return out


def has_own_items(order):
    return order.items.filter(seller_order__isnull=True).exists()


# ------------------------------------------------------------------ موجودی
def _stock(so, sign):
    from catalog.models import Product, Variation

    pids = set()
    for it in so.items.select_related("variation"):
        v = it.variation
        if v is None or v.stock_qty is None:
            continue
        qty = max(0, v.stock_qty + sign * it.quantity)
        Variation.objects.filter(pk=v.pk).update(stock_qty=qty, is_available=qty > 0 if sign < 0 else True)
        pids.add(v.product_id)
    for p in Product.objects.filter(pk__in=pids):
        p.refresh_price_cache()


def take_stock(so):
    if not so.stock_taken:
        _stock(so, -1)
        SellerOrder.objects.filter(pk=so.pk).update(stock_taken=True)
        so.stock_taken = True


def return_stock(so):
    if so.stock_taken:
        _stock(so, +1)
        SellerOrder.objects.filter(pk=so.pk).update(stock_taken=False)
        so.stock_taken = False


# ------------------------------------------------------------------ هماهنگی با سفارش مشتری
def sync(order):
    """وضعیت سفارش مشتری ← سفارش فروشنده‌ها (پرداخت، لغو، تحویل توسط مدیر)."""
    if order.pk in _SYNCING:
        return
    _SYNCING.add(order.pk)
    try:
        now = timezone.now()
        for so in order.seller_orders.select_related("seller"):
            if order.status in order.PAID_STATUSES and so.status == S.WAITING:
                so.status, so.paid_at = S.NEW, now
                so.save(update_fields=["status", "paid_at"])
                take_stock(so)
                notify_seller_new(so)
            elif order.status in ("cancelled", "refunded") and so.status not in (S.CANCELLED, S.DELIVERED):
                if so.status != S.SHIPPED:
                    return_stock(so)
                so.status, so.settle = S.CANCELLED, SellerOrder.Settle.NONE
                so.cancel_reason = so.cancel_reason or "لغو سفارش مشتری"
                so.save(update_fields=["status", "settle", "cancel_reason"])
            elif order.status == "completed" and so.status in (S.NEW, S.ACCEPTED, S.SHIPPED):
                _deliver(so, now)
    finally:
        _SYNCING.discard(order.pk)


def order_saved(sender, instance, created=False, **kw):
    if created or kw.get("raw"):
        return
    transaction.on_commit(lambda: _safe_sync(instance))


def _safe_sync(order):
    try:
        if order.seller_orders.exists():
            sync(order)
    except Exception:  # noqa: BLE001
        log.exception("market sync")


def update_parent(order):
    """سفارشی که همهٔ اقلامش از فروشنده‌هاست: وضعیتش از وضعیت ارسال فروشنده‌ها می‌آید."""
    if has_own_items(order):
        return
    sts = list(order.seller_orders.values_list("status", flat=True))
    live = [x for x in sts if x != S.CANCELLED]
    new = None
    if not live:
        new = "cancelled" if order.status in order.PAID_STATUSES else None
    elif all(x == S.DELIVERED for x in live):
        new = "completed"
    elif all(x in (S.SHIPPED, S.DELIVERED) for x in live):
        new = "shipped"
    elif any(x == S.ACCEPTED for x in live) and order.status == "paid":
        new = "processing"
    if new and new != order.status and order.status not in ("pending", "on_hold", "refunded"):
        order.status = new
        _SYNCING.add(order.pk)
        try:
            order.save(update_fields=["status"])
        finally:
            _SYNCING.discard(order.pk)


# ------------------------------------------------------------------ کارهای فروشنده، مشتری و مدیر
def accept(so):
    if so.status != S.NEW:
        return False
    so.status, so.accepted_at = S.ACCEPTED, timezone.now()
    so.save(update_fields=["status", "accepted_at"])
    update_parent(so.order)
    return True


def ship(so, tracking_code, carrier=""):
    if so.status not in (S.NEW, S.ACCEPTED, S.SHIPPED):
        return False
    so.status = S.SHIPPED
    so.tracking_code, so.carrier = tracking_code.strip()[:100], carrier.strip()[:60]
    so.shipped_at = so.shipped_at or timezone.now()
    so.accepted_at = so.accepted_at or so.shipped_at
    so.save(update_fields=["status", "tracking_code", "carrier", "shipped_at", "accepted_at"])
    update_parent(so.order)
    try:
        from accounts.sms import send_bulk

        send_bulk([so.order.mobile], f"ایران کارپت: بخشی از سفارش {so.order.number} توسط «{so.seller.name}» ارسال شد."
                                     + (f" {carrier}" if carrier else "") + f" کد رهگیری: {so.tracking_code}", kind="market", order=so.order)
    except Exception:  # noqa: BLE001
        pass
    return True


def cancel(so, reason, by_seller=True):
    if so.status in (S.SHIPPED, S.DELIVERED, S.CANCELLED):
        return False
    return_stock(so)
    so.status, so.settle, so.cancel_reason = S.CANCELLED, SellerOrder.Settle.NONE, (reason or "").strip()[:300]
    so.save(update_fields=["status", "settle", "cancel_reason"])
    if by_seller:
        try:
            from shop.notify import admin_text

            admin_text(f"فروشنده «{so.seller.name}» بخش خودش از سفارش {so.order.number} ({so.items_total:,} تومان) را لغو کرد: "
                       f"{so.cancel_reason}. مبلغ را به مشتری برگردانید.")
        except Exception:  # noqa: BLE001
            pass
    update_parent(so.order)
    return True


def _deliver(so, when=None):
    s = MarketSettings.load()
    when = when or timezone.now()
    so.status, so.delivered_at = S.DELIVERED, when
    so.payable_at = when + timezone.timedelta(days=s.hold_days)
    so.save(update_fields=["status", "delivered_at", "payable_at"])


def deliver(so):
    if so.status not in (S.NEW, S.ACCEPTED, S.SHIPPED):
        return False
    _deliver(so)
    update_parent(so.order)
    return True


def run_jobs(now=None):
    """هر ۱۰ دقیقه: تحویل خودکار ارسال‌های قدیمی و قابل تسویه شدن سفارش‌های گذشته از مهلت مرجوعی."""
    s = MarketSettings.load()
    now = now or timezone.now()
    n = 0
    old = now - timezone.timedelta(days=s.auto_deliver_days)
    for so in SellerOrder.objects.filter(status=S.SHIPPED, shipped_at__lte=old).select_related("order"):
        _deliver(so, now)
        update_parent(so.order)
        n += 1
    n += SellerOrder.objects.filter(status=S.DELIVERED, settle=SellerOrder.Settle.OPEN, payable_at__lte=now).update(
        settle=SellerOrder.Settle.PAYABLE)
    return n


# ------------------------------------------------------------------ مالی
def balances(seller):
    from django.db.models import Count, Sum

    qs = seller.orders.exclude(status=S.CANCELLED)
    out = {}
    for key, flt in (("waiting", {"status__in": [S.NEW, S.ACCEPTED, S.SHIPPED]}),
                     ("hold", {"status": S.DELIVERED, "settle": SellerOrder.Settle.OPEN}),
                     ("payable", {"settle": SellerOrder.Settle.PAYABLE}),
                     ("paid", {"settle": SellerOrder.Settle.PAID})):
        agg = qs.filter(**flt).aggregate(a=Sum("seller_amount"), n=Count("pk"))
        out[key] = {"amount": agg["a"] or 0, "count": agg["n"]}
    return out


def pay(seller, reference=""):
    """تسویهٔ همهٔ سفارش‌های قابل تسویهٔ یک فروشنده (اگر به حداقل رسیده باشد)."""
    s = MarketSettings.load()
    with transaction.atomic():
        rows = list(SellerOrder.objects.select_for_update().filter(seller=seller, settle=SellerOrder.Settle.PAYABLE))
        total = sum(r.seller_amount for r in rows)
        if not rows or total < s.min_payout:
            return None
        p = SellerPayout.objects.create(seller=seller, amount=total, reference=(reference or "")[:60])
        SellerOrder.objects.filter(pk__in=[r.pk for r in rows]).update(settle=SellerOrder.Settle.PAID, payout=p)
    try:
        from accounts.sms import send_bulk

        send_bulk([seller.mobile], f"ایران کارپت: {total:,} تومان بابت فروش «{seller.name}» به حساب شما واریز شد."
                                   + (f" کد پیگیری: {reference}" if reference else ""))
    except Exception:  # noqa: BLE001
        pass
    return p


# ------------------------------------------------------------------ پیامک
def notify_seller_new(so):
    try:
        from accounts.sms import send_bulk

        s = MarketSettings.load()
        send_bulk([so.seller.mobile], f"ایران کارپت: سفارش تازه {so.order.number} برای «{so.seller.name}» ({so.items_total:,} تومان). "
                                      f"لطفاً تا {s.accept_hours} ساعت در پنل فروشنده تأیید کنید: irancarpet.net/seller/orders/")
    except Exception:  # noqa: BLE001
        pass


def active_seller_q():
    """کالاهایی که در سایت قابل فروش‌اند: کالای خود ایران کارپت یا فروشندهٔ فعال."""
    from django.db.models import Q

    return Q(seller__isnull=True) | Q(seller__status=Seller.Status.ACTIVE)

