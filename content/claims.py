"""پیدا کردن و اصلاح ادعاهای ثابت‌نشده («اولین/نخستین فروشگاه»، «از ۱۳۸۷»، «۱۸ سال سابقه») و نشانی ناهمسان.

ادعای بی‌سند باعث می‌شود موتورهای جستجو و دستیارهای هوش مصنوعی به کل متن سایت کمتر اعتماد کنند.
سابقهٔ مستند: سایت از اردیبهشت ۱۳۸۹، فروشگاه اینترنتی از اسفند ۱۳۹۱ (آرشیو اینترنت).

scan() ← فهرست جمله‌ها با پیشنهاد؛ apply() ← جایگزینی جمله‌های تأییدشده با پشتیبان در «ابزار محتوا».
"""
import re

from django.apps import apps
from django.db import models, transaction
from django.db.models import Q

ADDRESS = "کاشان، میدان زجاجی، بلوار شهید پکوک"

# (مدل، فیلدها)؛ تنظیمات تک‌ردیفی هم مثل بقیه
TARGETS = [
    ("core.SiteSettings", ["tagline", "home_title", "home_description", "home_about", "footer_html", "feature_text",
                           "store_name", "store_hours_note"]),
    ("seo.SeoSettings", ["llms_about"]),
    ("blog.Page", ["title", "content", "seo_title", "seo_description"]),
    ("blog.Post", ["title", "content", "excerpt", "seo_title", "seo_description"]),
    ("catalog.Product", ["title", "content", "short_description", "seo_title", "seo_description"]),
    ("catalog.Category", ["description", "seo_title", "seo_description", "collection_note"]),
    ("catalog.ProductTag", ["description", "seo_title", "seo_description"]),
]
LABELS = {"core.SiteSettings": "تنظیمات سایت", "seo.SeoSettings": "تنظیمات سئو", "blog.Page": "برگه", "blog.Post": "مقاله",
          "catalog.Product": "فرش", "catalog.Category": "دسته", "catalog.ProductTag": "برچسب"}
FIELD_LABELS = {"home_about": "دربارهٔ ایران کارپت", "llms_about": "معرفی برای هوش مصنوعی (llms.txt)", "trust_points": "امتیازهای فروشگاه",
                "tagline": "شعار", "home_description": "توضیح صفحهٔ اول", "footer_html": "HTML فوتر", "content": "متن",
                "short_description": "توضیح کوتاه", "description": "توضیح", "excerpt": "خلاصه", "title": "عنوان",
                "seo_title": "عنوان سئو", "seo_description": "توضیح سئو", "address": "آدرس", "feature_text": "متن دستهٔ ویژه"}

NEEDLES = ["اولین فروشگاه", "نخستین فروشگاه", "1387", "۱۳۸۷", "۱۸ سال", "18 سال"]
FIND = re.compile(r"(?:اولین|نخستین)\s+فروشگاه|1387|۱۳۸۷|(?:۱۸|18)\s+سال")
ADDR_FIND = re.compile(r"زجاجی|پکوک")

RULES = [
    (re.compile(r"(ایران\s?کارپت[^؟!<>\n]*?)\s+(?:نخستین|اولین)\s+فروشگاه\s+(?:آنلاین|اینترنتی)\s+فرش\s+ماشینی(?:\s+در\s+ایران)?"
                r"\s+است\s+که\s+از\s+(?:سال\s+)?(?:1387|۱۳۸۷)\s+(?:فعالیت\s+)?(?:می‌?\s?کند|فعال\s+است)"),
     r"\1 از ۱۳۸۹ در فضای آنلاین فعال است و فروشگاه اینترنتی آن از ۱۳۹۱ کار می‌کند"),
    (re.compile(r"(?:اولین|نخستین)\s+فروشگاه\s+(?:آنلاین|اینترنتی)\s+فرش(?:\s+ماشینی)?(?:\s+(?:در\s+)?ایران)?"),
     "از قدیمی‌ترین فروشگاه‌های آنلاین فرش ماشینی"),
    (re.compile(r"(?:با\s+)?(?:بیش\s+از\s+)?(?:۱۸|18)\s+سال\s+(?:سابقه|تجربه|فعالیت)"), "فروش آنلاین از ۱۳۹۱"),
    (re.compile(r"از\s+(?:سال\s+)?(?:1387|۱۳۸۷)"), "از ۱۳۸۹"),
]
ADDR_RULE = re.compile(r"(?:کاشان[،,\s\-]*)?(?:میدان|م\.)\s*زجاجی(?:[،,\s\-]*(?:بلوار|بلوار\s+شهید|خیابان)?\s*(?:شهید\s+)?پکوک)?")


def suggest(text):
    out = text
    for rx, rep in RULES:
        out = rx.sub(rep, out)
    return re.sub(r"\s{2,}", " ", out)


BOUND = re.compile(r"[!؟?\n<>]|\.(?=\s|$|<)")


def _snippets(text, rx):
    """جمله‌هایی (بخش‌های متنی بین تگ‌ها و پایان جمله‌ها) که الگو در آن‌ها هست؛ بدون تکرار. نقطهٔ وسط کلمه (irancarpet.net) مرز نیست."""
    text = text or ""
    bounds = [m.start() for m in BOUND.finditer(text)]
    seen = []
    for m in rx.finditer(text):
        start = max([b for b in bounds if b < m.start()], default=-1) + 1
        end = min([b for b in bounds if b >= m.end()], default=len(text))
        s = text[start:end].strip()
        if s and s not in seen:
            seen.append(s)
    return seen


def _row(model, obj, field, idx, snippet, new, kind):
    name = "باز کردن" if model in ("core.SiteSettings", "seo.SeoSettings") else str(obj)[:80]
    return {"key": f"{model}|{obj.pk}|{field}|{idx}", "model": model, "label": LABELS[model], "obj": name,
            "edit_url": _edit_url(model, obj), "field": FIELD_LABELS.get(field, field), "old": snippet, "new": new,
            "auto": new != snippet, "kind": kind}


def _edit_url(model, obj):
    return {"core.SiteSettings": "/panel/settings/", "seo.SeoSettings": "/panel/settings/?tab=seo",
            "blog.Page": f"/panel/pages/{obj.pk}/", "blog.Post": f"/panel/posts/{obj.pk}/",
            "catalog.Product": f"/panel/products/{obj.pk}/edit/", "catalog.Category": f"/panel/categories/{obj.pk}/",
            "catalog.ProductTag": f"/panel/tags/{obj.pk}/"}.get(model, "")


def scan():
    rows = []
    for model, fields in TARGETS:
        M = apps.get_model(model)
        fields = [f for f in fields if f in {x.name for x in M._meta.get_fields()}]
        q = Q()
        for f in fields:
            for n in NEEDLES:
                q |= Q(**{f"{f}__contains": n})
        objs = list(M.objects.filter(q)) if model not in ("core.SiteSettings", "seo.SeoSettings") else [M.load()]
        for obj in objs:
            for f in fields:
                for i, s in enumerate(_snippets(getattr(obj, f) or "", FIND)):
                    rows.append(_row(model, obj, f, i, s, suggest(s), "claim"))
    site = apps.get_model("core.SiteSettings").load()
    for i, pair in enumerate(site.trust_points or []):
        for j, s in enumerate(pair if isinstance(pair, (list, tuple)) else [pair]):
            if isinstance(s, str) and FIND.search(s):
                rows.append(_row("core.SiteSettings", site, "trust_points", f"{i}.{j}", s, suggest(s), "claim"))
    # نشانی: همه‌جا یکسان
    if (site.address or "").strip() and site.address.strip() != ADDRESS:
        rows.append(_row("core.SiteSettings", site, "address", 0, site.address.strip(), ADDRESS, "address"))
    for model, fields in (("blog.Page", ["content"]), ("core.SiteSettings", ["footer_html", "home_about"])):
        M = apps.get_model(model)
        objs = [M.load()] if model == "core.SiteSettings" else M.objects.filter(Q(content__contains="زجاجی") | Q(content__contains="پکوک"))
        for obj in objs:
            for f in fields:
                for i, s in enumerate(_snippets(getattr(obj, f) or "", ADDR_FIND)):
                    new = ADDR_RULE.sub(ADDRESS, s, count=1)
                    if ADDRESS not in s:
                        rows.append(_row(model, obj, f, f"a{i}", s, new, "address"))
    return rows


def apply(choices, user=None):
    """choices: [(key, old, new)] — جملهٔ old در همان فیلد با new جایگزین می‌شود. خروجی: (تعداد، ContentEdit)"""
    from content.models import ContentEdit

    backup, done, touched = [], 0, set()
    with transaction.atomic():
        for key, old, new in choices:
            try:
                model, pk, field, _ = key.split("|", 3)
                M = apps.get_model(model)
            except (ValueError, LookupError):
                continue
            new = (new or "").strip()
            if not new or new == old or model not in LABELS:
                continue
            obj = M.objects.filter(pk=pk).first()
            if obj is None:
                continue
            if field == "trust_points":
                val = obj.trust_points or []
                before = [list(p) if isinstance(p, (list, tuple)) else p for p in val]
                after = [[new if x == old else x for x in p] if isinstance(p, list) else (new if p == old else p) for p in before]
                if after == before:
                    continue
                backup.append({"field": "__claims", "model": model, "id": obj.pk, "f": field, "old": before})
                M.objects.filter(pk=obj.pk).update(trust_points=after)
            elif field == "address":
                if (obj.address or "").strip() != old:
                    continue
                backup.append({"field": "__claims", "model": model, "id": obj.pk, "f": field, "old": obj.address})
                M.objects.filter(pk=obj.pk).update(address=new)
            else:
                allowed = {f for m, fs in TARGETS if m == model for f in fs}
                if field not in allowed or not isinstance(M._meta.get_field(field), (models.CharField, models.TextField)):
                    continue
                cur = getattr(obj, field) or ""
                if old not in cur:
                    continue
                backup.append({"field": "__claims", "model": model, "id": obj.pk, "f": field, "old": cur})
                M.objects.filter(pk=obj.pk).update(**{field: cur.replace(old, new)[:M._meta.get_field(field).max_length or None]})
            done += 1
            touched.add((model, obj.pk))
        edit = None
        if backup:
            edit = ContentEdit.objects.create(user=user, backup=backup, summary=f"اصلاح ادعاها و نشانی در {done} جمله")
    _refresh(touched)
    return done, edit


def _refresh(touched):
    """کش فایلی همین سایت (صفحهٔ اول، llms.txt، تنظیمات) پاک شود تا متن تازه بلافاصله دیده شود."""
    if touched:
        from django.core.cache import cache

        cache.clear()


def undo_rows(rows):
    for row in reversed(rows):
        if row.get("field") != "__claims" or row.get("model") not in LABELS:
            continue
        M = apps.get_model(row["model"])
        M.objects.filter(pk=row["id"]).update(**{row["f"]: row["old"]})
    from django.core.cache import cache

    cache.clear()
