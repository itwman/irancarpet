"""{% brand %} و {% site_domain %} — در همهٔ قالب‌ها بدون load در دسترس‌اند (builtins در settings)."""
from django import template

from core import brand as _brand

register = template.Library()


@register.simple_tag(name="brand")
def brand_tag():
    return _brand.name()


@register.simple_tag(name="site_domain")
def site_domain_tag():
    return _brand.domain()


@register.simple_tag(name="trust_facts")
def trust_facts_tag():
    """واقعیت‌های اعتماد برای کادر «دربارهٔ فروشگاه» (partials/_trust_about.html)؛ None اگر خاموش است."""
    from django.core.cache import cache

    hit = cache.get("trust_facts")
    if hit is None:
        hit = _trust_facts() or {}
        cache.set("trust_facts", hit, 600)
    return hit or None


def _trust_facts():
    from django.utils.html import escape, format_html

    from blog.models import Page
    from core.direct import _warranty_text
    from core.models import SiteSettings
    from core.templatetags.fa import fa_num
    from shop.models import ShopSettings

    site = SiteSettings.load()
    if not (site.trust_since or "").strip():
        return None
    name = _brand.name()
    items = []
    hist = Page.objects.filter(status="publish", parent=None, template="history").first()
    since = escape(site.trust_since.strip())
    items.append(format_html("فروشگاه اینترنتی فرش ماشینی کاشان؛ {} (<a href=\"{}\">تاریخچه</a>)", since, hist.get_absolute_url())
                 if hist else format_html("فروشگاه اینترنتی فرش ماشینی کاشان؛ {}", since))
    w = _warranty_text()
    if w:
        items.append(format_html("ضمانت‌نامهٔ کتبی: {} (<a href=\"/guarantee/\">شرایط</a>)", w))
    shop = ShopSettings.load()
    if shop.return_days:
        items.append(format_html("{} روز مهلت انصراف از خرید و بازگشت وجه، با فرش سالم و دست‌نخورده", fa_num(shop.return_days)))
    if site.has_store and site.address:
        items.append(format_html("فروشگاه حضوری: {}", fa_num(" ".join(site.address.split()))))
    if site.license_links or site.enamad_verify_url:
        items.append(format_html("پروانهٔ کسب و نماد اعتماد الکترونیکی، با پیوند استعلام در <a href=\"/license/\">برگهٔ مجوزها</a>"))
    return {"brand": name, "items": [str(x) for x in items]}
