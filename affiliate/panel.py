"""بخش‌های پنل: همکاران فروش، پورسانت‌ها، تسویه‌ها و پله‌های پورسانت."""
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.html import format_html

from core.templatetags.fa import fa_num, jdate, toman
from dashboard.registry import Col, Resource, register

from . import commission as C
from . import track
from .models import Affiliate, AffiliateSettings, Commission, CommissionTier, Payout

G = "همکاری در فروش"


def _badge(o):
    cls = {"pending": "pending", "active": "publish", "rejected": "cancelled", "blocked": "draft",
           "waiting": "pending", "approved": "publish", "paid": "completed", "cancelled": "cancelled"}.get(o.status, "draft")
    return format_html('<span class="badge-ic b-{}">{}</span>', cls, o.get_status_display())


def _sales(o):
    return toman(C.period_sales(o)) if o.is_active else "—"


def _payable(o):
    v = o.commissions.filter(status=Commission.Status.APPROVED).aggregate(s=Sum("amount"))["s"] or 0
    return format_html("<strong>{}</strong>", toman(v)) if v else "۰"


def _approve(request, qs):
    from .views import activate

    n = 0
    for a in qs.exclude(status=Affiliate.Status.ACTIVE):
        activate(a, request)
        n += 1
    return f"{fa_num(n)} همکار فعال شد."


def _set_status(status, label):
    def fn(request, qs):
        from .views import _coupon_for

        n = 0
        for a in qs:
            a.status = status
            a.save(update_fields=["status"])
            if a.coupon_id:
                _coupon_for(a, AffiliateSettings.load())
            n += 1
        return f"{fa_num(n)} همکار {label}."
    return fn


def _payout(request, qs):
    s = AffiliateSettings.load()
    reference = (request.POST.get("action_value") or "").strip()
    done, skipped = [], []
    for a in qs:
        with transaction.atomic():
            rows = list(Commission.objects.select_for_update().filter(affiliate=a, status=Commission.Status.APPROVED))
            total = sum(r.amount for r in rows)
            if not rows or total < s.min_payout:
                skipped.append(a.name)
                continue
            p = Payout.objects.create(affiliate=a, amount=total, reference=(reference or "")[:60])
            Commission.objects.filter(pk__in=[r.pk for r in rows]).update(status=Commission.Status.PAID, payout=p)
            done.append(f"{a.name}: {toman(total)}")
        try:
            from accounts.sms import send_bulk

            send_bulk([a.mobile], f"ایران کارپت: {toman(total)} تومان پورسانت همکاری در فروش به حساب شما واریز شد."
                                  + (f" کد پیگیری: {reference}" if reference else ""))
        except Exception:  # noqa: BLE001
            pass
    msg = ("تسویه ثبت شد — " + "، ".join(done)) if done else "تسویه‌ای ثبت نشد."
    if skipped:
        msg += f" ({fa_num(len(skipped))} همکار مانده‌ای کمتر از حداقل تسویه ({toman(s.min_payout)}) داشت.)"
    return msg


def _links(o):
    if not o.pk or not o.is_active:
        return "بعد از تأیید ساخته می‌شود"
    return format_html('<code dir="ltr">{}</code>', track.general_link(o))


def _after_save(request, obj, created, form=None):
    from .views import _coupon_for

    if obj.status == Affiliate.Status.ACTIVE and not obj.approved_at:
        from .views import activate

        activate(obj, request)
    elif obj.coupon_id or obj.is_active:
        _coupon_for(obj, AffiliateSettings.load())
    for period in obj.commissions.filter(status__in=C.OPEN).values_list("period", flat=True).distinct():
        C.recalc(obj, period)


register(Resource(
    key="affiliates", model=Affiliate, title="همکاران فروش", single="همکار فروش", group=G, icon="users",
    columns=[Col("name", "نام", lambda o: o.name, "name"),
             Col("code", "کد", lambda o: format_html('<code dir="ltr">{}</code>', o.code), "code"),
             Col("status", "وضعیت", _badge, "status"),
             Col("mobile", "موبایل", lambda o: fa_num(o.mobile)),
             Col("city", "شهر", lambda o: o.city or "—"),
             Col("sales", "فروش این دوره", _sales), Col("payable", "قابل تسویه", _payable),
             Col("created_at", "ثبت‌نام", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["name", "code", "mobile", "city"], filters=["status"], date_filter="created_at", ordering=("-created_at",),
    fieldsets=[("همکار", ["name", "mobile", "city", "channels"], "main"),
               ("حساب بانکی", ["sheba", "account_holder"], "main"),
               ("وضعیت", ["status", "code", "custom_percent"], "side"), ("یادداشت", ["admin_note"], "side")],
    readonly=[("پیوند عمومی", _links),
              ("کد تخفیف اختصاصی", lambda o: o.coupon.code if o.pk and o.coupon_id else "—"),
              ("فروش این دوره", lambda o: f"{toman(C.period_sales(o))} تومان" if o.pk else "—"),
              ("قابل تسویه", lambda o: f"{_payable(o)} تومان" if o.pk else "—"),
              ("ورود با پیوند (۳۰ روز)", lambda o: fa_num(o.clicks.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30)).count()) if o.pk else "—")],
    actions={"approve": ("تأیید و فعال کردن", _approve),
             "block": ("توقف همکاری", _set_status(Affiliate.Status.BLOCKED, "متوقف شد")),
             "reject": ("رد درخواست", _set_status(Affiliate.Status.REJECTED, "رد شد")),
             "payout": ("ثبت تسویه (واریز همهٔ پورسانت‌های قابل تسویه)", _payout, "کد پیگیری واریز")},
    after_save=_after_save, can_add=False,
    help="درخواست‌های تازه «در انتظار تأیید» هستند؛ بعد از تأیید، پیوند کوتاه و کد تخفیف اختصاصی همکار ساخته و پیامک می‌شود. "
         "تسویه: همکارها را انتخاب کنید ← «ثبت تسویه»، بعد از واریز به شبای ثبت‌شده. «درصد اختصاصی» برای همکارهای ویژه، پله‌ها را نادیده می‌گیرد.",
))


def _order_link(o):
    return format_html('<a href="/panel/orders/{}/view/">{}</a>', o.order_id, fa_num(o.order.number))


def _cancel(request, qs):
    rows = list(qs.exclude(status=Commission.Status.PAID))
    Commission.objects.filter(pk__in=[r.pk for r in rows]).update(status=Commission.Status.CANCELLED, locked=True)
    for aid, period in {(r.affiliate_id, r.period) for r in rows}:
        C.recalc(Affiliate.objects.get(pk=aid), period)
    return f"{fa_num(len(rows))} پورسانت لغو شد."


def _recalc(request, qs):
    n = C.resync_all() + C.recalc_open()
    return f"پورسانت‌ها دوباره حساب شد ({fa_num(n)} دوره/سفارش)."


register(Resource(
    key="affiliate-commissions", model=Commission, title="پورسانت‌ها", single="پورسانت", group=G, icon="receipt",
    columns=[Col("order", "سفارش", _order_link), Col("affiliate", "همکار", lambda o: o.affiliate.name),
             Col("source", "از راه", lambda o: o.get_source_display(), "source"),
             Col("base", "فروش", lambda o: toman(o.base), "base"),
             Col("percent", "درصد", lambda o: f"{fa_num(o.percent.normalize())}٪"),
             Col("amount", "پورسانت", lambda o: toman(o.amount), "amount"),
             Col("status", "وضعیت", _badge, "status"),
             Col("created_at", "تاریخ", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["=order__number", "affiliate__name", "affiliate__code"], filters=["status", "source", "affiliate"],
    date_filter="created_at", ordering=("-created_at",), queryset=lambda qs: qs.select_related("order", "affiliate"),
    fieldsets=[("پورسانت", ["status", "base", "percent", "amount", "locked"], "main")],
    readonly=[("سفارش", lambda o: _order_link(o) if o.pk else "—"), ("همکار", lambda o: str(o.affiliate) if o.pk else "—"),
              ("دوره", lambda o: o.period if o.pk else "—")],
    can_add=False,
    actions={"cancel": ("لغو پورسانت", _cancel), "recalc": ("محاسبهٔ دوباره همه", _recalc)},
    help="وضعیت پورسانت خودکار از سفارش می‌آید: پرداخت ← «منتظر تحویل»، تحویل‌شده ← «قابل تسویه»، لغو یا مسترد ← «لغو». "
         "اگر مبلغ را دستی عوض می‌کنید، «مبلغ دستی» را روشن کنید تا دوباره حساب نشود.",
))

register(Resource(
    key="affiliate-payouts", model=Payout, title="تسویه‌ها", single="تسویه", group=G, icon="card",
    columns=[Col("affiliate", "همکار", lambda o: o.affiliate.name), Col("amount", "مبلغ", lambda o: toman(o.amount), "amount"),
             Col("reference", "کد پیگیری", lambda o: o.reference or "—"),
             Col("paid_at", "تاریخ", lambda o: jdate(o.paid_at, "%Y/%m/%d"), "paid_at")],
    search=["affiliate__name", "reference"], filters=["affiliate"], date_filter="paid_at", ordering=("-paid_at",),
    queryset=lambda qs: qs.select_related("affiliate"), can_add=False,
    fieldsets=[("تسویه", ["reference", "note", "paid_at"], "main")],
    readonly=[("همکار", lambda o: str(o.affiliate) if o.pk else "—"), ("مبلغ", lambda o: f"{toman(o.amount)} تومان" if o.pk else "—")],
    help="تسویه از «همکاران فروش ← انتخاب ← ثبت تسویه» ساخته می‌شود.",
))


def _tier_range(o):
    nxt = CommissionTier.objects.filter(min_sales__gt=o.min_sales).order_by("min_sales").first()
    return f"از {toman(o.min_sales)}" + (f" تا {toman(nxt.min_sales)}" if nxt else " به بالا")


register(Resource(
    key="commission-tiers", model=CommissionTier, title="پله‌های پورسانت", single="پلهٔ پورسانت", group=G, icon="layers",
    columns=[Col("range", "فروش در دوره (تومان)", _tier_range, "min_sales"),
             Col("percent", "پورسانت", lambda o: f"{fa_num(o.percent.normalize())}٪", "percent"),
             Col("title", "نام", lambda o: o.title or "—")],
    ordering=("min_sales",), fieldsets=[("پله", ["min_sales", "percent", "title"], "main")],
    after_save=lambda request, obj, created, form=None: C.recalc_open(),
    help="هر پله از «از فروش» شروع می‌شود و تا شروع پلهٔ بعدی ادامه دارد. پلهٔ اول را از ۰ بگذارید. "
         "دوره و روش محاسبه در «تنظیمات ← همکاری در فروش». با ذخیرهٔ هر پله، پورسانت‌های تسویه‌نشده دوباره حساب می‌شوند.",
))
