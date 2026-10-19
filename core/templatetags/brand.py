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
