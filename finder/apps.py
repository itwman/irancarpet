from django.apps import AppConfig


class FinderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finder"
    verbose_name = "فرش‌یاب"

    def ready(self):
        from django.db.models.signals import m2m_changed, post_delete, post_save

        from .models import Need

        def clear(*a, **kw):
            from django.core.cache import cache

            cache.delete_many(["finder:needs", "finder:config"])

        post_save.connect(clear, sender=Need, dispatch_uid="finder-need-save")
        post_delete.connect(clear, sender=Need, dispatch_uid="finder-need-del")
        for f in ("categories", "terms", "exclude_categories"):
            m2m_changed.connect(clear, sender=getattr(Need, f).through, dispatch_uid=f"finder-need-{f}")
