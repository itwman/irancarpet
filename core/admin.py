from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Media, SiteSettings


@admin.register(Media)
class MediaAdmin(ModelAdmin):
    list_display = ["title", "file", "width", "height"]
    search_fields = ["title", "file", "alt"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
