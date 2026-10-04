"""خرید اقساطی در سفارش: خواندن فرم مدارک، ذخیرهٔ خصوصی تصویر چک، تأیید/رد از پنل."""
import io
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from accounts.utils import latin_digits, normalize_mobile

from .calc import QuoteError, quote
from .models import InstallmentPlan

log = logging.getLogger(__name__)
MAX_IMAGE = 8 * 1024 * 1024


def valid_national_code(code):
    code = latin_digits(code or "").strip()
    if len(code) != 10 or not code.isdigit() or len(set(code)) == 1:
        return False
    s = sum(int(code[i]) * (10 - i) for i in range(9)) % 11
    check = int(code[9])
    return check == s if s < 2 else check == 11 - s


def read_request(data, files, total, plan_id=None):
    """از فرم تسویه حساب (یا JSON اپ): روش، پیش‌پرداخت، مدت، فاصله و مدارک را می‌خواند.
    خروجی: (plan, quote, info, uploads, errors)"""
    errors = {}
    plan = InstallmentPlan.objects.filter(pk=latin_digits(str(plan_id or data.get("inst_plan") or "0")) or 0, is_active=True).first()
    if not plan:
        return None, None, {}, {}, {"inst_plan": "روش اقساط را انتخاب کنید."}
    q = None
    try:
        q = quote(plan, total, latin_digits(str(data.get("inst_down", plan.min_down_percent))),
                  latin_digits(str(data.get("inst_months") or "0")), latin_digits(str(data.get("inst_step") or "1")))
    except (QuoteError, ValueError) as e:
        errors["inst_quote"] = str(e) if isinstance(e, QuoteError) else "مقادیر اقساط درست نیست."
    info, uploads = {}, {}
    for key, label, typ in plan.info_fields:
        if typ == "image":
            f = files.get(f"inst_{key}") if files else None
            if not f:
                errors[f"inst_{key}"] = f"{label} را بارگذاری کنید."
                continue
            err = _check_image(f)
            if err:
                errors[f"inst_{key}"] = err
            else:
                uploads[key] = f
            continue
        val = latin_digits(str(data.get(f"inst_{key}") or "")).strip()[:200]
        if not val:
            errors[f"inst_{key}"] = f"{label} را وارد کنید."
        elif typ == "national_code" and not valid_national_code(val):
            errors[f"inst_{key}"] = "کد ملی درست نیست."
        elif typ == "mobile":
            val = normalize_mobile(val) or ""
            if not val:
                errors[f"inst_{key}"] = "شمارهٔ موبایل درست نیست."
        elif typ == "sayad" and not (val.isdigit() and len(val) == 16):
            errors[f"inst_{key}"] = "شناسهٔ صیادی ۱۶ رقم است."
        elif typ == "digits" and not val.replace("-", "").isdigit():
            errors[f"inst_{key}"] = f"{label} فقط عدد است."
        elif typ == "pensioner" and val not in plan.PENSIONER_CHOICES:
            errors[f"inst_{key}"] = "یکی از گزینه‌ها را انتخاب کنید."
        info[key] = val
    return plan, q, info, uploads, errors


def _check_image(f):
    if f.size > MAX_IMAGE:
        return "حجم تصویر باید کمتر از ۸ مگابایت باشد."
    try:
        from PIL import Image

        pos = f.tell() if hasattr(f, "tell") else 0
        img = Image.open(f)
        img.verify()
        f.seek(pos)
        if img.format not in ("JPEG", "PNG", "WEBP", "HEIC", "MPO"):
            return "فقط تصویر JPG یا PNG بفرستید."
    except Exception:  # noqa: BLE001
        return "فایل تصویر معتبر نیست."
    return ""


def private_dir(order):
    d = Path(settings.PRIVATE_ROOT) / "installments" / str(order.number)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_uploads(order, uploads):
    """تصویرها با کیفیت مناسب و بدون متادیتا (موقعیت مکانی و…) در پوشهٔ خصوصی ذخیره می‌شوند."""
    from PIL import Image, ImageOps

    saved = {}
    for key, f in uploads.items():
        f.seek(0)
        img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        img.thumbnail((2400, 2400))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88)
        path = private_dir(order) / f"{key}.jpg"
        path.write_bytes(buf.getvalue())
        saved[key] = str(path.relative_to(settings.PRIVATE_ROOT))
    return saved


def apply_to_order(order, plan, q, info, saved):
    order.payment_mode = "installment"
    order.installment_plan = plan
    order.installment = q
    order.installment_info = {**info, **saved}
    order.installment_state = "review"
    order.deposit_percent = q["down_percent"]
    order.online_amount = q["down"]
    if q["down"] and plan.down_timing == plan.DownTiming.CHECKOUT:
        order.status = order.Status.PENDING
    else:
        order.status = order.Status.ON_HOLD


def info_rows(order):
    """[(برچسب، مقدار، فایل؟)] برای نمایش در پنل."""
    labels = {k: (label, typ) for k, _, label, typ in InstallmentPlan.INFO_FIELDS}
    rows = []
    for key, val in (order.installment_info or {}).items():
        label, typ = labels.get(key, (key, "text"))
        rows.append((key, label, val, typ == "image"))
    return rows


def _sms(order, template, link=""):
    if not template:
        return False, "متن پیامک تنظیم نشده است."
    from accounts.sms import send_bulk

    text = template.replace("{name}", order.first_name or order.full_name).replace("{order}", str(order.number)).replace("{link}", link)
    return send_bulk([order.mobile], text)


def set_state(order, state, site_url=""):
    """تغییر وضعیت اقساط از پنل. خروجی: پیام برای مدیر."""
    plan = order.installment_plan
    order.installment_state = state
    order.installment_reviewed_at = timezone.now()
    msg = ""
    if state == "approved":
        if order.status == order.Status.ON_HOLD:
            # پیش‌پرداخت بعد از تأیید → مشتری حالا می‌تواند آنلاین بپردازد؛ بدون پیش‌پرداخت → آمادهٔ پردازش
            order.status = order.Status.PENDING if order.online_amount and order.paid_amount < order.online_amount else order.Status.PROCESSING
        if plan:
            ok, err = _sms(order, plan.approved_sms, site_url + order.get_absolute_url())
            msg = "پیامک تأیید فرستاده شد." if ok else f"پیامک فرستاده نشد: {err}"
    elif state == "rejected":
        if order.status in (order.Status.ON_HOLD, order.Status.PENDING):
            order.status = order.Status.CANCELLED
        if plan:
            ok, err = _sms(order, plan.rejected_sms)
            msg = "پیامک رد فرستاده شد." if ok else f"پیامک فرستاده نشد: {err}"
        if order.paid_amount:
            msg += " این سفارش پیش‌پرداخت دارد؛ بازگرداندن وجه را پیگیری کنید."
    elif state == "done" and order.status in (order.Status.ON_HOLD, order.Status.DEPOSIT_PAID, order.Status.PENDING):
        order.status = order.Status.PROCESSING
    order.save(update_fields=["installment_state", "installment_reviewed_at", "status"])
    return msg
