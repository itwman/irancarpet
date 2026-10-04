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
                    if order.status == "pending":
                        order.status = "paid" if order.paid_amount >= order.items_total else "deposit_paid"
                    order.save()
                log(request, "action", "سفارش‌ها", order, f"ثبت دریافت {d['amount']:,} تومان")
                messages.success(request, "دریافت وجه ثبت شد.")
                return redirect(request.path)
        else:
            form = style_form(OrderForm(request.POST, instance=order))
            if form.is_valid():
                form.save()
                log(request, "update", "سفارش‌ها", order, "وضعیت: " + order.get_status_display())
                messages.success(request, "سفارش ذخیره شد.")
                return redirect(request.path)
    return render(request, "dashboard/order_view.html", {
        "order": order, "form": form, "pay_form": pay_form, "items": order.items.select_related("product"),
        "payments": order.payments.all(), "provinces": PROVINCES,
    })


@staff_required
def order_print(request, pk):
    order = get_object_or_404(Order, pk=pk)
    return render(request, "dashboard/order_print.html", {"order": order, "items": order.items.all()})
