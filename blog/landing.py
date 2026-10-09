"""بخش‌های زنده در متن مقاله‌ها و برگه‌ها (شورت‌کد).

نویسنده هر جای متن (در پنل) یکی از این‌ها را در یک خط جدا می‌نویسد و موقع نمایش، بخش زنده جایش می‌نشیند:

  [installment_calc]     ماشین‌حساب اقساط با روش‌های فعال
  [installment_prices]   لیست قیمت روز گروه‌های اصلی (شانه و جنس) با قسط ماهانهٔ هر روش
  [installment_plans]    شرایط هر روش اقساط و مدارک لازم، از تنظیمات پنل
  [installment_steps]    مراحل سفارش اقساطی آنلاین (بدون تماس)
  [installment_faq]      پرسش‌های رایج اقساط با پاسخ از تنظیمات (+ نشانه‌گذاری FAQ برای گوگل)
  [price_updated]        تاریخ آخرین تغییر قیمت‌ها (درون جمله)
  [size_prices 6-meter]       کمترین و بیشترین قیمت روز یک سایز در هر شانه (با پیوند)
  [size_prices 6-meter 700]   قیمت روز همان سایز در تک‌تک لیست‌های قیمت یک شانه
  [size_faq 6-meter 700]      پرسش‌های رایج قیمت آن سایز (و شانه) با پاسخ زنده (+ FAQPage)
  [shipping_info گرگان]       شیوه‌های پرداخت و ارسال امروز (سقف ارسال رایگان، بیعانه، اقساط) برای یک شهر
  [city_faq گرگان]            پرسش‌های رایج خرید فرش از آن شهر با پاسخ زنده (+ FAQPage)
  [reeds_compare 1000 1200]   جدول مقایسهٔ زندهٔ دو یا چند شانه (قیمت روز هر سایز، تراکم، جنس نخ، دستگاه بافت)
  [price_table]               لیست قیمت امروز (جای عکس‌های قدیمی price-list-*.jpg): قیمت ۱۲، ۹ و ۶ متری هر گروه + اقساط و ارسال
  [reeds_links]               کارت‌های انتخاب بر اساس شانه با قیمت روز (جای بنرهای تصویری ۷۰۰/۱۰۰۰/۱۲۰۰/۱۵۰۰ شانه)
  [city_notice]               اطلاعیهٔ «در شهر شما فروشگاه نداریم» (جای عکس at-city-min.jpg)؛ نام شهر از عنوان مقاله

متن ثابت مقاله (برای گوگل) دست‌نخورده می‌ماند؛ فقط عددها و جدول‌ها هر روز از قیمت و تنظیمات واقعی ساخته می‌شوند.
"""
import re

from django.core.cache import cache
from django.db.models import Max, Q
from django.template.loader import render_to_string
from django.utils.html import escape

from core.templatetags.fa import fa_num, jdate, toman

CODES = ("installment_calc", "installment_prices", "installment_plans", "installment_steps", "installment_faq")
BLOCK_RE = re.compile(r"(?:<p[^>]*>\s*)?\[(%s)\](?:\s*</p>)?" % "|".join(CODES))
INLINE_RE = re.compile(r"\[price_updated\]")
SIZE_RE = re.compile(r"(?:<p[^>]*>\s*)?\[(size_prices|size_faq)\s+([\w-]+)(?:\s+(\d+))?\s*\](?:\s*</p>)?")
SIZE_SLUGS = ["12-meter", "9-meter", "6-meter"]


MISC_RE = re.compile(r"(?:<p[^>]*>\s*)?\[(price_table|city_notice|reeds_links)\](?:\s*</p>)?")
CMP_RE = re.compile(r"(?:<p[^>]*>\s*)?\[reeds_compare((?:\s+\d{3,4}){2,4})\s*\](?:\s*</p>)?")
CITY_RE = re.compile(r"(?:<p[^>]*>\s*)?\[(shipping_info|city_faq)(?:\s+([^\]\[<>]{1,40}))?\](?:\s*</p>)?")


def has_blocks(content):
    c = content or ""
    return bool(BLOCK_RE.search(c) or INLINE_RE.search(c) or SIZE_RE.search(c) or CITY_RE.search(c) or CMP_RE.search(c) or MISC_RE.search(c))


def last_price_update():
    from pricing.models import Album

    return Album.objects.filter(is_active=True).aggregate(m=Max("last_updated"))["m"]


# ------------------------------------------------------------------ داده
def _plans():
    from installments.services import active_plans

    return active_plans()


def _best_quote(plan, price):
    """کمترین قسط ماهانهٔ ممکن: کمترین پیش‌پرداخت و بیشترین مدت."""
    from installments.calc import QuoteError, quote

    step = 1 if plan.allow_monthly else plan.steps()[0]
    months = plan.months_for(step)
    if not months:
        return None
    try:
        return quote(plan, price, plan.min_down_percent, months[-1], step)
    except QuoteError:
        return None


def price_rows():
    """[(گروه، نشانی صفحهٔ گروه، {اسلاگ سایز: کمترین قیمت روز})] برای فرش‌های خود ایران کارپت."""
    stamp = last_price_update()
    key = f"landing:prices:{int(stamp.timestamp()) if stamp else 0}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    from catalog.models import Attribute, Product, Variation
    from pricing.models import Size
    from rajyar.pricelist_image import material

    sizes = {s.pk: s.slug for s in Size.objects.filter(slug__in=SIZE_SLUGS)}
    reeds_attr = Attribute.objects.filter(slug="reeds-per-meter").first() or Attribute.objects.filter(label__contains="شانه").first()
    pile_attr = Attribute.objects.filter(label__contains="خاب").first()
    if not reeds_attr or not sizes:
        return []
    vs = list(Variation.objects.filter(product__status="publish", product__seller__isnull=True, size_id__in=list(sizes),
                                       is_available=True).exclude(product__sale_status="unavailable")
              .only("product_id", "size_id", "final_price", "sale_price"))
    pids = {v.product_id for v in vs}
    spec = {}
    attrs = [reeds_attr] + ([pile_attr] if pile_attr else [])
    for pid, name, aid in Product.specs.through.objects.filter(product_id__in=pids, attributeterm__attribute__in=attrs).values_list(
            "product_id", "attributeterm__name", "attributeterm__attribute_id"):
        spec.setdefault(pid, {})["reeds" if aid == reeds_attr.pk else "pile"] = name
    groups = {}
    for v in vs:
        sp = spec.get(v.product_id, {})
        digits = re.sub(r"\D", "", (sp.get("reeds") or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if not digits or not v.price:
            continue
        g = groups.setdefault((int(digits), material(sp.get("pile"))), {})
        slug = sizes[v.size_id]
        g[slug] = min(g.get(slug, v.price), v.price)
    order = {"پلی‌استر": 0, "آکریلیک": 1}
    out = []
    for (reeds, mat), by in sorted(groups.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 2))):
        if reeds not in (700, 1000, 1200, 1500):
            continue
        out.append((f"فرش {reeds} شانه {mat}".strip(), f"/reeds-per-meter/{reeds}/", by))
    cache.set(key, out, 3600)
    return out


# ------------------------------------------------------------------ بخش‌ها
def block_calc(request):
    from installments.services import describe
    from installments.views import plans_payload

    plans = _plans()
    if not plans:
        return '<div class="alert-ic alert-ic--warn">خرید اقساطی فعلاً فعال نیست.</div>'
    return render_to_string("blog/blocks/installment_calc.html", {
        "plans": [(p, describe(p)) for p in plans], "plans_json": plans_payload(plans), "amount": 50_000_000, "uid": "L",
    }, request=request)


def block_prices(request):
    from pricing.models import Size

    plans = _plans()
    rows = price_rows()
    if not rows:
        return ""
    sizes = list(Size.objects.filter(slug__in=SIZE_SLUGS).order_by("sort_order"))
    tabs = []
    for z in sizes:
        lines = []
        for name, url, by in rows:
            price = by.get(z.slug)
            if not price:
                continue
            per_plan = []
            for p in plans:
                q = _best_quote(p, price)
                per_plan.append(q)
            lines.append({"name": name, "url": url, "price": price, "quotes": per_plan})
        if lines:
            tabs.append({"size": z, "label": (z.label or "").split("(")[0].strip(), "lines": lines})
    return render_to_string("blog/blocks/installment_prices.html", {
        "tabs": tabs, "plans": plans, "updated": last_price_update()}, request=request)


def block_plans(request):
    from installments.services import describe

    plans = _plans()
    cards = []
    for p in plans:
        docs = [label for _, label, _ in p.info_fields]
        cards.append({"p": p, "desc": describe(p), "docs": docs,
                      "pay_at": "آنلاین، همان موقع ثبت سفارش" if p.down_timing == "checkout" else "آنلاین، بعد از تأیید مدارک"})
    return render_to_string("blog/blocks/installment_plans.html", {"cards": cards}, request=request)


def block_steps(request):
    from installments.services import page_url

    plans = _plans()
    return render_to_string("blog/blocks/installment_steps.html", {"plans": plans, "inst_url": page_url()}, request=request)


def faq_items():
    plans = _plans()
    from installments.services import faq_answer

    items = []
    if plans:
        items.append(("چه کسانی می‌توانند فرش را قسطی بخرند؟", faq_answer()))
    for p in plans:
        if p.kind == "beta":
            items.append(("بازنشستگان چطور بدون چک فرش قسطی بخرند؟",
                          f"بازنشستگان و مستمری‌بگیرانی که حقوقشان از بانک رفاه واریز می‌شود، از سامانهٔ بتای بانک رفاه "
                          f"{'بدون پیش‌پرداخت' if p.min_down_percent == 0 else 'با ' + fa_num(p.min_down_percent) + '٪ پیش‌پرداخت'} و "
                          f"{fa_num(p.min_months)} تا {fa_num(p.max_months)} ماه خرید می‌کنند؛ قسط‌ها هر ماه از حقوق کم می‌شود. "
                          "هنگام سفارش مشخصات بازنشستگی و کد ملی را وارد می‌کنید و پیامک تأیید بانک را تأیید می‌کنید."))
        if p.kind == "cheque":
            items.append(("برای خرید قسطی فرش با چک صیادی چه مدارکی لازم است؟",
                          "تصویر یک برگ از دسته‌چک صیادی خودتان و مشخصاتتان را هنگام سفارش آنلاین می‌فرستید. "
                          "بعد از تأیید، چک‌ها را طبق جدول اقساطی که در صفحهٔ سفارش می‌بینید می‌نویسید و پست می‌کنید؛ پیش از تأیید چک ننویسید."))
    if plans:
        items.append(("قیمت فرش اقساطی با قیمت نقدی فرق دارد؟",
                      "نه؛ قیمت پایه همان قیمت روز سایت است. سود اقساط فقط روی مبلغ باقی‌مانده بعد از پیش‌پرداخت و به نسبت مدت حساب می‌شود "
                      "و جدول کامل قسط‌ها پیش از ثبت سفارش نشان داده می‌شود."))
        items.append(("اولین قسط کی است؟",
                      f"اقساط از حدود {fa_num(plans[0].first_due_days)} روز بعد از ثبت سفارش (زمان آماده‌شدن فرش) شروع می‌شود و اولین قسط "
                      "یک دوره بعد از آن است. تاریخ همهٔ قسط‌ها در ماشین‌حساب همین صفحه دیده می‌شود."))
    items.append(("آیا می‌توانم اقساط را زودتر تسویه کنم؟", "بله؛ با تسویهٔ زودتر، سود مدت باقی‌مانده کم می‌شود."))
    items.append(("برای سفارش اقساطی باید تماس بگیرم؟",
                  "نه. فرش را در سایت انتخاب کنید، در سبد خرید «خرید اقساطی» را بزنید و مدارک را همان‌جا بفرستید. "
                  "نتیجهٔ بررسی با پیامک و در صفحهٔ «سفارش‌های من» به شما خبر داده می‌شود."))
    items.append(("فرش اقساطی چطور ارسال می‌شود؟",
                  "بعد از تأیید و آماده شدن، از کاشان به سراسر ایران فرستاده می‌شود؛ هزینهٔ ارسال موقع تحویل با شرکت حمل حساب می‌شود (پس‌کرایه)."))
    return items


def block_faq(request):
    return render_to_string("blog/blocks/faq.html", {"items": faq_items()}, request=request)


def size_prices(size_slug, reeds=None):
    """داده‌های جدول قیمت روز یک سایز (از همان لیست قیمت عمومی)."""
    from pricing.models import Size
    from pricing.pricelist import build

    z = Size.objects.filter(slug=size_slug).first()
    if not z:
        return None
    label = (z.label or "").split("(")[0].strip()
    data = build()
    groups = [g for g in data["groups"] if g["reeds"]]
    if reeds:
        g = next((g for g in groups if g["reeds"] == str(reeds)), None)
        if not g:
            return None
        rows = {}
        for al in g["albums"]:
            price = al["prices"].get(z.pk)
            if price:
                rows.setdefault(price, []).append(al)
        lines = [{"price": p, "albums": als, "count": sum(a["count"] for a in als)} for p, als in sorted(rows.items())]
        return {"size": z, "label": label, "group": g, "lines": lines, "updated": data["updated"]} if lines else None
    links = {}
    try:
        from landing.build import live

        for lp in live().filter(size=z, color=None, style=None).exclude(reeds=None).select_related("reeds"):
            links[lp.reeds.slug] = lp.get_absolute_url()
    except Exception:  # noqa: BLE001
        pass
    lines = []
    for g in groups:
        vals = [al["prices"][z.pk] for al in g["albums"] if al["prices"].get(z.pk)]
        if vals:
            lines.append({"title": g["title"], "min": min(vals), "max": max(vals), "lists": len(vals),
                          "url": links.get(g["reeds"]) or g["reeds_url"], "anchor": g["anchor"]})
    return {"size": z, "label": label, "lines": lines, "updated": data["updated"]} if lines else None


def block_size(request, size_slug, reeds=None):
    d = size_prices(size_slug, reeds)
    if not d:
        return ""
    return render_to_string("blog/blocks/size_prices.html", d, request=request)


def size_faq_items(size_slug, reeds=None):
    """پرسش و پاسخ‌های قیمت یک سایز، با عددهای امروز."""
    from shop.models import ShopSettings

    d = size_prices(size_slug, reeds)
    if not d:
        return []
    z, label = d["size"], fa_num(d["label"])
    name = f"فرش ماشینی {label}" + (f" {fa_num(reeds)} شانه" if reeds else "")
    out = []
    if reeds:
        lines = d["lines"]
        lo, hi = lines[0], lines[-1]
        out.append((f"قیمت {name} امروز چند است؟",
                    f"قیمت {name} در ایران کارپت امروز از {toman(lo['price'])} تومان"
                    + (f" تا {toman(hi['price'])} تومان است" if hi["price"] != lo["price"] else " است")
                    + f"؛ در {fa_num(sum(len(x['albums']) for x in lines))} لیست قیمت و {fa_num(sum(x['count'] for x in lines))} نقشه."))
        out.append((f"ارزان‌ترین {name} کدام است؟",
                    f"ارزان‌ترین لیست امروز «{fa_num(lo['albums'][0]['title'])}» با قیمت {toman(lo['price'])} تومان برای یک تخته است. "
                    "همهٔ نقشه‌ها و رنگ‌های یک لیست هم‌قیمت‌اند."))
    else:
        lines = d["lines"]
        lo = min(lines, key=lambda r: r["min"])
        hi = max(lines, key=lambda r: r["max"])
        out.append((f"قیمت {name} امروز چند است؟",
                    f"ارزان‌ترین {name} امروز {fa_num(lo['title'])} از {toman(lo['min'])} تومان است و گران‌ترین، "
                    f"{fa_num(hi['title'])}، تا {toman(hi['max'])} تومان. قیمت هر شانه در جدول همین صفحه آمده است."))
        if len(lines) > 1:
            out.append((f"فرق قیمت {name} در شانه‌های مختلف چقدر است؟",
                        "، ".join(f"{fa_num(r['title'])} از {toman(r['min'])}" for r in lines) + " تومان. "
                        "هرچه شانه و تراکم بیشتر باشد، نقش ظریف‌تر و قیمت بالاتر است."))
    if z.width and z.length:
        dims = f"{fa_num(f'{z.width:g}')} در {fa_num(f'{z.length:g}')} متر"
        out.append((f"ابعاد فرش {label} چقدر است؟",
                    f"فرش {label} استاندارد {dims} است (مساحت {fa_num(f'{z.area:g}')} متر مربع)."
                    + (" این سایز از عرض ۳ متری دستگاه بریده می‌شود و هزینهٔ پرتی در قیمتش هست." if z.needs_waste else "")))
    free = ShopSettings.load().free_shipping_min
    if free:
        out.append(("هزینهٔ ارسال چقدر است؟",
                    f"ارسال به سراسر ایران است؛ سفارش‌های بالای {toman(free)} تومان با پرداخت کامل آنلاین ارسال رایگان دارند "
                    "و بقیه پس‌کرایه (هزینهٔ حمل موقع تحویل) فرستاده می‌شوند."))
    plans = _plans()
    if plans:
        out.append((f"می‌توانم {name} را قسطی بخرم؟",
                    "بله، با " + " یا ".join(p.title for p in plans) + ". قیمت پایه همان قیمت نقدی روز است و جدول قسط‌ها را پیش از سفارش می‌بینید."))
    return out


def block_size_faq(request, size_slug, reeds=None):
    items = size_faq_items(size_slug, reeds)
    return render_to_string("blog/blocks/faq.html", {"items": items}, request=request) if items else ""


def _common_spec(product_ids, label):
    from django.db.models import Count

    from catalog.models import Product

    row = (Product.specs.through.objects.filter(product_id__in=product_ids, attributeterm__attribute__label=label)
           .values("attributeterm__name").annotate(c=Count("product_id", distinct=True)).order_by("-c").first())
    return row["attributeterm__name"] if row else ""


def reeds_compare(reeds_list):
    """ستون‌های جدول مقایسهٔ شانه‌ها از لیست قیمت و مشخصات فرش‌های منتشرشده."""
    from catalog.models import Product
    from pricing.pricelist import build

    data = build()
    groups = {g["reeds"]: g for g in data["groups"] if g["reeds"]}
    cols = []
    for r in reeds_list:
        g = groups.get(str(r))
        if not g:
            continue
        from catalog.models import AttributeTerm

        terms = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter").filter(
            Q(slug=str(r)) | Q(name=str(r)) | Q(name=fa_num(r)))
        ids = list(Product.objects.filter(status="publish", seller__isnull=True, specs__in=terms)
                   .values_list("pk", flat=True).distinct()[:2000])
        sm = g.get("size_min", {})
        cols.append({
            "reeds": str(r), "title": g["title"], "url": g["reeds_url"], "count": g["count"], "lists": len(g["albums"]),
            "p12": sm.get("12-meter"), "p9": sm.get("9-meter"), "p6": sm.get("6-meter"),
            "density": _common_spec(ids, "تراکم"), "pile": _common_spec(ids, "جنس نخ خاب"),
            "machine": _common_spec(ids, "دستگاه بافت"),
        })
    return cols


def block_compare(request, nums):
    cols = reeds_compare(nums)
    if len(cols) < 2:
        return ""
    return render_to_string("blog/blocks/reeds_compare.html", {"cols": cols, "updated": last_price_update()}, request=request)


def price_table_data():
    """گروه‌های اصلی (شانه و جنس) با کمترین قیمت ۱۲، ۹ و ۶ متری و تراکم رایج؛ کش با زمان آخرین تغییر قیمت."""
    stamp = last_price_update()
    key = f"landing:pt:{int(stamp.timestamp()) if stamp else 0}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    from catalog.models import AttributeTerm, Product

    rows = []
    density = {}
    for name, url, by in price_rows():
        reeds = re.sub(r"\D", "", name.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if reeds and reeds not in density:
            terms = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter").filter(Q(slug=reeds) | Q(name=reeds))
            ids = list(Product.objects.filter(status="publish", seller__isnull=True, specs__in=terms).values_list("pk", flat=True)[:2000])
            density[reeds] = _common_spec(ids, "تراکم")
        rows.append({"name": name, "url": url, "p12": by.get("12-meter"), "p9": by.get("9-meter"), "p6": by.get("6-meter"),
                     "density": density.get(reeds, "")})
    cache.set(key, rows, 3600)
    return rows


def block_price_table(request, title=""):
    rows = price_table_data()
    if not rows:
        return ""
    plans = _plans()
    cheapest = min((r["p12"] for r in rows if r["p12"]), default=None)
    quotes = []
    if cheapest:
        for p in plans:
            q = _best_quote(p, cheapest)
            if q:
                quotes.append((p, q))
    from installments.services import page_url

    return render_to_string("blog/blocks/price_table.html", {
        "rows": rows, "updated": last_price_update(), "quotes": quotes, "cheapest": cheapest,
        "ship": shipping_lines(),
        "inst_url": page_url(),
    }, request=request)


REEDS_CATS = [("700", "/product-category/carpet-700-reeds/"), ("1000", "/product-category/carpet-1000-reeds/"),
              ("1200", "/product-category/carpet-1200-reeds/"), ("1500", "/product-category/carpet-1500-reeds/")]


def block_reeds_links(request, title=""):
    """کارت‌های «انتخاب بر اساس شانه» با کمترین قیمت ۱۲ متری امروز (جای بنرهای تصویری شانه)."""
    from pricing.pricelist import build

    groups = {g["reeds"]: g for g in build()["groups"] if g["reeds"]}
    cards = []
    for reeds, url in REEDS_CATS:
        g = groups.get(reeds)
        sm = (g or {}).get("size_min", {}).get("12-meter")
        cards.append({"reeds": reeds, "url": url, "from": sm["min"] if sm else None, "count": g["count"] if g else None})
    return render_to_string("blog/blocks/reeds_links.html", {"cards": cards}, request=request)


def city_from_title(title):
    m = re.match(r"^\s*خرید\s+فرش\s+در\s+(.+?)(?:\s*[|⭐☀️🌎+\-–:؛،!]|$)", title or "")
    return m.group(1).strip() if m else ""


def block_city_notice(request, title=""):
    from core.models import SiteSettings

    return render_to_string("blog/blocks/city_notice.html", {
        "city": city_from_title(title), "site": SiteSettings.load()}, request=request)


def _shop():
    from shop.models import ShopSettings

    return ShopSettings.load()


def shipping_lines(city=""):
    sh = _shop()
    where = f"به {city}" if city else "به سراسر ایران"
    out = []
    if sh.allow_full:
        out.append(("پرداخت کامل آنلاین",
                    f"سفارش‌های بالای {toman(sh.free_shipping_min)} تومان ارسال رایگان {where} دارند؛ کمتر از آن، هزینهٔ حمل موقع تحویل پرداخت می‌شود."
                    if sh.free_shipping_min else f"ارسال {where}."))
    if sh.allow_deposit:
        out.append(("پرداخت بیعانه",
                    f"{fa_num(sh.deposit_percent)}٪ مبلغ هنگام سفارش و بقیه موقع تحویل؛ هزینهٔ حمل با خریدار است (پس‌کرایه)."))
    plans = _plans()
    if plans:
        out.append(("خرید اقساطی", " یا ".join(p.title for p in plans) + "؛ هزینهٔ حمل موقع تحویل پرداخت می‌شود."))
    return out


def block_shipping(request, city=""):
    return render_to_string("blog/blocks/shipping_info.html", {"lines": shipping_lines(city), "city": city}, request=request)


def city_faq_items(city):
    city = (city or "").strip()
    if not city:
        return []
    out = []
    d = size_prices("12-meter")
    if d and d["lines"]:
        lo = min(d["lines"], key=lambda r: r["min"])
        hi = max(d["lines"], key=lambda r: r["max"])
        out.append((f"قیمت فرش ماشینی در {city} چقدر است؟",
                    f"قیمت فرش برای خریداران {city} همان قیمت سایت است: فرش ۱۲ متری امروز از {toman(lo['min'])} تومان "
                    f"({fa_num(lo['title'])}) تا {toman(hi['max'])} تومان ({fa_num(hi['title'])}). قیمت هر سایز روی صفحهٔ همان فرش آمده است."))
    sh = _shop()
    out.append((f"ارسال فرش به {city} چطور است؟",
                f"فرش از کاشان بسته‌بندی و به {city} فرستاده می‌شود."
                + (f" سفارش‌های بالای {toman(sh.free_shipping_min)} تومان با پرداخت کامل آنلاین ارسال رایگان دارند؛ بقیه پس‌کرایه است."
                   if sh.free_shipping_min else "")))
    out.append((f"ایران کارپت در {city} نمایندگی دارد؟",
                "نه؛ ایران کارپت شعبه و نمایندگی در شهرها ندارد. سفارش آنلاین ثبت می‌شود و فرش مستقیم از کاشان به نشانی شما می‌رسد."))
    plans = _plans()
    if plans:
        out.append((f"در {city} می‌توانم فرش را قسطی بخرم؟",
                    "بله، از هر شهری با " + " یا ".join(p.title for p in plans) + " می‌توانید قسطی بخرید؛ مدارک را آنلاین می‌فرستید."))
    out.append(("چطور فرش مناسب را انتخاب کنم؟",
                "اول سایز را از روی اندازهٔ اتاق انتخاب کنید (صفحهٔ محاسبهٔ سایز فرش)، بعد شانه و رنگ زمینه را. "
                "اگر بین چند نقشه مانده‌اید، فرش‌یاب با چند سؤال ساده فرش‌های مناسب را پیشنهاد می‌دهد."))
    return out


def block_city_faq(request, city=""):
    items = city_faq_items(city)
    return render_to_string("blog/blocks/faq.html", {"items": items}, request=request) if items else ""


BLOCKS = {"installment_calc": block_calc, "installment_prices": block_prices, "installment_plans": block_plans,
          "installment_steps": block_steps, "installment_faq": block_faq}


def render(content, request, title=""):
    """متن با شورت‌کدها ← HTML نهایی."""
    def inline(_m):
        d = last_price_update()
        return f'<time datetime="{d.date().isoformat()}">{escape(jdate(d))}</time>' if d else "امروز"

    content = INLINE_RE.sub(inline, content or "")

    def block(m):
        try:
            return '<div class="live-block">' + BLOCKS[m.group(1)](request) + "</div>"
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("landing block %s", m.group(1))
            return ""

    content = BLOCK_RE.sub(block, content)

    def size_block(m):
        try:
            fn = block_size if m.group(1) == "size_prices" else block_size_faq
            html = fn(request, m.group(2), m.group(3))
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("size block %s", m.group(0))
            html = ""
        return '<div class="live-block">' + html + "</div>" if html else ""

    content = SIZE_RE.sub(size_block, content)

    def city_block(m):
        try:
            fn = block_shipping if m.group(1) == "shipping_info" else block_city_faq
            html = fn(request, (m.group(2) or "").strip())
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("city block %s", m.group(0))
            html = ""
        return '<div class="live-block">' + html + "</div>" if html else ""

    content = CITY_RE.sub(city_block, content)

    def cmp_block(m):
        try:
            html = block_compare(request, m.group(1).split())
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("compare block %s", m.group(0))
            html = ""
        return '<div class="live-block">' + html + "</div>" if html else ""

    content = CMP_RE.sub(cmp_block, content)

    def misc_block(m):
        try:
            fn = {"price_table": block_price_table, "city_notice": block_city_notice,
                  "reeds_links": block_reeds_links}[m.group(1)]
            html = fn(request, title)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("block %s", m.group(0))
            html = ""
        return '<div class="live-block">' + html + "</div>" if html else ""

    return MISC_RE.sub(misc_block, content)


FAQ_BOX_RE = re.compile(r'<div class="faq[^"]*">(.*?)</div>', re.S)
FAQ_ITEM_RE = re.compile(r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>", re.S)


def static_faq(content):
    """پرسش‌های رایج نوشته‌شده در خود متن (<div class="faq"><details><summary>پرسش</summary><p>پاسخ</p></details>…)."""
    out = []
    for box in FAQ_BOX_RE.findall(content or ""):
        for q, a in FAQ_ITEM_RE.findall(box):
            q, a = re.sub(r"<[^>]+>", "", q).strip(), " ".join(re.sub(r"<[^>]+>", " ", a).split())
            if q and a:
                out.append((q, a))
    return out


def faq_jsonld(content):
    items = []
    if "[installment_faq]" in (content or ""):
        items += faq_items()
    for m in CITY_RE.finditer(content or ""):
        if m.group(1) == "city_faq":
            try:
                items += city_faq_items(m.group(2))
            except Exception:  # noqa: BLE001
                pass
    for m in SIZE_RE.finditer(content or ""):
        if m.group(1) == "size_faq":
            try:
                items += size_faq_items(m.group(2), m.group(3))
            except Exception:  # noqa: BLE001
                pass
    items += static_faq(content)
    if not items:
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}

