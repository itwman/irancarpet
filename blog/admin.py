from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import BlogCategory, BlogTag, Comment, Faq, Page, Post

SEO = ("سئو", {"fields": ["seo_title", "seo_description", "focus_keyword", "robots", "canonical_url"], "classes": ["collapse"]})


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ["title", "status", "published_at", "views"]
    list_filter = ["status", "categories"]
    search_fields = ["title", "slug"]
    autocomplete_fields = ["categories", "tags", "primary_category"]
    raw_id_fields = ["image"]
    fieldsets = [(None, {"fields": ["title", "slug", "status", "image", "excerpt", "content", "categories", "primary_category", "tags", "author_name", "published_at", "modified_at"]}), SEO]


@admin.register(Page)
class PageAdmin(ModelAdmin):
    list_display = ["title", "slug", "parent", "template", "status"]
    search_fields = ["title", "slug"]
    raw_id_fields = ["image", "parent"]
    fieldsets = [(None, {"fields": ["title", "slug", "parent", "template", "status", "image", "content", "menu_order"]}), SEO]


@admin.register(BlogCategory)
class BlogCategoryAdmin(ModelAdmin):
    list_display = ["name", "slug", "parent"]
    search_fields = ["name", "slug"]


@admin.register(BlogTag)
class BlogTagAdmin(ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ["author_name", "post", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    raw_id_fields = ["post", "parent"]


@admin.register(Faq)
class FaqAdmin(ModelAdmin):
    list_display = ["question", "group", "product", "is_active", "order"]
    list_filter = ["group", "is_active"]
    raw_id_fields = ["product"]
