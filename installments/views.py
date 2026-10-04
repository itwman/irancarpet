import json
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from accounts.utils import latin_digits
from core import seo
from core.templatetags.fa import fa_num

from .calc import QuoteError, quote
from .models import InstallmentPlan
from .services import active_plans, describe, faq_answer

SHORTCODE = "[installment_plans]"


def quote_api(request):
    """محاسبهٔ اقساط برای ماشین‌حساب صفحه‌ها: ?plan=&total=&down=&months=&step= (بدون total: جمع سبد خرید)."""
    g = request.GET
    plan = InstallmentPlan.objects.filter(pk=latin_digits(g.get("plan", "0")) or 0, is_active=True).first()
    if not plan:
        return JsonResponse({"error": "روش اقساط پیدا نشد."}, status=404)
    total = latin_digits(g.get("total", "")).replace(",", "")
    if not total.isdigit():
        from shop.cart import Cart

        total = Cart(request).summary()["total"]
    try:
        q = quote(plan, int(total), latin_digits(g.get("down", str(plan.min_down_percent))),
                  latin_digits(g.get("months", "0")), latin_digits(g.get("step", "1")))
    except (QuoteError, ValueError) as e:
        return JsonResponse({"error": str(e) if isinstance(e, QuoteError) else "مقادیر درست نیست."}, status=400)
    return JsonResponse(q)


def plans_payload(plans):
    return json.dumps([p.config() for p in plans], ensure_ascii=False)


def info_page(request, page):
    """برگهٔ «خرید اقساطی» (قالب installment): متن برگه + کارت روش‌ها و ماشین‌حساب به جای [installment_plans]."""
    if page.status != "publish" and not request.user.is_staff:
        raise Http404
    plans = active_plans()
    content = page.content or ""
    before, _, after = content.partition(SHORTCODE) if SHORTCODE in content else (content, "", "")
    amount = latin_digits(request.GET.get("amount", "")).replace(",", "")
    amount = int(amount) if amount.isdigit() and 1_000_000 <= int(amount) <= 10_000_000_000 else 50_000_000
    faq = []
    if plans:
        faq.append({"q": "آیا می‌شود فرش ماشینی را قسطی خرید؟", "a": faq_answer()})
        faq.append({"q": "سود اقساط چطور حساب می‌شود؟",
                    "a": "با راس‌گیری: میانگین فاصلهٔ سررسید قسط‌ها به روز، تقسیم بر ۳۰، ضرب در درصد سود ماهانه. "
                         "مثلاً دو قسط ماهانه راس ۴۵ روز دارد و با سود ماهی ۶٪ سود کل ۹٪ می‌شود."})
        for p in plans:
            if p.kind == "cheque":
                faq.append({"q": "برای خرید با چک چه مدارکی لازم است؟",
                            "a": "تصویر یک برگ از دسته‌چک صیادی خودتان و مشخصاتتان را هنگام سفارش می‌فرستید. "
                                 "بعد از تأیید، چک‌ها را طبق جدول اقساط می‌نویسید و پست می‌کنید؛ پیش از تأیید چک ننویسید."})
            if p.kind == "beta":
                faq.append({"q": "بازنشستگان چطور قسطی خرید کنند؟",
                            "a": f"از راه سامانهٔ بتا بانک رفاه: پیش‌پرداخت دلخواه (حتی صفر)، {fa_num(p.min_months)} تا {fa_num(p.max_months)} ماه. "
                                 "مشخصات بازنشسته یا مستمری‌بگیر، کد ملی و شمارهٔ دریافت پیامک بانک را وارد می‌کنید و پیامک تأیید بانک را تأیید می‌کنید."})
        faq.append({"q": "تاریخ اولین قسط کی است؟",
                    "a": f"اقساط از حدود {fa_num(plans[0].first_due_days)} روز بعد از ثبت سفارش (زمان آماده‌شدن فرش) شروع می‌شود و اولین قسط یک دوره بعد از آن است."})
    graph = [{"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "خانه", "item": settings.SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": page.title, "item": settings.SITE_URL + page.get_absolute_url()}]}]
    if faq:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]})
    return render(request, "installments/info.html", {
        "meta": seo.build(page, "page"), "page": page, "before": before, "after": after,
        "plans": [(p, describe(p)) for p in plans], "plans_json": plans_payload(plans), "amount": amount, "faq": faq,
        "crumbs": [(page.title, page.get_absolute_url())],
        "jsonld": json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False),
    })


@never_cache
def private_file(request, pk, key):
    """تصویر چک/مدارک مشتری فقط برای کارمندان پنل."""
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    from shop.models import Order

    order = get_object_or_404(Order, pk=pk)
    rel = (order.installment_info or {}).get(key)
    if not rel:
        raise Http404
    root = Path(settings.PRIVATE_ROOT).resolve()
    path = (root / rel).resolve()
    if root not in path.parents or not path.is_file():
        raise Http404
    return FileResponse(open(path, "rb"), content_type="image/jpeg")
