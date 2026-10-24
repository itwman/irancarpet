from django.apps import AppConfig


class MirrorConfig(AppConfig):
    name = "mirror"
    verbose_name = "همگام‌سازی فرشستان و ایران کارپت"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import auto

        auto.connect()
