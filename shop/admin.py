from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from core.templatetags.fa import jdate, toman

from .models import Order, OrderItem, Payment, ShopSettings


class ItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ["title", "size_label", "unit_price", "quantity"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(TabularInline):
    model = Payment
    extra = 0
    fields = ["gateway", "amount", "status", "ref_id", "card", "message", "created_at"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ["number", "customer", "total", "paid", "payment_mode", "status_badge", "created"]
    list_filter = ["status", "payment_mode", "shipping_mode", "province"]
    search_fields = ["=number", "mobile", "first_name", "last_name", "email", "payments__ref_id"]
    list_select_related = ["user"]
    inlines = [ItemInline, PaymentInline]
    readonly_fields = ["number", "user", "items_total", "deposit_percent", "online_amount", "paid_amount", "created_at", "paid_at", "payment_mode", "shipping_mode"]
    fieldsets = [
        ("سفارش", {"fields": ["number", "status", "tracking_code", "admin_note"]}),
        ("مبالغ", {"fields": ["payment_mode", "shipping_mode", "items_total", "deposit_percent", "online_amount", "paid_amount", "created_at", "paid_at"]}),
        ("مشتری و ارسال", {"fields": ["user", ("first_name", "last_name"), ("mobile", "email"), ("province", "city"), "address", "postal_code", "note"]}),
    ]
    actions = ["to_processing", "to_shipped", "to_completed"]

    @admin.display(description="مشتری")
    def customer(self, o):
        return f"{o.full_name} ({o.mobile})"

    @admin.display(description="مبلغ", ordering="items_total")
    def total(self, o):
        return toman(o.items_total)

    @admin.display(description="پرداخت‌شده", ordering="paid_amount")
    def paid(self, o):
        return toman(o.paid_amount)

    @admin.display(description="تاریخ", ordering="created_at")
    def created(self, o):
        return jdate(o.created_at, "%Y/%m/%d %H:%M")

    @admin.display(description="وضعیت", ordering="status")
    def status_badge(self, o):
        colors = {"pending": "#9aa0b4", "deposit_paid": "#FFB21E", "paid": "#12A9B8", "processing": "#7CC46B",
                  "shipped": "#22265A", "completed": "#2e7d32", "cancelled": "#E5395B", "refunded": "#E5395B"}
        return format_html('<span style="background:{};color:#fff;border-radius:99px;padding:2px 10px;font-size:12px">{}</span>',
                           colors.get(o.status, "#999"), o.get_status_display())

    def _set(self, request, qs, status):
        n = qs.update(status=status)
        self.message_user(request, f"{n} سفارش به‌روز شد.")

    @admin.action(description="در حال آماده‌سازی")
    def to_processing(self, request, qs):
        self._set(request, qs, "processing")

    @admin.action(description="ارسال شد")
    def to_shipped(self, request, qs):
        self._set(request, qs, "shipped")

    @admin.action(description="تحویل شد")
    def to_completed(self, request, qs):
        self._set(request, qs, "completed")


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ["order", "gateway", "amount", "status", "ref_id", "created_at"]
    list_filter = ["gateway", "status"]
    search_fields = ["=order__number", "ref_id", "token"]
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(ShopSettings)
class ShopSettingsAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return not ShopSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
