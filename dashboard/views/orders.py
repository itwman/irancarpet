from django import forms
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from shop.models import Order, Payment

from ..auth import staff_required
from ..forms import MoneyIntField, style_form, to_en
from ..models import log
from shop.views import PROVINCES


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status", "tracking_code", "admin_note", "first_name", "last_name", "mobile", "email",
                  "province", "city", "address", "postal_code", "note"]
        widgets = {"admin_note": forms.Textarea(attrs={"rows": 3}), "note": forms.Textarea(attrs={"rows": 2}),
                   "address": forms.Textarea(attrs={"rows": 2})}


class ManualPaymentForm(forms.Form):
    amount = MoneyIntField(label="مبلغ دریافتی (تومان)", min_value=1)
    method = forms.ChoiceField(label="روش", choices=[("cod", "نقد/کارتخوان موقع تحویل"), ("card", "کارت‌به‌کارت"), ("other", "سایر")])
    note = forms.CharField(label="توضیح / شمارهٔ پیگیری", required=False, max_length=100)


@staff_required
def order_view(request, pk):
    order = get_object_or_404(Order.objects.select_related("user"), pk=pk)
    form = style_form(OrderForm(instance=order))
    pay_form = style_form(ManualPaymentForm())
    if request.method == "POST":
        if request.POST.get("form") == "pay":
            pay_form = style_form(ManualPaymentForm(request.POST))
            if pay_form.is_valid():
                d = pay_form.cleaned_data
                with transaction.atomic():
                    Payment.objects.create(order=order, gateway="manual", amount=d["amount"], status="ok", ref_id=d["note"][:100],
                                           message=dict(pay_form.fields["method"].choices)[d["method"]], verified_at=timezone.now())
                    order.paid_amount += d["amount"]
                    order.paid_at = order.paid_at or timezone.now()
                    if order.status in ("pending", "on_hold"):
                        order.status = "paid" if order.paid_amount >= order.grand_total else "deposit_paid"
                    order.save()
                    from crm.notify import order_paid as crm_paid

                    if request.POST.get("notify") != "0":
                        crm_paid(order, d["amount"], customer=True, admin=False)
                log(request, "action", "سفارش‌ها", order, f"ثبت دریافت {d['amount']:,} تومان")
                messages.success(request, "دریافت وجه ثبت شد.")
                return redirect(request.path)
        else:
            old_status = order.status
            form = style_form(OrderForm(request.POST, instance=order))
            if form.is_valid():
                form.save()
                from crm.notify import status_changed

                status_changed(order, old_status)
                from shop.bnpl import on_status

                for ok, m in on_status(order, old_status):
                    (messages.success if ok else messages.warning)(request, m)
                log(request, "update", "سفارش‌ها", order, "وضعیت: " + order.get_status_display())
                messages.success(request, "سفارش ذخیره شد.")
                return redirect(request.path)
    from crm.customer import url as customer_url
    from installments.orders import info_rows

    return render(request, "dashboard/order_view.html", {
        "order": order, "form": form, "pay_form": pay_form, "items": order.items.select_related("product"),
        "payments": order.payments.all(), "provinces": PROVINCES,
        "inst_info": info_rows(order) if order.is_installment else [],
        "sms_logs": order.sms_logs.order_by("created_at"), "customer_url": customer_url(order.mobile),
    })


@staff_required
def order_installment(request, pk):
    """تأیید / رد / تکمیل درخواست اقساط."""
    from django.conf import settings

    from installments.orders import set_state

    order = get_object_or_404(Order, pk=pk, payment_mode="installment")
    state = request.POST.get("state")
    if request.method == "POST" and state in ("review", "approved", "rejected", "done"):
        msg = set_state(order, state, settings.SITE_URL)
        label = dict(Order._meta.get_field("installment_state").choices)[state]
        log(request, "action", "سفارش‌ها", order, f"اقساط: {label}")
        messages.success(request, f"وضعیت اقساط: {label}. {msg}".strip())
    return redirect(f"/panel/orders/{order.pk}/view/")


@staff_required
def order_print(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, "dashboard/order_print.html", {"rows": [(order, list(order.items.all()))], "mode": "invoice"})


def _selected(request):
    """سفارش‌های انتخاب‌شده در فهرست (ids=…) یا همهٔ نتایج فیلتر (all=1 با همان پارامترها)."""
    from ..registry import REGISTRY
    from .crud import apply_filters

    src = request.POST if request.method == "POST" else request.GET
    if src.get("all") == "1":
        return apply_filters(REGISTRY["orders"], Order.objects.all(), request).order_by("number")
    ids = [int(x) for x in src.getlist("ids") if str(x).isdigit()]
    return Order.objects.filter(pk__in=ids).order_by("number")


@staff_required
def orders_ship(request):
    """«ارسال شد» گروهی با کد رهگیری جدا برای هر سفارش."""
    from shop.orderflow import PREP, bulk

    qs = _selected(request)
    if request.method == "POST":
        ids = [int(x) for x in request.POST.getlist("ids") if x.isdigit()]
        qs = Order.objects.filter(pk__in=ids)
        tracking = {o.pk: request.POST.get(f"t_{o.pk}", "") for o in qs}
        done, skipped, msgs = bulk(qs, "shipped", PREP, request, notify=request.POST.get("notify") == "1", tracking=tracking)
        messages.success(request, f"{len(done)} سفارش «ارسال شد»." + (f" {len(skipped)} سفارش به خاطر وضعیتش دست نخورد." if skipped else ""))
        for ok, m in msgs:
            if not ok:
                messages.warning(request, m)
        return redirect("/panel/orders/?stage=shipped")
    rows = list(qs.prefetch_related("items")[:300])
    return render(request, "dashboard/orders_ship.html", {
        "ok": [o for o in rows if o.status in PREP], "skip": [o for o in rows if o.status not in PREP]})


@staff_required
def orders_print(request):
    """چاپ گروهی: فاکتورها (هر کدام یک صفحه) یا برچسب‌های ارسال (چند تا در هر صفحه)."""
    rows = [(o, list(o.items.all())) for o in _selected(request).prefetch_related("items")[:300]]
    mode = "label" if request.GET.get("mode") == "label" else "invoice"
    return render(request, "dashboard/order_print.html", {"rows": rows, "mode": mode})


@staff_required
def notify(request):
    """زنگولهٔ بالای پنل: سفارش‌های تازه (بعد از since) و کارهای فوری؛ هر دقیقه خوانده می‌شود."""
    from django.core.cache import cache
    from django.http import JsonResponse

    from core.templatetags.fa import fa_num, toman

    from shop.orderflow import late_summary

    since = int(request.GET.get("since") or 0) if (request.GET.get("since") or "0").isdigit() else 0
    latest = Order.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
    new = []
    if since:
        for o in Order.objects.filter(pk__gt=since).order_by("-pk")[:5]:
            new.append({"id": o.pk, "text": f"سفارش {fa_num(o.number)} · {o.full_name} · {toman(o.items_total)} تومان",
                        "status": o.get_status_display(), "url": f"/panel/orders/{o.pk}/view/"})
    counts = cache.get("panel:notify")
    if counts is None:
        from crm.models import ContactMessage

        late = late_summary()
        counts = [
            {"label": "سفارش عقب‌افتاده", "n": late["total"], "url": "/panel/orders/?late=late", "hot": True},
            {"label": "اقساطی منتظر بررسی", "n": Order.objects.filter(status="on_hold").count(), "url": "/panel/orders/?stage=review", "hot": True},
            {"label": "سفارش منتظر ارسال", "n": Order.objects.filter(status__in=("deposit_paid", "paid", "processing")).count(),
             "url": "/panel/orders/?stage=to_ship"},
            {"label": "پیام تازهٔ «تماس با ما»", "n": ContactMessage.objects.filter(status="new").count(),
             "url": "/panel/contact-messages/?status=new", "hot": True},
        ]
        from shop.offerflow import counts as offer_counts

        oc = offer_counts()
        counts += [
            {"label": "فرش جشنواره‌ای تمام‌شده؛ تمدید شود؟", "n": oc["waiting"], "url": "/panel/special-offers/?offer_state=waiting", "hot": True},
            {"label": "فرش جشنواره‌ای رو به پایان (۳ روز)", "n": oc["ending"], "url": "/panel/special-offers/?offer_state=ending"},
        ]
        cache.set("panel:notify", counts, 60)
    return JsonResponse({"latest": latest, "new": new, "items": counts,
                         "alert": sum(x["n"] for x in counts if x.get("hot"))})
