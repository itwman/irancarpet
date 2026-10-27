"""ویرایش گروهی فرش‌ها (مثل ووکامرس، ولی با پیش‌نمایش و برگرداندن): دسته‌ها، برچسب‌ها، دستهٔ اصلی و کلمهٔ عنوان.

- برای هر دسته/برچسبی که در فرش‌های انتخاب‌شده هست: «به همه» یا «از همه بردار»؛ دسته/برچسب تازه هم افزوده می‌شود.
- اگر دستهٔ اصلی فرشی برداشته شود، دستهٔ دیگرش جایش را می‌گیرد (مسیر صفحه خراب نمی‌شود).
- دسته‌ای با «خودکار برای فرشستان» فرش را برای فرشستان هم انتخاب می‌کند (مثل افزودن تکی).
- کلمهٔ عنوان (مثل «موکا») بعد از «… شانه» می‌آید و قانون‌های کلمهٔ عنوان دوباره روی همان فرش‌ها اعمال می‌شوند.
- اگر فرش‌های انتخاب‌شده کلمهٔ مشترکِ کمیابی در عنوان دارند، ساخت قانون پیشنهاد می‌شود تا فرش‌های بعدی خودکار بگیرند.
- همه‌چیز در «ابزار محتوا» برگرداندنی است.
"""
import re
from collections import Counter

from django.db import transaction
from django.utils import timezone

from .models import Category, KeywordRule, Product, ProductTag

REL = {"categories": Category, "tags": ProductTag}
STOP = {"فرش", "شانه", "نقشه", "زمینه", "حاشیه", "گل", "برجسته", "پلی", "استر", "کد", "طرح", "ماشینی", "سایز", "متری", "و", "با",
        "تراکم", "اکریلیک", "آکریلیک", "کناره", "گرد", "بیضی", "سجاده", "ای"}


def _words(title):
    return set(KeywordRule.norm(title).split())


def common_words(ids, limit=2):
    """کلمه‌هایی که در عنوان بیشترِ فرش‌های انتخاب‌شده هست ولی در کل فروشگاه کمیاب است (مثل «موکا»، «وینتیج»)."""
    from content.finglish import fa_colors, tight

    titles = list(Product.objects.filter(pk__in=ids).values_list("title", flat=True))
    if len(titles) < 2:
        return []
    mine = Counter(w for t in titles for w in _words(t))
    colors = {tight(c) for c in fa_colors()}
    total = Product.objects.exclude(status="trash").count() or 1
    out = []
    for w, n in mine.most_common(30):
        if n < 0.8 * len(titles) or w in STOP or w.isdigit() or re.fullmatch(r"[0-9۰-۹]+", w) or tight(w) in colors or len(w) < 3:
            continue
        everywhere = Product.objects.exclude(status="trash").filter(title__contains=w).count()
        if everywhere > 0.4 * total:
            continue
        out.append(w)
        if len(out) >= limit:
            break
    return out


def analyze(ids):
    """وضعیت فعلی: هر دسته/برچسب در چند فرش از انتخاب‌شده‌ها هست."""
    n = len(ids)
    rows = {}
    for rel, model in REL.items():
        through = getattr(Product, rel).through
        fk = "category_id" if rel == "categories" else "producttag_id"
        cnt = Counter(through.objects.filter(product_id__in=ids).values_list(fk, flat=True))
        objs = {o.pk: o for o in model.objects.filter(pk__in=list(cnt))}
        rows[rel] = sorted(({"obj": objs[k], "n": v, "all": v == n} for k, v in cnt.items() if k in objs),
                           key=lambda r: (-r["n"], r["obj"].name))
    primary = Counter(Product.objects.filter(pk__in=ids).values_list("primary_category_id", flat=True))
    sample = list(Product.objects.filter(pk__in=ids).values_list("title", flat=True)[:5])
    return {"n": n, "cats": rows["categories"], "tags": rows["tags"], "primary": primary, "sample": sample,
            "words": common_words(ids)}


def _ids_of(model, values):
    """شناسه‌ها؛ نام تازه (از جستجوی پنل) ساخته می‌شود."""
    from dashboard.ac import unique_slug

    out = []
    for v in values:
        v = str(v).strip()
        if not v:
            continue
        if v.isdigit() and model.objects.filter(pk=int(v)).exists():
            out.append(int(v))
            continue
        obj = model.objects.filter(name__iexact=v).first() or model.objects.create(name=v[:255], slug=unique_slug(model, v))
        out.append(obj.pk)
    return list(dict.fromkeys(out))


def apply(ids, ops, user=None):
    """ops: {categories: {add: [...], remove: [...]}, tags: {...}, primary: id|None, word: str, rule: str}
    خروجی: (پیام‌ها، ContentEdit یا None)"""
    from content.models import ContentEdit
    from content.quick import with_word

    ids = list(dict.fromkeys(int(i) for i in ids))
    backup, msgs, now = [], [], timezone.now()
    added_by_rel = {}
    with transaction.atomic():
        for rel, model in REL.items():
            through = getattr(Product, rel).through
            fk = "category_id" if rel == "categories" else "producttag_id"
            add = _ids_of(model, (ops.get(rel) or {}).get("add") or [])
            remove = [int(x) for x in (ops.get(rel) or {}).get("remove") or [] if str(x).isdigit() and int(x) not in add]
            added_by_rel[rel] = add
            if add:
                have = set(through.objects.filter(product_id__in=ids, **{f"{fk}__in": add}).values_list("product_id", fk))
                new = [(p, o) for p in ids for o in add if (p, o) not in have]
                through.objects.bulk_create([through(product_id=p, **{fk: o}) for p, o in new], ignore_conflicts=True)
                backup += [{"field": "__m2m", "rel": rel, "id": p, "obj": o, "op": "added"} for p, o in new]
                names = "، ".join(model.objects.filter(pk__in=add).values_list("name", flat=True))
                msgs.append(f"«{names}» به {len({p for p, _ in new})} فرش افزوده شد.")
            if remove:
                gone = list(through.objects.filter(product_id__in=ids, **{f"{fk}__in": remove}).values_list("product_id", fk))
                through.objects.filter(product_id__in=ids, **{f"{fk}__in": remove}).delete()
                backup += [{"field": "__m2m", "rel": rel, "id": p, "obj": o, "op": "removed"} for p, o in gone]
                names = "، ".join(model.objects.filter(pk__in=remove).values_list("name", flat=True))
                msgs.append(f"«{names}» از {len({p for p, _ in gone})} فرش برداشته شد.")
        # دستهٔ اصلی: انتخاب‌شده، یا اگر برداشته شد، دستهٔ دیگر همان فرش
        primary = ops.get("primary")
        removed_cats = set(int(x) for x in (ops.get("categories") or {}).get("remove") or [] if str(x).isdigit())
        for p in Product.objects.filter(pk__in=ids).only("pk", "primary_category_id"):
            new = p.primary_category_id
            if primary:
                new = int(primary)
                if not Category.objects.filter(pk=new, products=p.pk).exists():
                    Product.categories.through.objects.get_or_create(product_id=p.pk, category_id=new)
                    backup.append({"field": "__m2m", "rel": "categories", "id": p.pk, "obj": new, "op": "added"})
            elif new in removed_cats:
                new = (Category.objects.filter(products=p.pk).exclude(pk__in=removed_cats).order_by("order", "pk")
                       .values_list("pk", flat=True).first())
            if new != p.primary_category_id:
                backup.append({"field": "primary_category_id", "id": p.pk, "old": p.primary_category_id})
                Product.objects.filter(pk=p.pk).update(primary_category_id=new)
        # کلمهٔ عنوان + قانون‌های کلمه
        word = re.sub(r"\s+", " ", (ops.get("word") or "").strip())[:40]
        if word:
            changed = 0
            for p in Product.objects.filter(pk__in=ids).only("pk", "title"):
                if KeywordRule.has(word, p.title):
                    continue
                t = with_word(p.title, word)[:300]
                if t == p.title:
                    continue
                backup.append({"field": "title", "id": p.pk, "old": p.title})
                Product.objects.filter(pk=p.pk).update(title=t)
                changed += 1
                for r in KeywordRule.matches(t):
                    for c in r.categories.all():
                        _, made = Product.categories.through.objects.get_or_create(product_id=p.pk, category_id=c.pk)
                        if made:
                            backup.append({"field": "__m2m", "rel": "categories", "id": p.pk, "obj": c.pk, "op": "added"})
                            added_by_rel.setdefault("categories", []).append(c.pk)
                    for tg in r.tags.all():
                        _, made = Product.tags.through.objects.get_or_create(product_id=p.pk, producttag_id=tg.pk)
                        if made:
                            backup.append({"field": "__m2m", "rel": "tags", "id": p.pk, "obj": tg.pk, "op": "added"})
            if changed:
                msgs.append(f"«{word}» به عنوان {changed} فرش افزوده شد (نشانی صفحه‌ها عوض نشد).")
        # قانون کلمه برای فرش‌های بعدی
        rule_word = (ops.get("rule") or "").strip()
        if rule_word and (ops.get("categories", {}).get("add") or ops.get("tags", {}).get("add")):
            rule = next((r for r in KeywordRule.objects.all() if KeywordRule.norm(r.keyword) == KeywordRule.norm(rule_word)), None)
            rule = rule or KeywordRule.objects.create(keyword=rule_word[:80])
            rule.categories.add(*_ids_of(Category, ops["categories"].get("add") or []))
            rule.tags.add(*_ids_of(ProductTag, ops["tags"].get("add") or []))
            msgs.append(f"قانون «{rule_word}» ساخته شد؛ فرش‌های بعدی با این کلمه خودکار همین‌ها را می‌گیرند.")
        Product.objects.filter(pk__in=ids).update(modified_at=now)
        # «خودکار برای فرشستان»
        auto = Category.objects.filter(pk__in=added_by_rel.get("categories") or [], mirror_auto=True)
        if auto.exists():
            try:
                from mirror.auto import pick

                n = pick(ids)
                if n:
                    msgs.append(f"{n} فرش برای فرشستان هم انتخاب شد.")
            except Exception:  # noqa: BLE001
                pass
        edit = None
        if backup:
            edit = ContentEdit.objects.create(user=user, backup=backup,
                                              summary=f"ویرایش گروهی {len(ids)} فرش: " + " ".join(msgs)[:250])
    return msgs, edit


def undo_rows(rows):
    """برگرداندن ردیف‌های ویرایش گروهی (دسته/برچسب، دستهٔ اصلی، عنوان)."""
    for row in rows:
        f = row.get("field")
        if f == "__m2m" and row.get("rel") in REL:
            through = getattr(Product, row["rel"]).through
            fk = "category_id" if row["rel"] == "categories" else "producttag_id"
            if row.get("op") == "added":
                through.objects.filter(product_id=row["id"], **{fk: row["obj"]}).delete()
            elif row.get("op") == "removed":
                through.objects.get_or_create(product_id=row["id"], **{fk: row["obj"]})
        elif f == "primary_category_id":
            Product.objects.filter(pk=row["id"]).update(primary_category_id=row.get("old"))
        elif f == "title":
            Product.objects.filter(pk=row["id"]).update(title=row.get("old") or "")
