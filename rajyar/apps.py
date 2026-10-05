from django.apps import AppConfig


class RajyarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rajyar"
    verbose_name = "رج‌یار (انتشار در کانال‌ها)"

    def ready(self):
        from django.db.models.signals import post_save

        from . import signals

        post_save.connect(signals.product_saved, sender="catalog.Product", dispatch_uid="rajyar-product")
