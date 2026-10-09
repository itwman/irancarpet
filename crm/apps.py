from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crm"
    verbose_name = "باشگاه مشتریان"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .carts import on_login

        user_logged_in.connect(on_login, dispatch_uid="crm-cart-login")
