from django.apps import AppConfig


class MarketConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "market"
    verbose_name = "مارکت‌پلیس (فروشندگان)"

    def ready(self):
        from django.db.models.signals import post_save

        from .orders import order_saved

        post_save.connect(order_saved, sender="shop.Order", dispatch_uid="market-order")
