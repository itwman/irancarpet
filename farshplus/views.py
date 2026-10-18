from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from . import gift


@require_http_methods(["GET", "POST"])
def gift_page(request):
    info = gift.info()
    if info is None:
        raise Http404
    if request.method == "POST":
        from accounts.utils import normalize_mobile

        mobile = normalize_mobile(request.POST.get("mobile", ""))
        if not mobile:
            return JsonResponse({"ok": False, "msg": "شمارهٔ موبایل را درست وارد کنید (مثل ۰۹۱۲۱۲۳۴۵۶۷)."}, status=400)
        if not gift.ip_allowed(request):
            return JsonResponse({"ok": False, "msg": "تعداد درخواست‌ها زیاد بود؛ یک ساعت دیگر امتحان کنید."}, status=429)
        ok, msg = gift.claim(mobile)
        return JsonResponse({"ok": ok, "msg": msg})
    return render(request, "farshplus/gift.html", {
        "g": info,
        "meta": {"title": f"{info['amount']:,} تومان هدیه با دنبال کردن ایران کارپت در فرش پلاس".replace(",", "٬"),
                 "description": "اپ فرش پلاس را نصب کنید، پیج ایران کارپت را دنبال کنید و کد تخفیف شخصی بگیرید.",
                 "canonical": settings.SITE_URL + info["url"]},
        "crumbs": [("هدیهٔ فرش پلاس", info["url"])],
    })
