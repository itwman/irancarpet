from decimal import Decimal

from django.db import migrations

TIERS = [(0, "1.5", "پلهٔ ۱"), (150_000_000, "2", "پلهٔ ۲"), (500_000_000, "2.5", "پلهٔ ۳"), (1_000_000_000, "3", "پلهٔ ۴"),
         (2_000_000_000, "3.5", "پلهٔ ۵")]


def seed(apps, schema_editor):
    Tier = apps.get_model("affiliate", "CommissionTier")
    if not Tier.objects.exists():
        for mn, p, t in TIERS:
            Tier.objects.create(min_sales=mn, percent=Decimal(p), title=t)


class Migration(migrations.Migration):
    dependencies = [("affiliate", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
