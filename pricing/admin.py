from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import render
from unfold.admin import ModelAdmin

from .models import Album, PriceLog, PricingSettings, Size


@admin.register(PricingSettings)
class PricingSettingsAdmin(ModelAdmin):
    list_display = ["__str__", "markup_percent", "shipping_fixed", "round_to", "round_method"]

    def has_add_permission(self, request):
        return not PricingSettings.objects.exists()


@admin.register(Size)
class SizeAdmin(ModelAdmin):
    list_display = ["label", "slug", "type", "area", "default_pair_only", "needs_waste", "is_active", "sort_order", "n"]
    list_editable = ["default_pair_only", "needs_waste", "is_active", "sort_order"]
    list_filter = ["type", "is_active"]
    search_fields = ["label", "slug"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("variations"))

    @admin.display(description="تعداد تنوع", ordering="_n")
    def n(self, obj):
        return obj._n


class PercentForm(forms.Form):
    percent = forms.DecimalField(label="درصد تغییر (مثلاً 5 یا -3.5)")


@admin.register(Album)
class AlbumAdmin(ModelAdmin):
    list_display = ["name", "code", "base_size", "base_price_fmt", "waste_type", "waste_value", "is_active", "products_n", "last_updated"]
    list_filter = ["is_active", "base_size"]
    search_fields = ["name", "code", "company"]
    actions = ["adjust_percent"]
    readonly_fields = ["last_updated"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_n=Count("products"))

    @admin.display(description="تعداد محصول", ordering="_n")
    def products_n(self, obj):
        return obj._n

    @admin.display(description="قیمت پایه", ordering="base_price")
    def base_price_fmt(self, obj):
        return f"{int(obj.base_price):,}"

    def save_model(self, request, obj, form, change):
        if change and "base_price" in form.changed_data:
            old = Album.objects.get(pk=obj.pk).base_price
            super().save_model(request, obj, form, change)
            PriceLog.objects.create(album=obj, old_price=old, new_price=obj.base_price, reason="admin_edit", user=request.user)
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="افزایش/کاهش درصدی قیمت پایه")
    def adjust_percent(self, request, queryset):
        if "apply" in request.POST:
            form = PercentForm(request.POST)
            if form.is_valid():
                p = form.cleaned_data["percent"]
                for album in queryset:
                    album.set_base_price((album.base_price * (1 + p / 100)).quantize(Decimal("1")), request.user, "bulk_percent")
                messages.success(request, f"قیمت {queryset.count()} آلبوم {p}٪ تغییر کرد و قیمت محصولات بازمحاسبه شد.")
                return None
        else:
            form = PercentForm()
        return render(request, "admin/pricing/percent_form.html", {"form": form, "albums": queryset, "title": "تغییر درصدی قیمت"})


@admin.register(PriceLog)
class PriceLogAdmin(ModelAdmin):
    list_display = ["created_at", "album", "product", "old_price", "new_price", "reason", "user"]
    list_filter = ["reason"]
    readonly_fields = [f.name for f in PriceLog._meta.fields]
