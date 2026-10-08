"""کالای فروشندگان در سبد و پرداخت."""
from collections import OrderedDict

ONLY_FULL = "کالای فروشندگان مارکت‌پلیس فقط با پرداخت کامل آنلاین خریده می‌شود؛ برای بیعانه یا اقساط، آن‌ها را جدا سفارش دهید."


def seller_lines(lines):
    return [ln for ln in lines if getattr(ln.product, "seller_id", None)]


def restrict_modes(modes, lines):
    """سبدی که کالای فروشنده دارد فقط پرداخت کامل آنلاین دارد (بیعانه و اقساط ریسک فروشنده را به ما می‌دهد)."""
    if seller_lines(lines):
        return ["full"]
    return modes


def own_total(lines):
    """جمع کالاهای خود ایران کارپت (برای ارسال رایگان که فقط شامل کالای خود ماست)."""
    return sum(ln.total for ln in lines if not ln.problem and not getattr(ln.product, "seller_id", None))


def groups(lines):
    """[(فروشنده یا None، اقلام)] برای نمایش «ارسال توسط …» در سبد و تسویه."""
    out = OrderedDict()
    for ln in lines:
        out.setdefault(ln.product.seller if getattr(ln.product, "seller_id", None) else None, []).append(ln)
    return list(out.items())
