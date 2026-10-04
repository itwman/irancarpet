"""محاسبهٔ اقساط با راس‌گیری.

سود = درصد ماهانه × (میانگین فاصلهٔ سررسیدها به روز ÷ ۳۰)
مثال: ۲ قسط ماهانه → سررسیدها ۳۰ و ۶۰ روز → راس ۴۵ روز → با سود ماهی ۶٪ می‌شود ۹٪.
مبلغ اقساط = (مبلغ سبد − پیش‌پرداخت) × (۱ + سود)، به تعداد قسط تقسیم و رو به بالا گرد می‌شود.
تاریخ قسط‌ها (شمسی): «تاریخ سفارش + روزهای آماده‌سازی» به اضافهٔ k دوره.
"""
import datetime as dt
import math
from decimal import ROUND_HALF_UP, Decimal

import jdatetime

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


class QuoteError(ValueError):
    pass


def _j_days_in_month(y, m):
    if m <= 6:
        return 31
    if m <= 11:
        return 30
    return 30 if jdatetime.date(y, 1, 1).isleap() else 29


def add_jalali_months(d, months):
    """d: jdatetime.date؛ همان روز ماه، k ماه بعد (اگر آن ماه کوتاه‌تر بود، آخر ماه)."""
    idx = d.month - 1 + months
    y, m = d.year + idx // 12, idx % 12 + 1
    return jdatetime.date(y, m, min(d.day, _j_days_in_month(y, m)))


def quote(plan, total, down_percent, months, step=1, start=None):
    """خروجی dict با همهٔ جزئیات؛ در صورت ورودی نادرست QuoteError با پیام فارسی."""
    total = int(total)
    if total <= 0:
        raise QuoteError("مبلغ خرید معتبر نیست.")
    if plan.min_order_amount and total < plan.min_order_amount:
        raise QuoteError(f"این روش برای خریدهای بالای {plan.min_order_amount:,} تومان است.".translate(FA_DIGITS))
    step = int(step)
    if step not in plan.steps():
        raise QuoteError("فاصلهٔ اقساط مجاز نیست.")
    months = int(months)
    if months not in plan.months_for(step):
        raise QuoteError("مدت اقساط مجاز نیست.")
    down_percent = int(down_percent)
    if not (plan.min_down_percent <= down_percent <= max(plan.max_down_percent, plan.min_down_percent)) or down_percent >= 100:
        raise QuoteError(f"پیش‌پرداخت باید دست‌کم {plan.min_down_percent}٪ باشد.".translate(FA_DIGITS))

    down = int(math.ceil(total * down_percent / 100 / 1000) * 1000) if down_percent else 0
    down = min(down, total)
    principal = total - down
    count = months // step
    due_days = [30 * step * k for k in range(1, count + 1)]
    ras_days = Decimal(sum(due_days)) / count
    rate = Decimal(plan.monthly_rate)
    interest_percent = (rate * ras_days / 30).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    payable = Decimal(principal) * (1 + interest_percent / 100)
    round_to = max(int(plan.round_to or 0), 1)
    each = math.ceil(float(payable) / count / round_to - 1e-9) * round_to
    installments_total = each * count

    if start is None:
        from django.utils import timezone

        start = timezone.localdate()
    base = jdatetime.date.fromgregorian(date=start + dt.timedelta(days=int(plan.first_due_days)))
    schedule = []
    for k in range(1, count + 1):
        jd = add_jalali_months(base, k * step)
        schedule.append({"n": k, "date": jd.togregorian().isoformat(), "jdate": jd.strftime("%Y/%m/%d"), "amount": each})

    return {
        "plan": plan.pk, "plan_title": plan.title, "kind": plan.kind,
        "total": total, "down_percent": down_percent, "down": down, "principal": principal,
        "months": months, "step": step, "count": count, "monthly_rate": float(rate),
        "ras_days": float(ras_days), "interest_percent": float(interest_percent),
        "installment": each, "installments_total": installments_total,
        "interest_amount": installments_total - principal, "payable_total": down + installments_total,
        "start": base.togregorian().isoformat(), "schedule": schedule,
    }
