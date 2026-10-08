"""کادر «چرا ایران کارپت» صفحهٔ اول: «ارسال رایگان برای سفارشات بالای ۲۵ میلیون» ← حد واقعی (تنظیمات فروشگاه، ۵۰ میلیون)."""
import re

from django.db import migrations

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def forward(apps, schema_editor):
    S = apps.get_model("core", "SiteSettings")
    Shop = apps.get_model("shop", "ShopSettings")
    s = S.objects.filter(pk=1).first()
    shop = Shop.objects.first()
    if not s or not isinstance(s.trust_points, list):
        return
    limit = (shop.free_shipping_min if shop else 50_000_000) // 1_000_000
    new = []
    for item in s.trust_points:
        if isinstance(item, (list, tuple)) and any("ارسال رایگان" in str(x) for x in item):
            item = [re.sub(r"(?:\d+|[۰-۹]+)\s*میلیون", f"{limit} میلیون".translate(FA), str(x)) for x in item]
        new.append(item)
    if new != s.trust_points:
        S.objects.filter(pk=1).update(trust_points=new)


class Migration(migrations.Migration):
    dependencies = [("core", "0013_honest_seo_claims"), ("shop", "0009_orderitem_commission_percent_orderitem_seller_order")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
