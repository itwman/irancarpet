from django.apps import AppConfig


class DashboardConfig(AppConfig):
    name = "dashboard"
    verbose_name = "پنل مدیریت"

    def ready(self):
        from django.contrib import admin

        admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
        admin.site.site_url = "/panel/"
