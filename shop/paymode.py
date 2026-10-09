"""روش پرداخت سفارشِ هنوز پرداخت‌نشده: مبلغی که الان باید پرداخت شود و امکان عوض کردن کامل ↔ بیعانه پیش از پرداخت."""
from .models import ShopSettings

LABELS = {"full": "پرداخت کامل", "deposit": "بیعانه", "installment": "پیش‌پرداخت اقساط"}


def due_word(order):
    return {"deposit": "بیعانه", "installment": "پیش‌پرداخت"}.get(order.payment_mode, "مبلغ")


def options(order, shop=None):
    """[{mode, label, amount, note, on}] — فقط برای سفارش غیراقساطیِ منتظر پرداخت؛ کمتر از دو گزینه یعنی انتخابی نیست."""
    if order.is_installment or not order.can_pay:
        return []
    shop = shop or ShopSettings.load()
    total = order.items_total
    out = []
    if shop.allow_full:
        free = shop.shipping_for("full", _own_total(order)) == "free"
        out.append({"mode": "full", "label": "پرداخت کامل", "amount": total, "note": "با ارسال رایگان" if free else ""})
    if shop.allow_deposit and shop.deposit_percent:
        dep = shop.deposit_amount(total)
        out.append({"mode": "deposit", "label": f"بیعانه {shop.deposit_percent}٪", "amount": dep, "note": f"بقیه ({total - dep:,} تومان) موقع تحویل"})
    for o in out:
        o["on"] = o["mode"] == order.payment_mode
    return out


def _own_total(order):
    return sum(it.unit_price * it.quantity for it in order.items.select_related("product")
               if not (it.product_id and getattr(it.product, "seller_id", None)))


def switch(order, mode, shop=None):
    """عوض کردن روش پرداخت پیش از پرداخت. خروجی: True اگر عوض شد."""
    shop = shop or ShopSettings.load()
    if mode == order.payment_mode or mode not in {o["mode"] for o in options(order, shop)}:
        return False
    order.payment_mode = mode
    order.deposit_percent = shop.deposit_percent if mode == "deposit" else 0
    order.online_amount = shop.deposit_amount(order.items_total) if mode == "deposit" else order.items_total
    order.shipping_mode = shop.shipping_for(mode, _own_total(order))
    order.save(update_fields=["payment_mode", "deposit_percent", "online_amount", "shipping_mode"])
    return True
