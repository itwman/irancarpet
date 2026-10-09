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
    return render(request, "dashboard/order_print.html", {"order": order, "items": order.items.all()})
