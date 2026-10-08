from django.apps import AppConfig


class AffiliateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "affiliate"
    verbose_name = "همکاری در فروش"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import models
        from .commission import order_saved
        from .track import clear_cache

        post_save.connect(order_saved, sender="shop.Order", dispatch_uid="affiliate-order")

        def clear(*a, **kw):
            clear_cache()

        for m in (models.Affiliate, models.CommissionTier, models.AffiliateSettings):
            post_save.connect(clear, sender=m, weak=False)
            post_delete.connect(clear, sender=m, weak=False)
