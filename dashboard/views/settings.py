from functools import partial

from django import forms
from django.contrib import messages
from django.forms import modelform_factory
from django.shortcuts import redirect, render

from accounts import sms
from accounts.utils import normalize_mobile
from core.models import SiteSettings
from pricing.models import PricingSettings
from shop import config, gateways
from shop.models import ShopSettings

from ..auth import clear_site_cache, staff_required
from ..forms import formfield_for, style_form
from ..models import log

SECRET_FIELDS = {"smsir_api_key", "zarinpal_merchant_id"}

TABS = [
    ("site", "سایت و تماس"),
    ("shop", "فروش و ارسال"),
    ("gateways", "درگاه‌های پرداخت"),
    ("sms", "پیامک"),
    ("pricing", "فرمول قیمت"),
]

FORMS = {
    "site": (SiteSettings, ["site_name", "tagline", "title_separator", "home_title", "home_description", "phone", "whatsapp",
                            "email", "address", "footer_html"]),
    "shop": (ShopSettings, ["allow_full", "allow_deposit", "deposit_percent", "free_shipping_min", "checkout_note", "admin_mobiles"]),
    "gateways": (ShopSettings, ["sep_enabled", "sep_terminal_id", "zarinpal_enabled", "zarinpal_merchant_id", "zarinpal_sandbox"]),
    "sms": (ShopSettings, ["smsir_api_key", "smsir_otp_template_id", "smsir_order_template_id", "smsir_admin_template_id"]),
    "pricing": (PricingSettings, ["markup_percent", "shipping_fixed", "round_to", "round_method", "show_size_table"]),
}


def make_form(tab, data=None):
    model, fields = FORMS[tab]
    Form = modelform_factory(model, fields=fields, formfield_callback=partial(formfield_for, ac_urls={}))
    inst = model.load()
    form = Form(data, instance=inst)
    for name in fields:
        if name in SECRET_FIELDS:
            has = bool(getattr(inst, name))
            form.fields[name].widget = forms.PasswordInput(render_value=False, attrs={
                "placeholder": "•••••••• (ذخیره شده؛ برای تغییر مقدار تازه بنویسید)" if has else "", "autocomplete": "new-password"})
            form.fields[name].required = False
    return style_form(form)


def keep_secrets(form, inst_before):
    for name in SECRET_FIELDS & set(form.fields):
        if not form.cleaned_data.get(name):
            setattr(form.instance, name, getattr(inst_before, name))


def status_info():
    shop = ShopSettings.load()
    return {
        "sep": bool(config.get("SEP_TERMINAL_ID")), "zarinpal": bool(config.get("ZARINPAL_MERCHANT_ID")),
        "sms": sms.configured(), "fake": gateways.Fake.available(),
        "active": [g.key for g in gateways.enabled(shop)],
    }


@staff_required
def settings_view(request):
    tab = request.GET.get("tab") or request.POST.get("tab") or "site"
    if tab not in FORMS:
        tab = "site"
    trust = SiteSettings.load().trust_points or []
    if request.method == "POST":
        if request.POST.get("do") == "sms_test":
            mobile = normalize_mobile(request.POST.get("test_mobile"))
            if not mobile:
                messages.error(request, "شمارهٔ موبایل آزمایشی درست نیست.")
            elif not sms.configured():
                messages.error(request, "اول کلید API و شمارهٔ قالب کد ورود را ذخیره کنید.")
            elif sms.send_otp(mobile, "12345"):
                messages.success(request, f"پیامک آزمایشی (کد ۱۲۳۴۵) به {mobile} فرستاده شد.")
            else:
                messages.error(request, f"sms.ir پیامک را نفرستاد: {sms.LAST_ERROR['msg'] or 'خطای نامشخص'}")
            return redirect("/panel/settings/?tab=sms")
        model, _ = FORMS[tab]
        before = model.load()
        form = make_form(tab, request.POST)
        if form.is_valid():
            keep_secrets(form, before)
            obj = form.save(commit=False)
            if tab == "site":
                titles = request.POST.getlist("tp_title")
                subs = request.POST.getlist("tp_sub")
                obj.trust_points = [[t.strip(), s.strip()] for t, s in zip(titles, subs) if t.strip()]
            if tab == "pricing" and not form.has_changed():
                messages.info(request, "تغییری نبود.")
                return redirect(f"/panel/settings/?tab={tab}")
            obj.save()
            log(request, "update", "تنظیمات", None, dict(TABS)[tab])
            clear_site_cache()
            msg = "تنظیمات ذخیره شد."
            if tab == "pricing":
                msg += " قیمت همهٔ محصولات با فرمول تازه دوباره محاسبه شد."
            messages.success(request, msg)
            return redirect(f"/panel/settings/?tab={tab}")
        messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        form = make_form(tab)
    return render(request, "dashboard/settings.html", {
        "tabs": TABS, "tab": tab, "form": form, "trust": trust, "info": status_info(),
        "callback_sep": request.build_absolute_uri("/pay/sep/callback/"),
        "callback_zp": request.build_absolute_uri("/pay/zarinpal/callback/"),
    })
