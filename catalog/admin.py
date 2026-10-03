from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Attribute, AttributeTerm, Brand, Category, Product, ProductImage, ProductTag, Review, Variation

SEO = ("سئو", {"fields": ["seo_title", "seo_description", "focus_keyword", "robots", "canonical_url"], "classes": ["collapse"]})


class VariationInline(TabularInline):
    model = Variation
    extra = 0
    fields = ["size", "is_available", "override_price", "manual_price", "sale_price", "pair_only", "final_price", "sku"]
    readonly_fields = ["final_price"]
    autocomplete_fields = ["size"]
    show_change_link = True


class ImageInline(TabularInline):
    model = ProductImage
    extra = 0
    raw_id_fields = ["media"]


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["title", "album", "min_price", "stock_status", "sale_status", "status", "published_at"]
    list_filter = ["status", "sale_status", "stock_status", "kind", "brand", "album", "categories"]
    search_fields = ["title", "slug", "sku"]
    autocomplete_fields = ["album", "brand", "primary_category", "categories", "tags", "specs"]
    raw_id_fields = ["image"]
    readonly_fields = ["min_price", "max_price", "stock_status", "views"]
    inlines = [VariationInline, ImageInline]
    list_per_page = 50
    actions = ["mark_available", "mark_unavailable"]
    fieldsets = [
        (None, {"fields": ["title", "slug", "english_name", "status", "kind", "sku", "image"]}),
        ("قیمت‌گذاری", {"fields": ["album", "custom_base_price", "sale_status", "min_price", "max_price", "stock_status"]}),
        ("طبقه‌بندی", {"fields": ["primary_category", "categories", "tags", "brand", "specs"]}),
        ("محتوا", {"fields": ["short_description", "content"]}),
        SEO,
        ("سایر", {"fields": ["published_at", "modified_at", "menu_order", "rating_avg", "rating_count", "views"], "classes": ["collapse"]}),
    ]

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        form.instance.refresh_price_cache()

    @admin.action(description="وضعیت: موجود")
    def mark_available(self, request, qs):
        for p in qs:
            p.sale_status = "available"
            p.save()

    @admin.action(description="وضعیت: ناموجود")
    def mark_unavailable(self, request, qs):
        for p in qs:
            p.sale_status = "unavailable"
            p.save()


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "parent", "order"]
    search_fields = ["name", "slug"]
    list_editable = ["order"]
    raw_id_fields = ["image"]
    fieldsets = [(None, {"fields": ["name", "slug", "parent", "order", "image", "description"]}), SEO]


@admin.register(ProductTag)
class ProductTagAdmin(ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    raw_id_fields = ["logo"]


class TermInline(TabularInline):
    model = AttributeTerm
    extra = 0
    fields = ["name", "slug", "order"]


@admin.register(Attribute)
class AttributeAdmin(ModelAdmin):
    list_display = ["label", "slug", "is_public", "show_in_filters", "order"]
    inlines = [TermInline]


@admin.register(AttributeTerm)
class AttributeTermAdmin(ModelAdmin):
    list_display = ["name", "attribute", "slug", "order"]
    list_filter = ["attribute"]
    search_fields = ["name", "slug"]


@admin.register(Variation)
class VariationAdmin(ModelAdmin):
    list_display = ["product", "size", "final_price", "sale_price", "is_available"]
    list_filter = ["is_available", "size"]
    search_fields = ["product__title", "sku"]
    raw_id_fields = ["product", "image"]
    readonly_fields = ["final_price", "purchase_price"]


@admin.register(Review)
class ReviewAdmin(ModelAdmin):
    list_display = ["author_name", "product", "rating", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating"]
    search_fields = ["author_name", "content", "product__title"]
    raw_id_fields = ["product", "parent"]
    actions = ["approve"]

    @admin.action(description="تأیید نظرات")
    def approve(self, request, qs):
        qs.update(is_approved=True)
