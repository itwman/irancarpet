"""ویجت‌ها و فیلدهای فرم پنل: انتخاب آژاکسی، تاریخ شمسی، مبلغ، ویرایشگر، تصویر."""
import re
from datetime import datetime, time

import jdatetime
from django import forms
from django.db import models
from django.utils import timezone

FA2EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
EN2FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# فیلدهایی که ویرایشگر متن کامل (HTML) می‌گیرند
RICH_FIELDS = {"content", "description", "answer", "footer_html", "home_about", "short_description", "checkout_note"}
# فیلدهای مبلغ (با جداکنندهٔ هزارگان)
MONEY_FIELDS = {"base_price", "custom_base_price", "override_price", "manual_price", "sale_price", "shipping_fixed",
                "free_shipping_min", "min_order_amount", "items_total", "online_amount", "paid_amount", "unit_price", "amount", "waste_value",
                "max_discount", "min_order", "referral_max", "referral_min_order", "referral_reward", "discount",
                "winback_amount", "winback_min_order", "vip_total", "points_per", "point_value", "points_min_order",
                "birthday_amount", "birthday_min_order", "review_reward_amount", "review_reward_min_order"}


def to_en(s):
    return str(s or "").translate(FA2EN)


# ------------------------------------------------------------ انتخاب آژاکسی
class _AcMixin:
    def __init__(self, url, attrs=None, create=False, media=False):
        super().__init__(attrs)
        self.ac_url, self.create, self.is_media = url, create, media

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        a = ctx["widget"]["attrs"]
        a["data-ac"] = self.ac_url
        if self.create:
            a["data-ac-create"] = "1"
        if self.is_media:
            a["data-ac-media"] = "1"
        return ctx

    def optgroups(self, name, value, attrs=None):
        vals = [v for v in value if v not in ("", None)]
        groups = []
        if not self.allow_multiple_selected:
            groups.append((None, [self.create_option(name, "", "—", not vals, 0)], 0))
        qs = getattr(self.choices, "queryset", None)
        if qs is not None and vals:
            field = self.choices.field
            for i, o in enumerate(qs.filter(pk__in=vals), start=1):
                opt = self.create_option(name, str(o.pk), field.label_from_instance(o), True, i)
                if self.is_media and getattr(o, "url", ""):
                    opt["attrs"]["data-thumb"] = o.url
                groups.append((None, [opt], i))
        return groups


class AcSelect(_AcMixin, forms.Select):
    pass


class AcSelectMultiple(_AcMixin, forms.SelectMultiple):
    pass


# --------------------------------------------------------------- تاریخ شمسی
def to_jalali_str(value, with_time=True):
    if not value:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        j = jdatetime.datetime.fromgregorian(datetime=value)
        return j.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d")
    return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")


class JalaliInput(forms.TextInput):
    def __init__(self, with_time=True, attrs=None):
        base = {"data-jdp": "", "autocomplete": "off", "placeholder": "۱۴۰۵/۰۷/۱۲" + (" ۱۴:۳۰" if with_time else ""), "class": "form-control ltr-num"}
        if not with_time:
            base["data-jdp-only-date"] = ""
        base.update(attrs or {})
        super().__init__(base)
        self.with_time = with_time

    def format_value(self, value):
        if isinstance(value, (datetime,)) or hasattr(value, "year"):
            return to_jalali_str(value, self.with_time).translate(EN2FA)
        return value


class JalaliDateTimeField(forms.CharField):
    def __init__(self, *args, with_time=True, **kwargs):
        kwargs.pop("max_length", None)
        for k in ("encoder", "decoder"):
            kwargs.pop(k, None)
        self.with_time = with_time
        kwargs.setdefault("widget", JalaliInput(with_time))
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if value in (None, ""):
            return None
        if hasattr(value, "year"):
            return value
        v = to_en(value).strip().replace("-", "/")
        m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", v)
        if not m:
            raise forms.ValidationError("تاریخ نامعتبر است. نمونه: ۱۴۰۵/۰۷/۱۲ ۱۴:۳۰")
        y, mo, d, hh, mm = m.groups()
        try:
            g = jdatetime.date(int(y), int(mo), int(d)).togregorian()
        except ValueError:
            raise forms.ValidationError("این تاریخ وجود ندارد.")
        if not self.with_time:
            return g
        dt = datetime.combine(g, time(int(hh or 0), int(mm or 0)))
        return timezone.make_aware(dt)


# ------------------------------------------------------------------- مبلغ
class MoneyInput(forms.TextInput):
    def __init__(self, attrs=None):
        base = {"inputmode": "numeric", "class": "form-control money", "autocomplete": "off"}
        base.update(attrs or {})
        super().__init__(base)

    def format_value(self, value):
        if value in (None, ""):
            return ""
        try:
            n = float(value)
            return f"{int(n):,}" if n == int(n) else f"{n:,}"
        except (TypeError, ValueError):
            return value


class _MoneyClean:
    def to_python(self, value):
        if isinstance(value, str):
            value = re.sub(r"[^\d.\-]", "", to_en(value))
        return super().to_python(value)


class MoneyIntField(_MoneyClean, forms.IntegerField):
    widget = MoneyInput


class MoneyDecimalField(_MoneyClean, forms.DecimalField):
    widget = MoneyInput


class NumberClean(forms.IntegerField):
    def to_python(self, value):
        if isinstance(value, str):
            value = to_en(value).replace(",", "").replace("٬", "")
        return super().to_python(value)


class Editor(forms.Textarea):
    def __init__(self, attrs=None):
        base = {"class": "rich", "rows": 12}
        base.update(attrs or {})
        super().__init__(base)


# -------------------------------------------------------- نگاشت فیلد ← ویجت
def formfield_for(db_field, ac_urls, **kwargs):
    """formfield_callback برای modelform_factory"""
    from .ac import AC

    name = db_field.name
    if isinstance(db_field, models.DateTimeField):
        return JalaliDateTimeField(label=db_field.verbose_name, required=not db_field.blank, help_text=db_field.help_text, with_time=True)
    if isinstance(db_field, models.DateField):
        return JalaliDateTimeField(label=db_field.verbose_name, required=not db_field.blank, help_text=db_field.help_text, with_time=False)
    if isinstance(db_field, (models.ForeignKey, models.OneToOneField, models.ManyToManyField)):
        key = ac_urls.get(name) or AC.key_for(db_field.related_model)
        ff = db_field.formfield(**kwargs)
        if key and ff is not None:
            spec = AC.get(key)
            multi = isinstance(db_field, models.ManyToManyField)
            cls = AcSelectMultiple if multi else AcSelect
            ff.widget = cls(f"/panel/ac/{key}/", create=bool(spec and spec.create), media=key == "media")
            if spec and spec.label:
                ff.label_from_instance = spec.label
        return ff
    if name in MONEY_FIELDS and isinstance(db_field, models.DecimalField):
        return MoneyDecimalField(label=db_field.verbose_name, required=not db_field.blank and not db_field.null,
                                 help_text=db_field.help_text, max_digits=db_field.max_digits, decimal_places=db_field.decimal_places)
    if name in MONEY_FIELDS and isinstance(db_field, (models.IntegerField, models.BigIntegerField, models.PositiveBigIntegerField, models.PositiveIntegerField)):
        return MoneyIntField(label=db_field.verbose_name, required=not db_field.blank and not db_field.null, help_text=db_field.help_text, min_value=0,
                             initial=db_field.get_default() if db_field.has_default() else None)
    ff = db_field.formfield(**kwargs)
    if ff is None:
        return None
    if isinstance(db_field, models.TextField) and name in RICH_FIELDS:
        ff.widget = Editor()
    elif isinstance(db_field, models.SlugField):
        ff.required = False
        ff.help_text = ff.help_text or "خالی بگذارید تا خودکار از عنوان ساخته شود."
        ff.widget.attrs["class"] = "form-control ltr-num"
    elif isinstance(ff, forms.IntegerField) and not isinstance(ff.widget, forms.HiddenInput):
        f2 = NumberClean(label=ff.label, required=ff.required, help_text=ff.help_text, min_value=getattr(ff, "min_value", None),
                         initial=ff.initial)
        f2.widget = forms.TextInput(attrs={"inputmode": "numeric", "class": "form-control ltr-num"})
        return f2
    return ff


def style_form(form):
    """کلاس‌های بوت‌استرپ روی ویجت‌ها"""
    for f in form.fields.values():
        w = f.widget
        if isinstance(w, forms.CheckboxInput):
            w.attrs.setdefault("class", "form-check-input")
            w.attrs.setdefault("role", "switch")
        elif isinstance(w, (forms.Select, forms.SelectMultiple)) and not w.attrs.get("data-ac"):
            w.attrs.setdefault("class", "form-select")
        elif isinstance(w, (AcSelect, AcSelectMultiple)):
            w.attrs.setdefault("class", "ac")
        elif isinstance(w, forms.FileInput):
            w.attrs.setdefault("class", "form-control")
        else:
            cls = w.attrs.get("class", "")
            if "form-control" not in cls and "rich" not in cls:
                w.attrs["class"] = (cls + " form-control").strip()
            if isinstance(w, forms.Textarea) and "rich" not in cls and str(w.attrs.get("rows", "10")) == "10":
                w.attrs["rows"] = 3
    return form
