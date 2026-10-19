"""آماده‌کردن تنظیمات یک سایت دیگر روی همین کد (مثلاً فرشستان).

    python manage.py site_profile --brand فرشستان --site-name "فرشستان" --off affiliate market finder farshplus app torob manix

- نام برند و نام سایت در «تنظیمات سایت» ثبت می‌شود.
- در همهٔ تنظیمات یک‌ردیفی (پیامک‌ها، رج‌یار، فرش پلاس و...) «ایران کارپت» و «irancarpet.net» با نام و دامنهٔ این سایت عوض می‌شود.
- بخش‌های اختیاری خاموش می‌شوند (نشانی‌هایشان ۴۰۴ می‌دهند و اتصال‌هایشان غیرفعال می‌شود).
اجرای دوباره بی‌خطر است. روی خود ایران کارپت اجرا نکنید.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from core import brand as site_brand
from core.features import FEATURES

OLD_NAMES = ("ایران کارپت", "ایران‌کارپت")
OLD_DOMAINS = ("www.irancarpet.net", "irancarpet.net")
# مدل‌های تنظیمات و فیلد «فعال بودن» هر بخش
SWITCHES = {
    "affiliate": [("affiliate", "AffiliateSettings", "enabled")],
    "market": [("market", "MarketSettings", "enabled")],
    "farshplus": [("farshplus", "FarshPlusSettings", "enabled"), ("farshplus", "FarshPlusSettings", "gift_enabled")],
    "torob": [("torob", "TorobSettings", "enabled"), ("torob", "TorobSettings", "emalls_enabled")],
    "manix": [("shop", "ShopSettings", "manix_enabled")],
}


class Command(BaseCommand):
    help = "تنظیم نام برند، جایگزینی متن‌های پیش‌فرض و خاموش کردن بخش‌های اختیاری برای سایتی غیر از ایران کارپت"

    def add_arguments(self, parser):
        parser.add_argument("--brand", dest="brand_name", required=True, help="نام کوتاه برند، مثل فرشستان")
        parser.add_argument("--site-name", help="نام سایت (خالی = همان نام برند)")
        parser.add_argument("--off", nargs="*", default=[], choices=sorted(FEATURES), help="بخش‌هایی که خاموش می‌شوند")

    def handle(self, *args, brand_name=None, site_name=None, off=(), **opts):
        from core.models import SiteSettings

        new_name = brand_name.strip()
        new_domain = site_brand.domain()
        if not new_name:
            raise CommandError("نام برند خالی است")
        if new_domain.endswith("irancarpet.net"):
            raise CommandError("SITE_URL هنوز irancarpet.net است؛ این دستور برای سایت‌های دیگر است.")

        s = SiteSettings.load()
        s.brand_name = new_name
        s.site_name = site_name or new_name
        s.features_off = ",".join(sorted(set(off)))
        s.save()

        changed = 0
        for model in apps.get_models():
            if not hasattr(model, "load") or not model.__name__.endswith("Settings"):
                continue
            obj = model.load()
            fields = []
            for f in model._meta.get_fields():
                if isinstance(f, (models.CharField, models.TextField)) and not f.choices and f.name not in ("brand_name", "features_off"):
                    val = getattr(obj, f.name, None)
                    if isinstance(val, str) and val:
                        new = val
                        for o in OLD_NAMES:
                            new = new.replace(o, new_name)
                        for o in OLD_DOMAINS:
                            new = new.replace(o, new_domain)
                        if new != val:
                            setattr(obj, f.name, new)
                            fields.append(f.name)
            if fields:
                obj.save(update_fields=fields)
                changed += len(fields)
                self.stdout.write(f"  {model._meta.verbose_name}: {', '.join(fields)}")

        for name in off:
            for app_label, model_name, field in SWITCHES.get(name, []):
                try:
                    m = apps.get_model(app_label, model_name)
                except LookupError:
                    continue
                obj = m.load()
                if getattr(obj, field, None):
                    setattr(obj, field, False)
                    obj.save(update_fields=[field])
        site_brand.clear()
        self.stdout.write(self.style.SUCCESS(
            f"برند: {new_name} · دامنه: {new_domain} · {changed} متن پیش‌فرض اصلاح شد · بخش‌های خاموش: {', '.join(off) or '—'}"))
