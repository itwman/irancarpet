from functools import partial

from django import forms
from django.conf import settings as django_settings
from django.contrib import messages
from django.forms import modelform_factory
from django.shortcuts import redirect, render

from accounts import sms
from accounts.utils import normalize_mobile
from core.models import SiteSettings
from farshplus import sync as fp_sync
from farshplus.client import ApiError
from farshplus.models import FarshPlusItem, FarshPlusSettings
from pricing.models import PricingSettings
from shop import config, gateways
from shop.models import ShopSettings
from api.models import AppSettings
from content.models import ContentSettings
from rajyar.models import RajyarSettings
from seo import indexnow
from seo.models import SeoSettings
from torob.models import TorobSettings

from ..auth import clear_site_cache, staff_required
from ..forms import formfield_for, style_form
from ..models import log

SECRET_FIELDS = {"smsir_api_key", "zarinpal_merchant_id", "api_key"}  # api_key: فرش پلاس و رج‌یار

TABS = [
    ("site", "سایت و تماس"),
    ("shop", "فروش و ارسال"),
    ("gateways", "درگاه‌های پرداخت"),
    ("sms", "پیامک"),
    ("pricing", "فرمول قیمت"),
    ("farshplus", "فرش پلاس"),
    ("torob", "فید ترب و ایمالز"),
    ("app", "اپلیکیشن"),
    ("seo", "سئو و هوش مصنوعی"),
    ("rajyar", "رج‌یار (کانال‌ها)"),
    ("content", "متن محصولات"),
]

FORMS = {
    "site": (SiteSettings, ["site_name", "tagline", "title_separator", "home_title", "home_description", "phone", "mobile", "whatsapp",
                            "telegram", "eitaa", "telegram_channel", "eitaa_channel", "bale_channel", "instagram", "aparat", "youtube", "farshplus",
                            "email", "address", "store_name", "store_city", "store_province", "store_postal_code",
                            "store_days", "store_open", "store_close", "store_open2", "store_close2", "store_hours_note",
                            "latitude", "longitude", "map_google", "map_neshan", "map_balad",
                            "trust_badge", "trust_html", "footer_html"]),
    "shop": (ShopSettings, ["allow_full", "allow_deposit", "deposit_percent", "free_shipping_min", "checkout_note", "admin_mobiles",
                            "referral_enabled", "referral_percent", "referral_max", "referral_min_order", "referral_reward"]),
    "gateways": (ShopSettings, ["sep_enabled", "sep_terminal_id", "zarinpal_enabled", "zarinpal_merchant_id", "zarinpal_sandbox"]),
    "sms": (ShopSettings, ["smsir_api_key", "smsir_otp_template_id", "smsir_order_template_id", "smsir_admin_template_id",
                            "smsir_line_number"]),
    "pricing": (PricingSettings, ["markup_percent", "shipping_fixed", "round_to", "round_method", "show_size_table"]),
    "farshplus": (FarshPlusSettings, ["enabled", "url", "api_key", "auto_sync", "default_in_feed", "hashtags", "hide_out_of_stock",
                                      "max_images", "categories"]),
    "torob": (TorobSettings, ["enabled", "emalls_enabled", "only_album", "per_page", "price_divisor", "decrease_rate", "tax_percent", "round_to",
                              "title_suffix", "registry_text", "guarantee_attr", "excluded"]),
    "app": (AppSettings, ["latest_version", "min_version", "update_url", "update_note", "home_notice"]),
    "rajyar": (RajyarSettings, ["enabled", "url", "api_key", "channels", "auto_new", "interval_minutes",
                                "price_mode", "price_sizes", "show_specs", "show_summary", "button_text", "tags", "footer",
                                "daily_enabled", "daily_times", "daily_albums",
                                "weekly_enabled", "weekly_day", "weekly_time", "weekly_sizes", "weekly_group", "weekly_reeds", "weekly_albums",
                                "weekly_title"]),
    "seo": (SeoSettings, ["indexnow_enabled", "bing_verification", "llms_about"]),
    "content": (ContentSettings, ["prep_time", "shipping_cost", "cancel_penalty", "warranty", "pair_colors", "pair_note"]),
}


class GeoForm(forms.ModelForm):
    """طول و عرض جغرافیایی با هر تعداد رقم اعشار، ارقام فارسی، هر دو در یک خانه، یا خودکار از پیوند گوگل‌مپ."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for name, label in (("latitude", "عرض جغرافیایی (Latitude)"), ("longitude", "طول جغرافیایی (Longitude)")):
            if name in self.fields:
                self.fields[name] = forms.CharField(label=label, required=False, help_text=(
                    "مثل ۳۳٫۹۹۵۶۰۸۹. می‌توانید هر دو عدد را با ویرگول در همین خانه بنویسید، یا خالی بگذارید تا از پیوند گوگل‌مپ خوانده شود."
                    if name == "latitude" else "مثل ۵۱٫۴۵۸۲۷۱۳"))

    def clean(self):
        from core import geo

        cd = super().clean()
        if "latitude" not in self.fields:
            return cd
        lat_txt, lng_txt = cd.get("latitude") or "", cd.get("longitude") or ""
        lat = lng = None
        try:
            both = geo.pair(lat_txt) or geo.pair(lng_txt)
            if both:
                lat, lng = both
            else:
                lat, lng = geo.coord(lat_txt), geo.coord(lng_txt)
        except ValueError:
            self.add_error("latitude", "عدد مختصات را درست بنویسید؛ مثل ۳۳٫۹۹۵۶۰۸۹ و ۵۱٫۴۵۸۲۷۱۳.")
            return cd
        if lat is None and lng is None:
            for f in ("map_google", "map_neshan", "map_balad"):
                got = geo.from_url(cd.get(f) or "")
                if got:
                    lat, lng = got
                    break
        if (lat is None) != (lng is None):
            self.add_error("longitude" if lng is None else "latitude", "هر دو عدد طول و عرض جغرافیایی لازم است.")
        elif lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            self.add_error("latitude", "عددها جابه‌جا یا نادرست‌اند؛ عرض ایران حدود ۲۵ تا ۴۰ و طول حدود ۴۴ تا ۶۳ است.")
        elif lat is not None and 44 <= lat <= 63 and 25 <= lng <= 40:  # جابه‌جا وارد شده
            lat, lng = lng, lat
        cd["latitude"], cd["longitude"] = lat, lng
        return cd


def make_form(tab, data=None):
    model, fields = FORMS[tab]
    Form = modelform_factory(model, form=GeoForm, fields=fields, formfield_callback=partial(formfield_for, ac_urls={}))
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
def rajyar_pricelist_png(request):
    """پیش‌نمایش تصویر لیست قیمت هفتگی (بدون ارسال)."""
    from django.http import HttpResponse

    from rajyar.pricelist_image import render as render_png

    png, _d, _s = render_png(RajyarSettings.load())
    resp = HttpResponse(png, content_type="image/png")
    resp["Cache-Control"] = "no-store"
    return resp


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
        if request.POST.get("do") == "rajyar_ping":
            from rajyar.client import ping

            ok, msg = ping()
            (messages.success if ok else messages.error)(request, f"رج‌یار: {msg}")
            return redirect("/panel/settings/?tab=rajyar")
        if request.POST.get("do") in ("rajyar_weekly_now", "rajyar_daily_now"):
            from rajyar import auto
            from rajyar.client import RajyarError

            rs = RajyarSettings.load()
            try:
                post = auto.send_weekly(rs) if request.POST["do"] == "rajyar_weekly_now" else auto.send_daily(rs)
            except RajyarError as e:
                messages.error(request, f"رج‌یار: {e}")
            else:
                ok = post.status != "failed"
                what = "لیست قیمت" if post.kind == "weekly" else f"«{post.product}»" if post.product_id else "فرش"
                (messages.success if ok else messages.error)(
                    request, f"{what} به رج‌یار فرستاده شد." if ok else f"ارسال نشد: {post.error}")
            log(request, "action", "رج‌یار", None, request.POST["do"])
            return redirect("/panel/settings/?tab=rajyar")
        if request.POST.get("do") == "indexnow_all":
            urls = indexnow.all_urls()
            ok, msg = indexnow.submit(urls)
            log(request, "action", "IndexNow", None, f"ارسال {len(urls)} نشانی")
            (messages.success if ok else messages.error)(request, f"IndexNow: {msg} ({len(urls)} نشانی).")
            return redirect("/panel/settings/?tab=seo")
        if request.POST.get("do", "").startswith("fp_"):
            return farshplus_action(request, request.POST["do"])
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
            form.save_m2m()
            log(request, "update", "تنظیمات", None, dict(TABS)[tab])
            clear_site_cache()
            msg = "تنظیمات ذخیره شد."
            if tab == "torob":
                from django.core.cache import cache

                cache.delete("torob_rows")
            messages.success(request, msg)
            return redirect(f"/panel/settings/?tab={tab}")
        messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        form = make_form(tab)
    return render(request, "dashboard/settings.html", {
        "tabs": TABS, "tab": tab, "form": form, "trust": trust, "info": status_info(),
        "fp": farshplus_info() if tab == "farshplus" else None,
        "seo": SeoSettings.load() if tab == "seo" else None,
        "rj": RajyarSettings.load() if tab == "rajyar" else None,
        "rj_next": __import__("rajyar.auto", fromlist=["next_runs"]).next_runs(RajyarSettings.load()) if tab == "rajyar" else [], "SITE_URL": django_settings.SITE_URL,
        "callback_sep": request.build_absolute_uri("/pay/sep/callback/"),
        "callback_zp": request.build_absolute_uri("/pay/zarinpal/callback/"),
    })


def farshplus_info():
    from django.db.models import Count

    s = FarshPlusSettings.load()
    counts = dict(FarshPlusItem.objects.values_list("status").annotate(n=Count("id")))
    return {"s": s, "inactive": fp_sync.inactive_reason(s), "counts": counts,
            "queued": FarshPlusItem.objects.filter(queued=True).count(),
            "published": counts.get("PUBLISHED", 0), "errors": FarshPlusItem.objects.exclude(error="").count(),
            "page": (s.connection or {}).get("page") or {}, "limits": s.limits}


def farshplus_action(request, do):
    s = FarshPlusSettings.load()
    if do == "fp_check":
        try:
            me = fp_sync.check_connection(s)
            page = me.get("page") or {}
            messages.success(request, f"اتصال برقرار است: صفحهٔ «{page.get('name', '')}» در فرش پلاس.")
        except ApiError as e:
            messages.error(request, f"اتصال برقرار نشد: {e}")
    elif do == "fp_bulk":
        n = fp_sync.queue_all_unsent(s)
        log(request, "action", "فرش پلاس", None, f"ارسال گروهی {n} محصول")
        messages.success(request, f"{n} محصول در صف ارسال گروهی قرار گرفت (روزانه تا سقف مجاز فرستاده می‌شوند).")
    elif do == "fp_run":
        why = fp_sync.inactive_reason(s)
        if why:
            messages.error(request, why)
        else:
            lines = []
            n = fp_sync.run(limit=3, out=lines.append)
            messages.info(request, f"{n} درخواست انجام شد. " + " ".join(lines[-3:]))
    elif do == "fp_resume":
        s.rate_limited_until = None
        s.save(update_fields=["rate_limited_until"])
        messages.success(request, "توقف برداشته شد.")
    return redirect("/panel/settings/?tab=farshplus")
