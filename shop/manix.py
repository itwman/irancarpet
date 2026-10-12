"""مانیکس پلاس ← سایت: فهرست فرش‌ها برای انتخاب در فاکتور، سفارش تلفنی از فاکتور، لینک پرداخت، و پیش‌نویس فرش تازه.

پیدا کردن فرش از روی نام فاکتور، بی‌حساسیت به نوشتار:
  «ي/ك» عربی، ارقام فارسی و لاتین، فاصله و نیم‌فاصله و خط تیره («سرمه ای» = «سرمه‌ای» = «سرمه‌اي»)،
  و واژه‌های کمکی (فرش، نقشه، زمینه، طرح، رنگ، شانه). سایز از آخر نام خوانده می‌شود («- ۹ متری»، «۳×۲»، «کناره ۳ متری»).
فقط اگر **یک** فرش بخواند، همان انتخاب می‌شود؛ وگرنه پیش‌نویس تازه با درخواست آلبوم و تصویر ساخته می‌شود.
"""
import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

STOP = {"فرش", "نقشه", "زمینه", "طرح", "رنگ", "شانه", "ماشینی", "کد", "مدل", "با", "و"}
FA2EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CHARS = str.maketrans({"ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و",
                       "٫": ".", "/": ".", "×": "x", "*": "x", "X": "x"})
SIZE_SPLIT = re.compile(r"\s+[-–—|،,]\s+|\s*[،,]\s*")


def norm(text):
    """نوشتار یکسان: حروف عربی ← فارسی، ارقام لاتین، بدون اعراب و کشیده."""
    t = (text or "").translate(FA2EN).translate(CHARS)
    t = re.sub(r"[ً-ْـ]", "", t)  # اعراب و کشیده
    return t.lower().strip()


def tokens(text):
    t = norm(text)
    t = re.sub(r"[‌‍‎‏\-_()\[\]«»\"'.:؛;!؟?]+", " ", t)
    return [w for w in t.split() if w and w not in STOP]


def key(text):
    """کلید مقایسه: بدون فاصله و نیم‌فاصله (پس «سرمه ای» و «سرمه‌ای» یکی‌اند)."""
    return "".join(tokens(text))


def sorted_key(text):
    return " ".join(sorted(tokens(text)))


# ------------------------------------------------------------------ سایز
def _num(s):
    try:
        return Decimal(s)
    except Exception:  # noqa: BLE001
        return None


def parse_size(text):
    """Size از روی متن («۹ متری»، «۱۲ متری (۴ × ۳)»، «۳x۲»، «کناره ۳ متری»، «گرد قطر ۲»، یا نامک سایز)."""
    from pricing.models import Size

    t = norm(text)
    if not t:
        return None
    sizes = list(Size.objects.filter(is_active=True))
    for s in sizes:
        if t == s.slug or t == norm(s.label) or key(t) == key(s.label):
            return s
    m = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", t)
    if m:
        a, b = sorted([_num(m.group(1)), _num(m.group(2))])
        if a and b and a > 10:  # سانتی‌متر
            a, b = a / 100, b / 100
        for s in sizes:
            if s.width and s.length and sorted([s.width, s.length]) == [a, b]:
                return s
    m = re.search(r"قطر\s*(\d+(?:\.\d+)?)", t)
    if m:
        d = _num(m.group(1))
        for s in sizes:
            if s.diameter and s.diameter == d:
                return s
    m = re.search(r"(\d+(?:\.\d+)?)\s*متر", t)
    if m:
        area = _num(m.group(1))
        kind = "runner" if "کناره" in t else "rug" if "قالیچه" in t else None
        square = "مربع" in t
        cands = [s for s in sizes if s.area and abs(Decimal(s.area) - area) < Decimal("0.01") and (not kind or s.type == kind)]
        if kind == "runner":
            cands = [s for s in sizes if s.type == "runner" and s.length == area] or cands
        if square:
            cands = [s for s in cands if s.width == s.length] or cands
        elif len(cands) > 1:
            cands = [s for s in cands if s.width != s.length] or cands
        if len(cands) >= 1:
            return cands[0]
    return None


def split_name(name):
    """«فرش X زمینه Y - ۹ متری» ← («فرش X زمینه Y»، Size)."""
    name = (name or "").strip()
    parts = [p for p in SIZE_SPLIT.split(name) if p.strip()]
    if len(parts) > 1:
        size = parse_size(parts[-1])
        if size:
            return " ".join(parts[:-1]).strip(), size
    m = re.search(r"\s(\d+(?:[.٫]\d+)?\s*متری.*|[\d۰-۹.٫]+\s*[x×*]\s*[\d۰-۹.٫]+.*)$", name)
    if m:
        size = parse_size(m.group(1))
        if size:
            return name[:m.start()].strip(), size
    return name, None


# ------------------------------------------------------------------ پیدا کردن فرش
def find_product(core):
    """یک فرش با همین نام (بی‌حساسیت به نوشتار)، یا None اگر هیچ یا چند تا بخواند."""
    from catalog.models import Product

    k, sk = key(core), sorted_key(core)
    if not k:
        return None
    qs = Product.objects.exclude(status="trash").filter(seller__isnull=True).only("pk", "title", "status")
    exact, loose = [], []
    for p in qs.iterator(chunk_size=1000):
        pk_ = key(p.title)
        if pk_ == k:
            exact.append(p)
        elif sorted_key(p.title) == sk:
            loose.append(p)
    for group in (exact, loose):
        live = [p for p in group if p.status == "publish"] or group
        if len(live) == 1:
            return live[0]
    return None


def match_item(name, variation_id=None, sku=""):
    """(Variation یا None، Product یا None، Size یا None) برای یک ردیف فاکتور."""
    from catalog.models import Variation

    if variation_id:
        v = Variation.objects.filter(pk=variation_id).select_related("product", "size").first()
        if v:
            return v, v.product, v.size
    if sku:
        v = Variation.objects.filter(sku=sku).select_related("product", "size").first()
        if v:
            return v, v.product, v.size
    core, size = split_name(name)
    product = find_product(core)
    if product is None:
        return None, None, size
    v = product.variations.filter(size=size).first() if size else None
    return v, product, size


def ensure_draft(core, size):
    """فرش تازه (پیش‌نویس) برای ردیفی که در سایت نبود؛ آلبوم قیمت و تصویر را مدیر کامل می‌کند."""
    from catalog.models import Product, Variation
    from dashboard.ac import unique_slug

    title = re.sub(r"\s+", " ", (core or "").replace("‌ ", "‌")).strip()[:300] or "فرش تازه از مانیکس"
    product = find_product(title)
    if product is None:
        product = Product.objects.create(title=title, slug=unique_slug(Product, title), status="draft", manix_draft=True,
                                         custom_note="از فاکتور تلفنی مانیکس پلاس ساخته شد؛ آلبوم قیمت و تصویر را وارد کنید.")
    v = None
    if size is not None:
        v = product.variations.filter(size=size).first() or Variation.objects.create(product=product, size=size)
    return product, v


# ------------------------------------------------------------------ فهرست فرش‌ها برای مانیکس
def catalog_rows():
    from catalog.models import Variation

    from .wc_api import variation_sku

    qs = (Variation.objects.filter(product__status="publish", product__seller__isnull=True)
          .select_related("product", "size").order_by("product_id", "menu_order", "pk"))
    out = []
    for v in qs.iterator(chunk_size=1000):
        size = v.size.label if v.size_id else ""
        out.append({"variation_id": v.pk, "product_id": v.product_id, "sku": variation_sku(v),
                    "name": f"{v.product.title} - {size}" if size else v.product.title, "size": size,
                    "price": int(v.price or 0), "available": bool(v.is_available and v.product.stock_status != "outofstock")})
    return out


# ------------------------------------------------------------------ سفارش تلفنی از فاکتور
class ManixError(ValueError):
    pass


def _int(v):
    try:
        return max(int(Decimal(str(v or 0))), 0)
    except Exception:  # noqa: BLE001
        return 0


@transaction.atomic
def upsert_order(data):
    """فاکتور مانیکس ← سفارش سایت (ایدمپوتنت با شناسهٔ فاکتور). خروجی: (Order، [ردیف‌ها])."""
    from accounts.utils import normalize_mobile
    from accounts.views import user_for_mobile

    from .models import Order, OrderItem, Payment

    ref = str(data.get("ref") or "").strip()[:40]
    if not ref:
        raise ManixError("شناسهٔ فاکتور (ref) لازم است.")
    c = data.get("customer") or {}
    mobile = normalize_mobile(str(c.get("mobile") or ""))
    if not mobile:
        raise ManixError("شمارهٔ موبایل مشتری در فاکتور ثبت نشده یا نادرست است.")
    items = [i for i in (data.get("items") or []) if (i.get("name") or "").strip() and _int(i.get("qty")) > 0]
    if not items and not data.get("cancelled"):
        raise ManixError("فاکتور ردیف ندارد.")

    order = Order.objects.select_for_update().filter(manix_ref=ref).first()
    site_paid = bool(order and order.payments.filter(status="ok").exclude(gateway="manix").exists())
    name = (c.get("name") or "").strip()
    first, _, last = name.partition(" ")
    if order is None:
        order = Order(manix_ref=ref, src="phone", src_name="تلفنی (مانیکس پلاس)", payment_mode="full", shipping_mode="cod")
    order.first_name, order.last_name = (first or "مشتری")[:100], last[:100]
    order.mobile = mobile
    order.province, order.city = (c.get("province") or "")[:60], (c.get("city") or "")[:80]
    order.address, order.postal_code = (c.get("address") or "—"), (c.get("postcode") or "")[:10]
    order.user = order.user or user_for_mobile(mobile)
    order.admin_note = f"فاکتور {data.get('number') or ''} مانیکس پلاس".strip()
    if data.get("date") and not order.pk:
        from .wc_api import _parse_dt

        order.created_at = _parse_dt(data["date"]) or timezone.now()
    lines = []
    if not site_paid:  # بعد از پرداخت آنلاین، ردیف‌ها و مبلغ فقط در مانیکس اصلاح می‌شوند
        order.discount = _int(data.get("discount"))
        order.items_total = _int(data.get("total"))
    order.save()
    if not site_paid and items:
        order.items.all().delete()
        for i in items:
            v, product, size = match_item(i.get("name"), _int(i.get("variation_id")), (i.get("sku") or "").strip())
            draft = False
            if product is None:
                core, size2 = split_name(i.get("name"))
                product, v = ensure_draft(core, size or size2)
                draft = True
            OrderItem.objects.create(order=order, product=product, variation=v, title=product.title if product else i["name"][:300],
                                     size_label=(v.size.label if v and v.size_id else "")[:150], unit_price=_int(i.get("price")),
                                     quantity=_int(i.get("qty")) or 1)
            lines.append({"name": i.get("name"), "variation_id": v.pk if v else 0, "product_id": product.pk if product else 0,
                          "draft": draft, "index": i.get("index")})

    # پرداخت‌های ثبت‌شده در مانیکس (نقدی، کارت، چک وصول‌شده…)
    seen = set()
    for p in data.get("payments") or []:
        amount, pid = _int(p.get("amount")), str(p.get("id") or "")[:60]
        if not amount or not pid:
            continue
        ref_id = f"mx:{pid}"
        seen.add(ref_id)
        from .wc_api import _parse_dt

        when = _parse_dt(p.get("date")) or timezone.now()
        Payment.objects.update_or_create(order=order, gateway="manix", ref_id=ref_id, defaults={
            "amount": amount, "status": "ok", "verified_at": when, "created_at": when, "message": "ثبت در مانیکس پلاس"})
    order.payments.filter(gateway="manix").exclude(ref_id__in=seen).delete()

    paid = sum(order.payments.filter(status="ok").values_list("amount", flat=True))
    order.paid_amount = paid
    first_pay = order.payments.filter(status="ok").order_by("verified_at").values_list("verified_at", flat=True).first()
    order.paid_at = first_pay if paid else None
    advanced = order.status in ("processing", "shipped", "completed", "refunded")
    if data.get("cancelled"):
        if not site_paid and not advanced:
            order.status = "cancelled"
    elif not advanced:
        order.status = "paid" if paid and paid >= order.grand_total else ("deposit_paid" if paid else "pending")
    pay = data.get("pay_link") or None
    if pay is not None:
        amount = _int(pay.get("amount")) or order.remaining
        order.online_amount = min(amount, order.remaining)
        if order.status == "cancelled":
            raise ManixError("سفارش لغو شده است؛ لینک پرداخت ساخته نمی‌شود.")
    elif order.online_amount and order.online_amount > order.remaining:
        order.online_amount = order.remaining
    order.save()
    return order, lines


def pay_urls(order):
    from crm.links import shorten
    from growth.jobs import quickpay_url

    full = quickpay_url(order)
    return full, shorten(full, "o", days=30)


def send_pay_sms(order):
    from core.templatetags.fa import toman
    from crm.models import CrmSettings, SmsLog
    from crm.notify import context, render, send

    s = CrmSettings.load()
    ctx = context(order, amount=toman(order.online_amount), pay_link=pay_urls(order)[1])
    return send(order.mobile, render(s.manix_pay_text, **ctx), SmsLog.Kind.ORDER, order)
