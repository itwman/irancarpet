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


def border_attribute():
    return Attribute.objects.filter(slug="border-color").first() or Attribute.objects.filter(label__contains="رنگ حاشیه").first()


def with_word(title, word):
    """«موکا» بعد از «… شانه» (یا بعد از «فرش» اگر شانه نبود)."""
    word = re.sub(r"\s+", " ", (word or "").strip())
    if not word or norm(word) in norm(title):
        return title
    if re.search(r"شانه", title):
        return re.sub(r"(شانه)", r"\1 " + word, title, count=1)
    return re.sub(r"^(فرش)", r"\1 " + word, title, count=1) if title.startswith("فرش") else f"{word} {title}"


def defaults_of(album):
    """{specs: [term], brand, categories, primary, tags, embossed, saved} — اول از آلبوم، وگرنه از یک فرش نمونهٔ آلبوم."""
    color = color_attribute()
    skip = {x.pk for x in (color, border_attribute()) if x}
    specs = list(album.default_specs.select_related("attribute"))
    saved = bool(specs or album.default_brand_id or album.default_categories.exists())
    if saved:
        return {"specs": [t for t in specs if t.attribute_id not in skip], "brand": album.default_brand,
                "categories": list(album.default_categories.all()), "primary": album.default_primary_category,
                "tags": list(album.default_tags.all()), "embossed": album.embossed, "saved": True}
    from .views import sample_of

    s = sample_of(album)
    if s is None:
        return {"specs": [], "brand": None, "categories": [], "primary": None, "tags": [], "embossed": album.embossed, "saved": False}
    return {"specs": [t for t in s.specs.select_related("attribute") if t.attribute_id not in skip],
            "brand": s.brand, "categories": list(s.categories.all()), "primary": s.primary_category,
            "tags": list(s.tags.all()), "embossed": album.embossed or "برجسته" in (s.title or ""), "saved": False}


def material_of_terms(terms):
    return material_of(t.name for t in terms if "جنس" in (t.attribute.label or ""))


def _spec(terms, *keys):
    for t in terms:
        if any(k in (t.attribute.label or "").replace("‌", " ") for k in keys):
            return t.name
    return ""


def title_template(album, terms, brand, embossed, word=None):
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
    t = with_word(t, album.title_word if word is None else word)
    if material_of_terms(terms) == "polyester" and "پلی استر" not in t:
        t += POLY_SUFFIX
    return t


def is_code(design):
    """نقشه‌ای که فقط عدد است (مثل 5006) کد نقشه است: «کد 5006» به‌جای «نقشه 5006»."""
    d = (design or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    return d.isdigit()


def make(template, design, color, border=""):
    if is_code(design):
        template = template.replace("نقشه " + D, "کد " + D).replace("نقشهٔ " + D, "کد " + D)
        design = fa_num(design.strip())
    color = color.strip()
    if border and norm(border) != norm(color):  # «زمینه کرم حاشیه سرمه ای»؛ حاشیهٔ هم‌رنگ در عنوان نمی‌آید
        color = f"{color} حاشیه {border.strip()}"
    t = template.replace(D, design.strip()).replace(C, color)
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
        "title_word": album.title_word,
        "borders": _border_names(),
        "material": material_of_terms(d["specs"]),
        "designs": designs,
        "colors": list(AttributeTerm.objects.filter(attribute=color).order_by("name").values_list("name", flat=True)) if color else [],
        "count": Product.objects.filter(album=album).count(),
    }


def _border_names():
    b = border_attribute()
    names = set(AttributeTerm.objects.filter(attribute=b).values_list("name", flat=True)) if b else set()
    return sorted(names)


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
    skip = {x.pk for x in (color_attr, border_attribute()) if x}
    terms = [t for t in _terms_from(data.get("specs") or {}) if t.attribute_id not in skip]
    brand = Brand.objects.filter(pk=data.get("brand") or 0).first() if str(data.get("brand") or "").isdigit() else None
    brand = brand_for(terms) or brand
    cats = list(Category.objects.filter(pk__in=[int(x) for x in data.get("categories") or [] if str(x).isdigit()]))
    primary = Category.objects.filter(pk=data.get("primary") or 0).first() if str(data.get("primary") or "").isdigit() else None
    tags = list(ProductTag.objects.filter(pk__in=[int(x) for x in data.get("tags") or [] if str(x).isdigit()]))
    embossed = bool(data.get("embossed"))
    word = re.sub(r"\s+", " ", str(data.get("title_word") or "").strip())[:40]
    if data.get("save_defaults"):
        album.title_word = word
        album.default_specs.set(terms)
        album.default_categories.set(cats)
        album.default_tags.set(tags)
        album.default_brand, album.default_primary_category, album.embossed = brand, primary, embossed
        album.save(update_fields=["default_brand", "default_primary_category", "embossed", "title_word"])
    template = title_template(album, terms, brand, embossed, word)
    border_attr = border_attribute()
    publish = data.get("status") == "publish"
    warnings, created, learn_rows = [], [], []
    existing = {norm(t) for t in Product.objects.values_list("title", flat=True)}
    dups = DupCheck(album)
    with transaction.atomic():
        for i, row in enumerate(data.get("rows") or []):
            design = re.sub(r"\s+", " ", str(row.get("design") or "").strip())[:120]
            color = re.sub(r"\s+", " ", str(row.get("color") or "").strip())[:120]
            if not design or not color:
                warnings.append(f"ردیف {fa_num(i + 1)}: نقشه و رنگ زمینه لازم است؛ ساخته نشد.")
                continue
            border = re.sub(r"\s+", " ", str(row.get("border") or "").strip())[:120]
            title = (str(row.get("title") or "").strip() or make(template, design, color, border))[:300]
            if norm(title) in existing:
                warnings.append(f"«{title}» از قبل هست؛ دوباره ساخته نشد. اگر فرش دیگری است، عنوانش را عوض کنید.")
                continue
            dup = dups.check(design, color, border, n=i + 1)
            if dup["level"] == "dup" and not row.get("force"):
                where = f"ردیف {fa_num(dup['row'])} همین فهرست" if dup["row"] else "«" + dup["items"][0]["title"] + "»"
                warnings.append(f"«{title}» ساخته نشد؛ همین نقشه و رنگ در {where} هست. اگر فرش دیگری است، «با این حال بساز» را بزنید.")
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
            border_term = term_named(border_attr, border) if border_attr and border else None
            p.specs.set(terms + [t for t in (color_term, border_term) if t])
            p.categories.set(list(row_cats.values()))
            p.tags.set(list(row_tags.values()))
            ProductImage.objects.bulk_create([ProductImage(product=p, media_id=m, order=k) for k, m in enumerate(images)])
            Media.objects.filter(pk__in=images, alt="").update(alt=title[:500])
            created.append(p)
            learn_rows.append({"dl": row.get("dl"), "cl": row.get("cl"), "bl": row.get("bl"), "design": design, "color": color,
                               "border": border})
        if created:
            from .finglish import learn

            learn(learn_rows)
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


# ------------------------------------------------------------------ فرش تکراری
_CODE = re.compile(r"کد\s+([0-9۰-۹]+)")


class DupCheck:
    """پیش از ساختن: آیا این نقشه و رنگ در همین آلبوم (یا در فرش‌های بی‌آلبومی که به این آلبوم می‌خورند) هست؟

    تکراری (dup): همان نقشه با همان رنگ زمینه و حاشیه (رنگ‌های هم‌معنی تنظیمات یکی حساب می‌شوند)، یا همان عنوان در سایت،
    یا دو ردیف یکسان در همین فهرست. هم‌نقشه (same): این نقشه با رنگ‌های دیگر هست؛ فقط برای اطلاع.
    مقایسهٔ نقشه بدون فاصله و نیم‌فاصله است («کرشمه طلا کوب» = «کرشمه طلاکوب»).
    """

    def __init__(self, album):
        from . import render as R
        from .finglish import ColorCanon, tight

        self.tight, self.canon = tight, ColorCanon()
        self.items, self.batch = [], {}
        qs = list(Product.objects.filter(album=album).exclude(status="trash").prefetch_related("specs__attribute"))
        brands = {p.brand_id for p in qs if p.brand_id}
        if brands:  # فرش‌های قدیمی (وردپرس) که هنوز آلبوم ندارند ولی به همین آلبوم می‌خورند
            from pricing.suggest import missing_q, suggest_ids

            orphans = list(Product.objects.filter(missing_q("none"), brand_id__in=brands).exclude(status="trash")
                           .select_related("album").prefetch_related("specs__attribute"))
            hit = suggest_ids(orphans)
            qs += [p for p in orphans if hit.get(p.pk) == album.pk]
        for p in qs:
            d = R.design_of(p)
            if not d:
                m = _CODE.search(p.title or "")
                d = m.group(1) if m else ""
            c, b = R.color_of(p), R.border_of(p)
            self.items.append({"id": p.pk, "title": fa_num(p.title), "d": tight(d), "key": self._key(c, b),
                               "label": self._label(c, b), "status": p.status, "orphan": not p.album_id,
                               "url": f"/panel/products/{p.pk}/edit/", "view": p.get_absolute_url()})
        self.titles = {}
        for pk, t in Product.objects.exclude(status="trash").values_list("pk", "title"):
            self.titles.setdefault(norm(t), pk)
        self.by_id = {it["id"]: it for it in self.items}

    def _key(self, color, border):
        c = self.canon(color)
        return c, (self.canon(border) if border else c)  # حاشیهٔ خالی یعنی هم‌رنگ زمینه

    @staticmethod
    def _label(color, border):
        if border and norm(border) != norm(color):
            return f"{color} حاشیه {border}"
        return color

    def _brief(self, it):
        return {k: it[k] for k in ("id", "title", "label", "status", "orphan", "url", "view")}

    def check(self, design, color, border="", title="", n=None):
        """{level: dup|same|'', items: [فرش‌های تکراری], colors: [رنگ‌های دیگرِ همین نقشه], row: ردیف تکراری همین فهرست}"""
        d, k = self.tight(design), self._key(color, border)
        out = {"level": "", "items": [], "colors": [], "row": None}
        if not d:
            return out
        same = [it for it in self.items if it["d"] == d]
        dup = [it for it in same if it["key"] == k]
        pk = self.titles.get(norm(title)) if title else None
        if pk and pk not in {it["id"] for it in dup}:
            it = self.by_id.get(pk)
            if it is None:
                p = Product.objects.filter(pk=pk).first()
                it = {"id": pk, "title": fa_num(p.title), "label": "", "status": p.status, "orphan": not p.album_id,
                      "url": f"/panel/products/{pk}/edit/", "view": p.get_absolute_url()}
            dup.append(it)
        if (d, k) in self.batch:
            out["row"] = self.batch[(d, k)]
        elif n is not None:
            self.batch[(d, k)] = n
        if dup or out["row"]:
            out["level"] = "dup"
        elif same:
            out["level"] = "same"
        out["items"] = [self._brief(it) for it in dup]
        seen, colors = set(), []
        for it in same:
            if it["key"] != k and it["label"] and it["key"] not in seen:
                seen.add(it["key"])
                colors.append(it["label"])
        out["colors"] = colors
        return out
