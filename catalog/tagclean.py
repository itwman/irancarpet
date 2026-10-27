"""دقیق‌کردن فرش‌های یک برچسب (مثل «فرش طرح افشان») تا صفحه‌اش واقعاً دربارهٔ همان موضوع باشد.

فرش‌هایی که کلمه («افشان») در عنوانشان هست می‌مانند. بقیه بر اساس نام نقشه دسته می‌شوند و مدیر تیک می‌زند
کدام نقشه‌ها هم افشان‌اند: آن‌ها می‌مانند و برایشان «قانون کلمهٔ عنوان» ساخته می‌شود تا فرش‌های بعدی همان نقشه
خودکار برچسب بخورند؛ بقیه از برچسب برداشته می‌شوند. فرش‌هایی که کلمه را دارند ولی برچسب ندارند هم برچسب می‌گیرند.
هر تغییر در «ابزار محتوا» برگرداندنی است.
"""
from .models import KeywordRule, Product

NOISE = {"فرش", "طرح", "نقشه", "ماشینی", "خرید"}


def default_word(tag_name):
    """«فرش طرح افشان» ← «افشان»"""
    words = [w for w in KeywordRule.norm(tag_name).split() if w not in NOISE]
    return " ".join(words) or KeywordRule.norm(tag_name)


def _tight(s):
    from content.finglish import tight

    return tight(s)


def analyze(tag, word):
    from content.render import design_of

    word = KeywordRule.norm(word)
    prods = list(tag.products.exclude(status="trash").select_related("image"))
    keep, groups = [], {}
    for p in prods:
        if KeywordRule.has(word, p.title):
            keep.append(p)
            continue
        label = (design_of(p) or "").strip()
        key = _tight(label) or "-"
        g = groups.setdefault(key, {"key": key, "label": label or "بدون نام نقشه", "named": bool(label), "products": []})
        g["products"].append(p)
    ruled = {_tight(r.keyword) for r in KeywordRule.objects.filter(tags=tag, is_active=True)}
    out = []
    for g in groups.values():
        ps = g.pop("products")
        g.update({"n": len(ps), "pub": sum(1 for p in ps if p.status == "publish"), "ids": [p.pk for p in ps],
                  "samples": [p.title for p in ps[:3]], "image": next((p.image for p in ps if p.image_id), None),
                  "ruled": g["key"] in ruled})
        out.append(g)
    out.sort(key=lambda g: (-g["n"], g["label"]))
    missing = []
    core = max(word.split(), key=len) if word else ""
    if core:
        tagged = set(tag.products.values_list("pk", flat=True))
        for pk, title in Product.objects.exclude(status="trash").filter(title__contains=core).values_list("pk", "title"):
            if pk not in tagged and KeywordRule.has(word, title):
                missing.append(pk)
    from pricing.models import Album

    albums = list(Album.objects.filter(default_tags=tag).values_list("name", flat=True))
    return {"word": word, "total": len(prods), "keep": len(keep), "groups": out, "missing": missing, "albums": albums}


def apply(tag, word, keep_keys, add_missing=True, drop_album_defaults=True, user=None):
    """خروجی: (خلاصه، ContentEdit یا None)"""
    from django.db import transaction

    from content.models import ContentEdit
    from pricing.models import Album

    data = analyze(tag, word)
    keep_keys = set(keep_keys)
    remove, rules, backup = [], [], []
    for g in data["groups"]:
        if g["key"] in keep_keys:
            if g["named"]:
                rules.append(g["label"])
        else:
            remove += g["ids"]
    add = data["missing"] if add_missing else []
    with transaction.atomic():
        if remove:
            tag.products.remove(*remove)
            backup += [{"id": pk, "field": "__tag", "tag": tag.pk, "op": "removed"} for pk in remove]
        if add:
            tag.products.add(*add)
            backup += [{"id": pk, "field": "__tag", "tag": tag.pk, "op": "added"} for pk in add]
        made = 0
        for kw in [data["word"]] + rules:
            rule = next((r for r in KeywordRule.objects.all() if KeywordRule.norm(r.keyword) == KeywordRule.norm(kw)), None)
            if rule is None:
                rule = KeywordRule.objects.create(keyword=kw[:80])
                made += 1
            rule.tags.add(tag)
        albums = 0
        if drop_album_defaults:
            for a in Album.objects.filter(default_tags=tag):
                a.default_tags.remove(tag)
                albums += 1
        edit = None
        summary = (f"برچسب «{tag.name}»: {len(remove)} فرش برداشته، {len(add)} فرش افزوده، "
                   f"{len(rules)} نقشه نگه داشته شد")
        if backup:
            edit = ContentEdit.objects.create(user=user, backup=backup, summary=summary[:300])
    return {"removed": len(remove), "added": len(add), "rules": rules, "new_rules": made, "albums": albums,
            "summary": summary}, edit


def undo_rows(rows):
    """برگرداندن ردیف‌های «__tag» یک ContentEdit."""
    from .models import ProductTag

    for row in rows:
        if row.get("field") != "__tag":
            continue
        tag = ProductTag.objects.filter(pk=row.get("tag")).first()
        if tag is None:
            continue
        if row.get("op") == "removed":
            tag.products.add(row["id"])
        elif row.get("op") == "added":
            tag.products.remove(row["id"])

