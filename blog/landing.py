"""بخش‌های زنده در متن مقاله‌ها و برگه‌ها (شورت‌کد).

نویسنده هر جای متن (در پنل) یکی از این‌ها را در یک خط جدا می‌نویسد و موقع نمایش، بخش زنده جایش می‌نشیند:

  [installment_calc]     ماشین‌حساب اقساط با روش‌های فعال
  [installment_prices]   لیست قیمت روز گروه‌های اصلی (شانه و جنس) با قسط ماهانهٔ هر روش
  [installment_plans]    شرایط هر روش اقساط و مدارک لازم، از تنظیمات پنل
  [installment_steps]    مراحل سفارش اقساطی آنلاین (بدون تماس)
  [installment_faq]      پرسش‌های رایج اقساط با پاسخ از تنظیمات (+ نشانه‌گذاری FAQ برای گوگل)
  [price_updated]        تاریخ آخرین تغییر قیمت‌ها (درون جمله)

متن ثابت مقاله (برای گوگل) دست‌نخورده می‌ماند؛ فقط عددها و جدول‌ها هر روز از قیمت و تنظیمات واقعی ساخته می‌شوند.
"""
import re

from django.core.cache import cache
from django.db.models import Max
from django.template.loader import render_to_string
from django.utils.html import escape

from core.templatetags.fa import fa_num, jdate

CODES = ("installment_calc", "installment_prices", "installment_plans", "installment_steps", "installment_faq")
BLOCK_RE = re.compile(r"(?:<p[^>]*>\s*)?\[(%s)\](?:\s*</p>)?" % "|".join(CODES))
INLINE_RE = re.compile(r"\[price_updated\]")
SIZE_SLUGS = ["12-meter", "9-meter", "6-meter"]


def has_blocks(content):
    return bool(BLOCK_RE.search(content or "") or INLINE_RE.search(content or ""))


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


BLOCKS = {"installment_calc": block_calc, "installment_prices": block_prices, "installment_plans": block_plans,
          "installment_steps": block_steps, "installment_faq": block_faq}


def render(content, request):
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

    return BLOCK_RE.sub(block, content)


def faq_jsonld(content):
    if "[installment_faq]" not in (content or ""):
        return None
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq_items()]}

