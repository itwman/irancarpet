"""خلاصهٔ خودکار صفحه‌های دسته، برند، برچسب و شانه (مثل صفحه‌های فرود).

در سرچ کنسول این صفحه‌ها پرنمایش‌اند ولی جز کارت فرش متنی ندارند (مثلاً «فرش پاتریس» ۵۶۰۰ نمایش با ۱٪ کلیک).
اینجا از دادهٔ واقعی یک بند معرفی، جدول قیمت هر سایز و چند پرسش متداول ساخته می‌شود؛ متن دستی پنل دست نمی‌خورد.
"""
import re

from django.core.cache import cache
from django.db.models import Count, Max, Min

from core.templatetags.fa import fa_num, toman

SIZE_TYPES = ["rect", "runner", "round"]


def _stamp():
    from pricing.models import Album

    t = Album.objects.aggregate(t=Max("last_updated"))["t"]
    return int(t.timestamp()) if t else 0


def _name(name):
    name = fa_num(name or "")
    return name if name.startswith(("فرش", "پادری", "کناره", "قالیچه", "گلیم")) else f"فرش {name}"


def info(archive, products_qs, name, reeds=None):
    if archive is None:
        return None
    key = f"archinfo:{archive._meta.label_lower}:{archive.pk}:{_stamp()}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    data = _build(products_qs, _name(name), reeds)
    cache.set(key, data, 3600)
    return data


def _build(products_qs, title, reeds):
    from catalog.models import AttributeTerm, Variation

    qs = products_qs.published().exclude(stock_status="outofstock")
    n = qs.count()
    if n < 2:
        return None
    ids = qs.values("pk")
    rows = list(Variation.objects.filter(product__in=ids, is_available=True, final_price__gt=0, size__is_active=True,
                                         size__type__in=SIZE_TYPES)
                .values("size__slug", "size__label", "size__sort_order")
                .annotate(lo=Min("final_price"), hi=Max("final_price"), n=Count("product", distinct=True))
                .order_by("size__sort_order"))
    size_rows = [{"slug": r["size__slug"], "label": re.sub(r"\s*\(.*?\)\s*", " ", r["size__label"]).strip(),
                  "lo": r["lo"], "hi": r["hi"], "n": r["n"]} for r in rows if r["n"]][:8]
    reeds_list = []
    if not reeds:
        reeds_list = [t for t in AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", products__in=ids)
                      .annotate(c=Count("products", distinct=True)).order_by("-c").values_list("name", flat=True)[:5]]
        reeds_list = sorted({r for r in reeds_list if str(r).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).isdigit()},
                            key=lambda x: int(str(x).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))))
    main = next((r for r in size_rows if r["slug"] == "12-meter"), None) or (size_rows[0] if size_rows else None)

    lead = f"<p>{fa_num(n)} طرح {title} در ایران کارپت موجود است"
    if len(reeds_list) > 1:
        lead += "، در " + _join([f"{fa_num(r)} شانه" for r in reeds_list])
    lead += "."
    if main:
        lead += (f" قیمت {main['label'] and fa_num(main['label'])} این مجموعه امروز "
                 + (f"از {toman(main['lo'])} تا {toman(main['hi'])} تومان است." if main["hi"] != main["lo"] else f"{toman(main['lo'])} تومان است."))
    lead += "</p>"
    note = ""
    if reeds:
        from landing.build import REEDS_NOTE

        note = REEDS_NOTE.get(str(reeds), "")
    lead += f"<p>{note + ' ' if note else ''}همهٔ فرش‌ها مستقیم از کاشان ارسال می‌شوند و خرید نقدی و اقساطی ممکن است.</p>"

    faqs = []
    if size_rows:
        parts = "، ".join(f"{fa_num(r['label'])} از {toman(r['lo'])}" for r in size_rows[:4])
        faqs.append({"q": f"قیمت {title} چند است؟", "a": f"قیمت هر سایز فرق می‌کند؛ امروز {parts} تومان. قیمت دقیق هر نقشه در صفحهٔ همان فرش است."})
        if len(size_rows) > 1:
            faqs.append({"q": f"{title} در چه سایزهایی هست؟",
                         "a": _join([fa_num(r["label"]) for r in size_rows]) + ". بعضی سایزهای کوچک فقط جفت فروخته می‌شوند."})
    faqs.append({"q": f"چند طرح {title} موجود است؟", "a": f"الان {fa_num(n)} طرح موجود است و این صفحه با تغییر موجودی کارخانه‌ها به‌روز می‌شود."})
    try:
        from installments.services import faq_answer

        ans = faq_answer()
        if ans:
            faqs.append({"q": f"امکان خرید اقساطی {title} هست؟", "a": ans})
    except Exception:  # noqa: BLE001
        pass
    return {"title": title, "lead": lead, "size_rows": size_rows, "faqs": faqs, "count": n}


def _join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "، ".join(items[:-1]) + " و " + items[-1]


def faq_jsonld(data):
    if not data or not data.get("faqs"):
        return None
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in data["faqs"]]}
