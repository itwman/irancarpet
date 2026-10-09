"""صفحهٔ «باشگاه مشتریان» در حساب کاربری: امتیاز، تبدیل به کد تخفیف، کدهای شخصی و ثبت تاریخ تولد."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.utils import latin_digits, normalize_mobile

from . import points
from .models import CrmSettings
from .segments import JMONTHS

META = {"robots": "noindex, nofollow"}
KNOTS = 60


def mobile_of(user):
    return normalize_mobile(getattr(getattr(user, "profile", None), "mobile", "") or "") or normalize_mobile(user.username or "")


@login_required(login_url="/my-account/login/")
def club(request):
    from accounts.views import profile_of
    from shop.models import ShopSettings

    s = CrmSettings.load()
    user = request.user
    profile = profile_of(user)
    mobile = mobile_of(user)
    if request.method == "POST":
        if request.POST.get("do") == "redeem" and mobile:
            raw = latin_digits(request.POST.get("points", "")).strip()
            coupon, err = points.redeem(mobile, int(raw) if raw.isdigit() else 0, s)
            if err:
                messages.error(request, err)
            else:
                messages.success(request, f"کد تخفیف شما ساخته شد: {coupon.code} — در سبد خرید وارد کنید.")
        elif request.POST.get("do") == "birthday":
            if profile.birth_month:
                messages.info(request, "تاریخ تولد قبلاً ثبت شده؛ برای تغییر با پشتیبانی تماس بگیرید.")
            else:
                m, d = latin_digits(request.POST.get("month", "")), latin_digits(request.POST.get("day", ""))
                if m.isdigit() and d.isdigit() and 1 <= int(m) <= 12 and 1 <= int(d) <= (31 if int(m) <= 6 else 30):
                    profile.birth_month, profile.birth_day = int(m), int(d)
                    profile.save(update_fields=["birth_month", "birth_day"])
                    messages.success(request, "تاریخ تولد ثبت شد. روز تولدتان منتظر هدیهٔ ما باشید!")
                else:
                    messages.error(request, "روز و ماه تولد را درست انتخاب کنید.")
        return redirect("/my-account/club/")

    bal = points.balance(mobile, s) if mobile else 0
    need = max(s.points_min_redeem, 1)
    filled = min(KNOTS, round(KNOTS * bal / need)) if bal else 0
    shop = ShopSettings.load()
    return render(request, "crm/club.html", {
        "meta": {**META, "title": "باشگاه مشتریان"}, "s": s, "profile": profile, "mobile": mobile,
        "balance": bal, "value": bal * s.point_value, "earned": points.earned(mobile, s) if mobile else 0,
        "to_go": max(need - bal, 0), "can_redeem": s.points_enabled and bal >= s.points_min_redeem,
        "max_redeem": bal, "knots": [i < filled for i in range(KNOTS)],
        "coupons": points.my_coupons(mobile) if mobile else [], "months": list(enumerate(JMONTHS, 1)), "days": range(1, 32),
        "birth_label": f"{profile.birth_day} {JMONTHS[profile.birth_month - 1]}" if profile.birth_month and profile.birth_day else "",
        "shop": shop,
    })
