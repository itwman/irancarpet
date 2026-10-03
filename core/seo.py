"""ساخت عنوان، توضیحات، canonical و robots — سازگار با متغیرهای Rank Math."""
import re

from django.conf import settings
from django.utils.html import strip_tags

from .models import SiteSettings
from .templatetags.fa import fa_num

VAR_RE = re.compile(r"%\s*([a-z_]+)%")


def plain(html, limit=None):
    import html as _html

    text = re.sub(r"\s+", " ", _html.unescape(strip_tags(html or "")).replace("\xa0", " ")).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def render(template, ctx):
    if not template:
        return ""
    out = VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "")), template)
    out = re.sub(r"\s+", " ", out).strip()
    sep = re.escape(ctx.get("sep", "-"))
    out = re.sub(rf"^(?:{sep}\s*)+|(?:\s*{sep})+$", "", out).strip()
    return out


def page_label(page):
    return f"صفحه {fa_num(page)}" if page and page > 1 else ""


def build(obj=None, kind="", page=1, extra=None, path=""):
    """kind: product, post, page, product_cat, product_tag, product_brand, pa_<attr>, category, post_tag, home, search."""
    s = SiteSettings.load()
    tpl = s.title_templates or {}
    ctx = {"sitename": s.site_name, "sep": s.title_separator or "-", "page": page_label(page)}
    ctx.update(extra or {})
    if kind == "home":
        title, desc = s.home_title, s.home_description
        canonical = settings.SITE_URL + "/"
        return dict(title=title or s.site_name, description=desc, robots="", canonical=canonical)

    if kind in ("product", "post", "page"):
        ctx["title"] = obj.title
        ctx["excerpt"] = plain(getattr(obj, "excerpt", "") or getattr(obj, "short_description", "") or obj.content, 155)
        if kind == "product":
            ctx["wc_brand"] = obj.brand.name if obj.brand_id else ""
            ctx["category"] = obj.primary_category.name if obj.primary_category_id else ""
            ctx["wc_shortdesc"] = plain(obj.short_description, 155)
        key = f"pt_{kind}"
    else:
        ctx["term"] = getattr(obj, "name", "") if obj else ""
        ctx["term_description"] = ctx["category_description"] = plain(getattr(obj, "description", ""), 155)
        key = f"tax_{kind}"

    title = render(obj.seo_title, ctx) if obj is not None and obj.seo_title else render(tpl.get(f"{key}_title"), ctx)
    if not title:
        title = render(f"%{'title' if 'title' in ctx else 'term'}% %page% %sep% %sitename%", ctx)
    if obj is not None and obj.seo_description:
        desc = render(obj.seo_description, ctx)
    elif kind == "product" and ctx.get("wc_shortdesc"):
        desc = ctx["wc_shortdesc"]  # رفتار فعلی سایت: توضیح کوتاه محصول
    else:
        desc = render(tpl.get(f"{key}_description"), ctx)
    if not desc or "%" in desc:
        desc = ctx.get("excerpt") or ctx.get("term_description") or ""
    canonical = (obj.canonical_url if obj is not None and obj.canonical_url else "") or (
        settings.SITE_URL + (path or obj.get_absolute_url()) + (f"page/{page}/" if page and page > 1 else "")
    )
    robots = obj.robots if obj is not None else ""
    return dict(title=title, description=plain(desc, 300), robots=robots, canonical=canonical)
