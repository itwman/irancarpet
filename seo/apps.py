from django.apps import AppConfig


class SeoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "seo"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import signals

        for model, fn in (("catalog.Product", signals.product), ("pricing.Album", signals.album),
                          ("blog.Post", signals.post), ("blog.Page", signals.page)):
            post_save.connect(fn, sender=model, dispatch_uid=f"indexnow-save-{model}")
            post_delete.connect(fn, sender=model, dispatch_uid=f"indexnow-del-{model}")
