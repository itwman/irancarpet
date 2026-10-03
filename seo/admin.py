from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import NotFoundLog, Redirect


@admin.register(Redirect)
class RedirectAdmin(ModelAdmin):
    list_display = ["source", "target", "status_code", "match", "hits", "is_active", "origin"]
    list_filter = ["status_code", "match", "is_active", "origin"]
    search_fields = ["source", "target"]


@admin.register(NotFoundLog)
class NotFoundLogAdmin(ModelAdmin):
    list_display = ["path", "hits", "last_seen", "referrer"]
    search_fields = ["path"]
