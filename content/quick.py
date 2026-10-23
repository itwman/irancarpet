"""افزودن سریع فرش‌های یک آلبوم: پیش‌فرض‌های آلبوم + برای هر فرش فقط نقشه، رنگ زمینه و عکس.

پیش‌فرض‌ها (مشخصات، برند، دسته‌ها، برچسب‌ها، برجسته) روی خود آلبوم ذخیره می‌شوند؛ اگر آلبوم هنوز پیش‌فرض
ندارد، از یک فرش موجود همان آلبوم برداشته می‌شوند. عنوان از قالب متن آلبوم ساخته می‌شود و فرش پلی‌استر
« - پلی استر» در آخر عنوانش می‌گیرد (آکریلیک نامی در عنوان ندارد، ولی در مشخصات و متن هست).
"""
import re

from django.db import transaction
from django.utils import timezone

from catalog.models import (Attribute, AttributeTerm, Brand, Category, KeywordRule, Product, ProductImage, ProductTag,
                            material_of)
from core.models import Media
from core.templatetags.fa import fa_num
from dashboard.ac import unique_slug

D, C = "⁣D⁣", "⁣C⁣"  # جای نقشه و رنگ در الگوی عنوان (برای پیش‌نمایش زندهٔ عنوان در مرورگر)
POLY_SUFFIX = " - پلی استر"


def color_attribute():
    from .views import color_attribute as ca

    return ca()


def defaults_of(album):
    """{specs: [term], brand, categories, primary, tags, embossed, saved} — اول از آلبوم، وگرنه از یک فرش نمونهٔ آلبوم."""
    color = color_attribute()
    specs = list(album.default_specs.select_related("attribute"))
    saved = bool(specs or album.default_brand_id or album.default_categories.exists())
    if saved:
        return {"specs": [t for t in specs if not color or t.attribute_id != color.pk], "brand": album.default_brand,
                "categories": list(album.default_categories.all()), "primary": album.default_primary_category,
                "tags": list(album.default_tags.all()), "embossed": album.embossed, "saved": True}
    from .views import sample_of

    s = sample_of(album)
    if s is None:
        return {"specs": [], "brand": None, "categories": [], "primary": None, "tags": [], "embossed": album.embossed, "saved": False}
    return {"specs": [t for t in s.specs.select_related("attribute") if not color or t.attribute_id != color.pk],
            "brand": s.brand, "categories": list(s.categories.all()), "primary": s.primary_category,
            "tags": list(s.tags.all()), "embossed": album.embossed or "برجسته" in (s.title or ""), "saved": False}


def material_of_terms(terms):
    return material_of(t.name for t in terms if "جنس" in (t.attribute.label or ""))


def _spec(terms, *keys):
    for t in terms:
        if any(k in (t.attribute.label or "").replace("‌", " ") for k in keys):
            return t.name
    return ""


def title_template(album, terms, brand, embossed):
    """الگوی عنوان با جای خالی نقشه و رنگ؛ پلی‌استر « - پلی استر» در آخر."""
    from .views import make_title, template_for_album

    tpl = template_for_album(album.pk)
    t = make_title(tpl.title_pattern if tpl else "", {
        "شانه": fa_num(_spec(terms, "شانه")), "تراکم": fa_num(_spec(terms, "تراکم")),
        "برجسته": "گل برجسته" if embossed else "", "برند": brand.name if brand else (_spec(terms, "برند") or album.company),
        "نقشه": D, "رنگ": C,
    })
    t = re.sub(r"\s+", " ", t).strip()
    if D not in t or C not in t:  # الگو به خاطر خالی بودن شانه یا… خالی شد: الگوی ساده
        reeds = fa_num(_spec(terms, "شانه"))
        t = "فرش" + (f" {reeds} شانه" if reeds else "") + (" گل برجسته" if embossed else "") + f" نقشه {D} زمینه {C}"
    if material_of_terms(terms) == "polyester" and "پلی استر" not in t:
        t += POLY_SUFFIX
    return t


def make(template, design, color):
    t = template.replace(D, design.strip()).replace(C, color.strip())
    return re.sub(r"\s+", " ", t).strip()


def norm(s):
    return " ".join((s or "").replace("‌", " ").replace("ي", "ی").replace("ك", "ک").split())


def album_payload(album):
    """داده‌های صفحهٔ افزودن سریع برای یک آلبوم (JSON)."""
    d = defaults_of(album)
    color = color_attribute()
    designs = sorted({x for x in Product.objects.filter(album=album).exclude(design_name="").values_list("design_name", flat=True)})
    by_attr = {}
    for t in d["specs"]:
        by_attr.setdefault(t.attribute_id, []).append({"value": str(t.pk), "text": t.name})
    return {
        "album": {"id": album.pk, "name": album.name, "company": album.company},
        "saved": d["saved"], "embossed": d["embossed"],
        "specs": by_attr,
        "brand": {"value": str(d["brand"].pk), "text": d["brand"].name} if d["brand"] else None,
        "categories": [c.pk for c in d["categories"]], "primary": d["primary"].pk if d["primary"] else None,
        "tags": [{"value": str(t.pk), "text": t.name} for t in d["tags"]],
        "template": title_template(album, d["specs"], d["brand"], d["embossed"]),
        "material": material_of_terms(d["specs"]),
        "designs": designs,
        "colors": list(AttributeTerm.objects.filter(attribute=color).order_by("name").values_list("name", flat=True)) if color else [],
        "count": Product.objects.filter(album=album).count(),
    }


def rules_payload():
    return [{"k": norm(r.keyword), "cats": [c.pk for c in r.categories.all()], "names": [c.name for c in r.categories.all()],
             "tags": [{"value": str(t.pk), "text": t.name} for t in r.tags.all()]}
            for r in KeywordRule.objects.filter(is_active=True).prefetch_related("categories", "tags")]


def _terms_from(post_specs):
    """{attr_id: [شناسه یا نام تازه]} ← مقدارها (نام تازه ساخته می‌شود)."""
    out = []
    for attr_id, values in post_specs.items():
        attr = Attribute.objects.filter(pk=attr_id).first()
        if attr is None:
            continue
        for v in values:
            v = str(v).strip()
            if v.isdigit():
                t = AttributeTerm.objects.filter(pk=int(v), attribute=attr).first()
            else:
                t = term_named(attr, v)
            if t:
                out.append(t)
    return out


def term_named(attr, name):
    name = re.sub(r"\s+", " ", (name or "").strip())[:255]
    if not name:
        return None
    for t in AttributeTerm.objects.filter(attribute=attr):
        if norm(t.name) == norm(name):
            return t
    return AttributeTerm.objects.create(attribute=attr, name=name, slug=unique_slug(AttributeTerm, name))


def create(album, data, request=None):
    """data: {specs:{attr:[...]}, brand, categories:[], primary, tags:[], embossed, save_defaults, status, rows:[{design, color, images}]}
    خروجی: (فرش‌های ساخته‌شده، هشدارها)"""
    color_attr = color_attribute()
    terms = [t for t in _terms_from(data.get("specs") or {}) if not color_attr or t.attribute_id != color_attr.pk]
    brand = Brand.objects.filter(pk=data.get("brand") or 0).first() if str(data.get("brand") or "").isdigit() else None
    brand = brand_for(terms) or brand
    cats = list(Category.objects.filter(pk__in=[int(x) for x in data.get("categories") or [] if str(x).isdigit()]))
    primary = Category.objects.filter(pk=data.get("primary") or 0).first() if str(data.get("primary") or "").isdigit() else None
    tags = list(ProductTag.objects.filter(pk__in=[int(x) for x in data.get("tags") or [] if str(x).isdigit()]))
    embossed = bool(data.get("embossed"))
    if data.get("save_defaults"):
        album.default_specs.set(terms)
        album.default_categories.set(cats)
        album.default_tags.set(tags)
        album.default_brand, album.default_primary_category, album.embossed = brand, primary, embossed
        album.save(update_fields=["default_brand", "default_primary_category", "embossed"])
    template = title_template(album, terms, brand, embossed)
    publish = data.get("status") == "publish"
    warnings, created = [], []
    existing = {norm(t) for t in Product.objects.values_list("title", flat=True)}
    with transaction.atomic():
        for i, row in enumerate(data.get("rows") or []):
            design = re.sub(r"\s+", " ", str(row.get("design") or "").strip())[:120]
            color = re.sub(r"\s+", " ", str(row.get("color") or "").strip())[:120]
            if not design or not color:
                warnings.append(f"ردیف {fa_num(i + 1)}: نقشه و رنگ زمینه لازم است؛ ساخته نشد.")
                continue
            title = (str(row.get("title") or "").strip() or make(template, design, color))[:300]
            if norm(title) in existing:
                warnings.append(f"«{title}» از قبل هست؛ دوباره ساخته نشد.")
                continue
            existing.add(norm(title))
            color_term = term_named(color_attr, color) if color_attr else None
            images = [int(x) for x in row.get("images") or [] if str(x).isdigit()]
            images = [m for m in images if Media.objects.filter(pk=m).exists()]
            rules = KeywordRule.matches(title)
            row_cats = {c.pk: c for c in cats}
            row_tags = {t.pk: t for t in tags}
            for r in rules:
                row_cats.update({c.pk: c for c in r.categories.all()})
                row_tags.update({t.pk: t for t in r.tags.all()})
            p = Product(title=title, slug=unique_slug(Product, title), album=album, status="publish" if publish else "draft",
                        use_template=True, design_name=design, brand=brand,
                        primary_category=primary or (next(iter(row_cats.values())) if row_cats else None),
                        image_id=images[0] if images else None, published_at=timezone.now(), modified_at=timezone.now())
            p.save()
            p.specs.set(terms + ([color_term] if color_term else []))
            p.categories.set(list(row_cats.values()))
            p.tags.set(list(row_tags.values()))
            ProductImage.objects.bulk_create([ProductImage(product=p, media_id=m, order=k) for k, m in enumerate(images)])
            Media.objects.filter(pk__in=images, alt="").update(alt=title[:500])
            created.append(p)
        if created:
            from pricing.albums import sync_album_variations

            sync_album_variations(list(Product.objects.filter(pk__in=[p.pk for p in created]).select_related("album")))
            for p in Product.objects.filter(pk__in=[p.pk for p in created]).select_related("album"):
                p.refresh_price_cache()
    return created, warnings


def brand_for(terms):
    """برند فرش (فیلد برند) از مقدار ویژگی «برند»؛ اگر نبود ساخته می‌شود — تا دو جای برند با هم یکی بمانند."""
    name = _spec(terms, "برند")
    if not name:
        return None
    for b in Brand.objects.all():
        if norm(b.name) == norm(name):
            return b
    return Brand.objects.create(name=name[:255], slug=unique_slug(Brand, name))


def sync_brand(product):
    """ویژگی «برند» منبع اصلی است؛ فیلد برند (برای صفحهٔ برند و فیلتر) هم‌نام آن می‌شود."""
    b = brand_for(list(product.specs.select_related("attribute")))
    if b and b.pk != product.brand_id:
        Product.objects.filter(pk=product.pk).update(brand=b)
        product.brand = b


def missing_required(product):
    """نام مشخصات لازمی که این فرش ندارد (برای هشدار در فرم محصول)."""
    have = {t.attribute_id for t in product.specs.all()}
    out = []
    for a in Attribute.objects.filter(required=True).order_by("order"):
        if a.pk in have or ("برند" in a.label and product.brand_id):
            continue
        out.append(a.label)
    return out
