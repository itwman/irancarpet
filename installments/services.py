"""کمک‌های مشترک: روش‌های فعال، نمونهٔ «اقساط از ماهی…»، متن پرسش متداول."""
from core.templatetags.fa import fa_num, toman

from .calc import QuoteError, quote
from .models import InstallmentPlan


def page_url():
    """آدرس برگهٔ «خرید اقساطی» (اگر منتشر شده باشد)."""
    from blog.models import Page

    p = Page.objects.filter(template="installment", status="publish").first()
    return p.get_absolute_url() if p else ""


def active_plans(total=None):
    qs = InstallmentPlan.objects.filter(is_active=True)
    plans = list(qs)
    if total is not None:
        plans = [p for p in plans if not p.min_order_amount or total >= p.min_order_amount]
    return plans


def _rate(p):
    return fa_num(f"{p.monthly_rate.normalize():f}")


def teaser(amount):
    """کمترین قسط ماهانه بین روش‌های فعال (با کمترین پیش‌پرداخت و بیشترین مدت ماهانه)."""
    best = None
    for p in active_plans(amount):
        step = 1 if p.allow_monthly else p.steps()[0]
        months = p.months_for(step)
        if not months:
            continue
        try:
            q = quote(p, amount, p.min_down_percent, months[-1], step)
        except QuoteError:
            continue
        per_month = q["installment"] / step
        if best is None or per_month < best["per_month"]:
            best = {"plan": p.title, "per_month": per_month, "installment": q["installment"], "count": q["count"],
                    "step": step, "down_percent": q["down_percent"], "down": q["down"], "amount": amount}
    if best:
        best["url"] = page_url()
    return best


def faq_answer():
    plans = active_plans()
    if not plans:
        return ""
    parts = []
    for p in plans:
        down = "بدون پیش‌پرداخت یا با پیش‌پرداخت دلخواه" if p.min_down_percent == 0 else f"با دست‌کم {fa_num(p.min_down_percent)}٪ پیش‌پرداخت"
        parts.append(f"«{p.title}» {down}، {fa_num(p.min_months)} تا {fa_num(p.max_months)} ماه، سود ماهی {_rate(p)}٪")
    return "بله. " + "؛ ".join(parts) + ". قسط‌ها با راس‌گیری حساب می‌شوند و جدول کامل اقساط پیش از ثبت سفارش نشان داده می‌شود."


def describe(p):
    """یک خط توضیح برای کارت هر روش."""
    down = "پیش‌پرداخت دلخواه (حتی صفر)" if p.min_down_percent == 0 else f"حداقل {fa_num(p.min_down_percent)}٪ پیش‌پرداخت"
    period = "ماهانه یا دوماهه" if p.allow_monthly and p.allow_bimonthly else ("دوماهه" if p.allow_bimonthly else "ماهانه")
    return f"{down} · {fa_num(p.min_months)} تا {fa_num(p.max_months)} ماه · {period} · سود ماهی {_rate(p)}٪"


def money(n):
    return toman(n)
