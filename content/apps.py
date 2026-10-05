from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content"
    verbose_name = "متن محصولات"

    def ready(self):
        from django.db.models.signals import m2m_changed, post_delete, post_save

        from . import models
        from .render import clear_cache

        def clear(*a, **kw):
            clear_cache()

        for m in (models.ContentTemplate, models.InfoBlock, models.ContentSettings):
            post_save.connect(clear, sender=m, weak=False)
            post_delete.connect(clear, sender=m, weak=False)
        for through in (models.ContentTemplate.albums.through, models.ContentTemplate.categories.through, models.InfoBlock.albums.through):
            m2m_changed.connect(clear, sender=through, weak=False)
