"""افزودن سریع کالای فروشنده با عکس: هر عکس (یا چند عکس یک فرش) یک کالا در آلبوم قیمت فروشنده.

نقشه و رنگ زمینه از نام فایل حدس زده می‌شود («افشان-لاکی.jpg»، «Afshan-Laki-2.jpg» عکس دوم همان فرش)؛
کالاها مثل کالای عادی فروشنده برای بررسی ایران کارپت می‌روند.
"""
import os
from collections import OrderedDict

from django.db import transaction

from catalog.models import AttributeTerm, Product, ProductImage

from . import products as P


def _terms(post):
    out = []
    for a in P.spec_attributes():
        t = P._int(post.get(f"spec_{a.pk}"))
        if t and AttributeTerm.objects.filter(pk=t, attribute=a).exists():
            out.append(t)
    return out


@transaction.atomic
def build(seller, album, category, prefix, files, post, meta=None):
    """meta (از اپ): برای هر عکس {"design", "color", "group"}؛ عکس‌های هم‌گروه یک کالا می‌شوند و نام فایل حدس زده نمی‌شود."""
    from content import finglish as F
    from content.views import color_attribute
    from pricing.albums import sync_album_variations

    color_attr = color_attribute()
    colors = list(AttributeTerm.objects.filter(attribute=color_attr).values_list("name", flat=True)) if color_attr else []
    designs = sorted(set(Product.objects.filter(seller=seller).exclude(design_name="").values_list("design_name", flat=True)))
    learned = F._learned()
    groups = OrderedDict()
    for i, f in enumerate(files):
        m = meta[i] if meta and i < len(meta) and isinstance(meta[i], dict) else None
        if m is not None:
            design = str(m.get("design") or "").strip()[:120]
            color = str(m.get("color") or "").strip()
            g = {"design": design, "color": color if color in colors else "", "n": i}
            key = f"m:{str(m.get('group') or '').strip() or i}"
        else:
            name = os.path.splitext(os.path.basename(f.name))[0]
            g = F.guess(name, designs, colors, learned)
            key = g["group"] or name
        groups.setdefault(key, {"g": g, "files": []})["files"].append((g["n"], f))
    common = _terms(post)
    created = []
    for key, item in groups.items():
        g = item["g"]
        design = g["design"] or ("" if key.startswith("m:") else key.replace("-", " ").replace("_", " "))
        title = (f"{prefix} نقشه {design}" if design else prefix) + (f" زمینه {g['color']}" if g["color"] else "")
        if not design and not g["color"] and len(groups) > 1:
            from core.templatetags.fa import fa_num

            title = f"{prefix} {fa_num(str(len(created) + 1))}"
        p = Product(seller=seller, status=Product.Status.DRAFT, kind=Product.Kind.VARIABLE, use_template=False, title=title[:300],
                    primary_category=category, album=album, design_name=design[:120], slug=P.unique_slug(title))
        p.save()
        p.categories.set([category])
        terms = list(common)
        if g["color"] and color_attr:
            t = AttributeTerm.objects.filter(attribute=color_attr, name=g["color"]).first()
            if t:
                terms.append(t.pk)
        p.specs.set(terms)
        for i, (_, f) in enumerate(sorted(item["files"], key=lambda x: x[0])[:P.MAX_IMAGES]):
            m = P.save_image(f)
            ProductImage.objects.create(product=p, media=m, order=i)
            if i == 0:
                Product.objects.filter(pk=p.pk).update(image_id=m.pk)
        sync_album_variations([p])
        P.submit(p)
        created.append(p)
    return created
