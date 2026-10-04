from django.apps import AppConfig


class PricingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pricing"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from .pricelist import bump

        for model in ("pricing.Album", "pricing.Size", "catalog.Product"):
            post_save.connect(bump, sender=model, dispatch_uid=f"pricelist-save-{model}")
            post_delete.connect(bump, sender=model, dispatch_uid=f"pricelist-del-{model}")
