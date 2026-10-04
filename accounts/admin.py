from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import OtpCode, Profile


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = ["mobile", "user", "city"]
    search_fields = ["mobile", "user__username", "user__email", "user__first_name", "user__last_name"]
    raw_id_fields = ["user"]


@admin.register(OtpCode)
class OtpAdmin(ModelAdmin):
    list_display = ["mobile", "created_at", "attempts", "used"]
    search_fields = ["mobile"]
    readonly_fields = ["mobile", "code_hash", "created_at", "attempts", "used"]

    def has_add_permission(self, request):
        return False
