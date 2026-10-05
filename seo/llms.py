"""فایل /llms.txt: خلاصهٔ ماشین‌خوان ایران کارپت برای دستیارهای هوش مصنوعی (ChatGPT، Claude، Gemini، Perplexity...).

قالب Markdown طبق پیشنهاد llmstxt.org؛ قیمت‌ها از همان لیست قیمت روز خوانده می‌شوند.
عددها با رقم لاتین و جداکننده نوشته می‌شوند تا مدل‌ها بی‌خطا بخوانند.
"""
import re

import jdatetime
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def n(v):
    return f"{int(v):,}"


def lat(s):
    return str(s or "").translate(FA)


def jdate(dt):
    d = jdatetime.date.fromgregorian(date=timezone.localtime(dt or timezone.now()).date())
    return d.strftime("%Y/%m/%d")


def one_line(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def build():
    from pricing import pricelist

    key = f"llms:{pricelist._version()}"
    text = cache.get(key)
    if text is None:
        text = _build(pricelist)
        cache.set(key, text, 600)
    return text


def _build(pricelist):
    from blog.models import Page
    from catalog.models import Category
    from core.models import SiteSettings

    from .models import SeoSettings

    site, seo = SiteSettings.load(), SeoSettings.load()
    url = settings.SITE_URL
    data = pricelist.build()
    month, year = pricelist.month_year(data["updated"])
    L = []
    add = L.append

    add(f"# {site.site_name} ({url.split('//')[-1]})")
    add("")
    add(f"> {one_line(site.tagline) or 'فروشگاه اینترنتی فرش ماشینی کاشان'}. فروش آنلاین فرش ماشینی کاشان از 500 تا 1500 شانه "
        "در همهٔ سایزها، با قیمت روشن برای هر سایز، خرید نقدی و اقساطی و ارسال به سراسر ایران.")
    add("")
    if seo.llms_about.strip():
        add(seo.llms_about.strip())
        add("")
    add("همهٔ قیمت‌ها به **تومان** است. قیمت‌ها از قیمت‌گذاری روز فروشگاه خوانده می‌شوند و با هر تغییر قیمت کارخانه همین فایل هم عوض می‌شود.")
    add(f"آخرین تغییر قیمت: {jdate(data['updated'])} (شمسی) — {month} {lat(year)}.")
    add("")

    add("## تماس و خرید")
    if site.phone:
        add(f"- تلفن: {lat(site.phone)}")
    if site.mobile:
        add(f"- موبایل پاسخگو: {lat(site.mobile)}")
    for k, name, link in site.messengers:
        add(f"- گفتگو در {name}: {link}")
    if site.email:
        add(f"- ایمیل: {site.email}")
    if site.address:
        add(f"- نشانی: {one_line(site.address)}")
    for k, name, link in site.follows:
        add(f"- {name}: {link}")
    add(f"- خرید آنلاین: {url}/ (افزودن به سبد، پرداخت از درگاه بانکی)")
    add("")

    add(f"## لیست قیمت فرش ماشینی ({month} {lat(year)})")
    add(f"صفحهٔ کامل: {url}{pricelist.PRICE_LIST_PATH}")
    add(f"{n(data['albums'])} لیست قیمت (طرح/آلبوم) و {n(data['products'])} فرش. قیمت سایزهای دیگر هر لیست به نسبت متراژ از قیمت 12 متری به دست می‌آید.")
    add("")
    for g in data["groups"]:
        title = lat(g["title"])
        if g["min_base"]:
            rng = (f"{n(g['min_base'])} تومان" if g["min_base"] == g["max_base"]
                   else f"از {n(g['min_base'])} تا {n(g['max_base'])} تومان")
            add(f"### {title} — 12 متری {rng}")
        else:
            add(f"### {title}")
        sizes = {s.pk: lat(s.label) for s in g["sizes"]}
        for a in g["albums"]:
            prices = "؛ ".join(f"{sizes[sid]}: {n(p)}" for sid, p in a["prices"].items() if sid in sizes)
            company = f" — {a['company']}" if a["company"] else ""
            add(f"- [{lat(a['title'])}]({url}{a['url']}){company} — {n(a['count'])} طرح — {prices} تومان")
        add("")

    try:
        from installments.services import active_plans, describe, page_url

        plans = active_plans()
    except ImportError:
        plans = []
    if plans:
        add("## خرید اقساطی")
        inst = page_url()
        if inst:
            add(f"صفحه و ماشین‌حساب اقساط: {url}{inst}")
        for p in plans:
            add(f"- {p.title}: {lat(describe(p)).replace(' · ', '، ')}")
        add("- سود با راس‌گیری حساب می‌شود: میانگین فاصلهٔ سررسید قسط‌ها (روز) ÷ 30 × سود ماهانه. "
            "مثال: دو قسط ماهانه راس 45 روز دارد و با سود ماهی 6٪ سود کل 9٪ می‌شود.")
        add("- خرید اقساطی کاملاً آنلاین نیست: درخواست در سایت ثبت می‌شود، فروشگاه مدارک را بررسی و تأیید می‌کند، بعد خرید نهایی می‌شود.")
        add("")

    add("## دسته‌های اصلی")
    for c in Category.objects.filter(parent=None).order_by("order")[:20]:
        add(f"- [{lat(c.name)}]({url}{c.get_absolute_url()})")
    add("")

    add("## صفحه‌های مهم")
    for p in Page.objects.filter(status="publish").exclude(template__in=["cart", "checkout", "account", "tracking", "home"])\
            .exclude(robots__contains="noindex").order_by("menu_order")[:25]:
        add(f"- [{lat(p.title)}]({url}{p.get_absolute_url()})")
    add(f"- [مجله و راهنمای خرید فرش]({url}/blog/)")
    add("")

    add("## Optional")
    add(f"- [نقشهٔ سایت]({url}/sitemap_index.xml)")
    add("")
    return "\n".join(L)
