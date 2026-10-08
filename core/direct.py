"""بخش «خرید مستقیم فرش از کارخانه کاشان» صفحهٔ اول.

پربازدیدترین جستجوی سایت در سرچ کنسول همین عبارت است و صفحهٔ هدفش صفحهٔ اول است.
همهٔ عددها (کمترین قیمت روز هر شانه، تعداد فرش، حد ارسال رایگان، روش‌های اقساط) از دادهٔ واقعی ساخته می‌شوند.
"""
from django.core.cache import cache

from core.templatetags.fa import fa_num, toman

KEY = "home:direct"


def data():
    from blog.landing import last_price_update

    stamp = last_price_update()
    key = f"{KEY}:{int(stamp.timestamp()) if stamp else 0}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    out = _build(stamp)
    cache.set(key, out, 1800)
    return out


def _build(stamp):
    from blog.landing import price_rows
    from catalog.models import Product
    from core.models import SiteSettings
    from shop.models import ShopSettings

    site = SiteSettings.load()
    rows = []
    for name, url, by in price_rows():
        p = by.get("12-meter")
        if p:
            rows.append({"name": name, "url": url, "price": p})
    plans = []
    try:
        from installments.services import active_plans, page_url

        plans = active_plans()
        inst_url = page_url()
    except Exception:  # noqa: BLE001
        inst_url = ""
    inst_post = None
    try:
        from blog.models import Post

        inst_post = Post.objects.published().filter(slug="خرید-فرش-قسطی-از-کارخانه-فرش-کاشان").only("slug").first()
    except Exception:  # noqa: BLE001
        pass
    free_min = ShopSettings.load().free_shipping_min
    count = Product.objects.published().filter(seller__isnull=True).count()
    city = site.store_city or "کاشان"
    d = {
        "rows": rows, "count": count, "free_min": free_min, "updated": stamp, "address": site.address,
        "city": city, "has_store": site.has_store,
        "inst_url": inst_post.get_absolute_url() if inst_post else inst_url,
        "plans": [p.title for p in plans],
    }
    d["faq"] = faq(d, plans)
    return d


def faq(d, plans):
    rows = d["rows"]
    out = [("ایران کارپت خود کارخانه است یا واسطه؟",
            "ایران کارپت فروشگاه فرش ماشینی در کاشان است و فرش‌ها را مستقیم از کارخانه‌های فرش ماشینی کاشان تهیه می‌کند؛ "
            "بدون عمده‌فروش و مغازهٔ واسطه. فرش از کاشان بسته‌بندی و به نشانی شما فرستاده می‌شود.")]
    if rows:
        lo = min(rows, key=lambda r: r["price"])
        hi = max(rows, key=lambda r: r["price"])
        out.append(("قیمت فرش ۱۲ متری از کارخانه کاشان چند است؟",
                    f"امروز ارزان‌ترین فرش ۱۲ متری ({fa_num(lo['name'])}) از {toman(lo['price'])} تومان است و "
                    f"در گروه {fa_num(hi['name'])} از {toman(hi['price'])} تومان شروع می‌شود. "
                    "قیمت هر سایز و هر نقشه در صفحهٔ همان فرش و در لیست قیمت سایت هست و با تغییر قیمت کارخانه به‌روز می‌شود."))
    out.append(("برای خرید مستقیم باید به کاشان بیایم؟",
                "نه. فرش را در سایت انتخاب و سفارش می‌دهید و به همهٔ شهرهای ایران ارسال می‌شود."
                + (f" اگر بخواهید حضوری ببینید، فروشگاه ما در {d['city']} است: {d['address']}" if d["address"] else "")))
    if d["free_min"]:
        out.append(("هزینهٔ ارسال فرش از کاشان چقدر است؟",
                    f"برای سفارش‌های بالای {toman(d['free_min'])} تومان که هنگام ثبت سفارش کامل پرداخت شوند، ارسال رایگان است؛ "
                    "در بقیهٔ سفارش‌ها هزینهٔ حمل موقع تحویل به شرکت حمل پرداخت می‌شود."))
    if plans:
        out.append(("می‌توانم فرش را مستقیم از کارخانه قسطی بخرم؟",
                    "بله، با " + "، ".join(p.title for p in plans) + ". قیمت پایه همان قیمت روز سایت است و جدول قسط‌ها را پیش از ثبت سفارش می‌بینید."))
    out.append(("فرش‌ها ضمانت دارند؟",
                "بله؛ فرش‌ها ضمانت‌نامهٔ ۵ ساله دارند. شرایط کامل در صفحهٔ ضمانت سایت آمده است."))
    return out


def faq_jsonld(d):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in d["faq"]]}
