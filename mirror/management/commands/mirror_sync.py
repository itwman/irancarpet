from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("فرشستان: گرفتن محصولات، قیمت و موجودی از ایران کارپت (همان کاری که هر ۱۰ دقیقه خودکار انجام می‌شود). "
            "با --report فقط گزارش می‌دهد و چیزی تغییر نمی‌کند.")

    def add_arguments(self, p):
        p.add_argument("--report", action="store_true", help="فقط گزارش؛ بدون تغییر")
        p.add_argument("--apply", action="store_true", help="اعمال، حتی اگر «اعمال تغییرات» در پنل خاموش باشد")
        p.add_argument("--orders", action="store_true", help="بعدش سفارش‌ها را هم به ایران کارپت بفرست")

    def handle(self, *a, **o):
        from mirror.models import MirrorSettings
        from mirror.sync import run

        if not MirrorSettings.load().is_target:
            self.stdout.write("همگام‌سازی روشن نیست: پنل ← تنظیمات ← «همگام‌سازی کاتالوگ» (نشانی منبع، کلید و تیک «محصولات از سایت منبع گرفته شوند»).")
            return
        res = run(report=True if o["report"] else (False if o["apply"] else None), out=self.stdout.write)
        if res and not res.get("live") and not res.get("error"):
            self.stdout.write("نمونهٔ عنوان‌های تازه در فرشستان:")
            for t in res.get("sample_new", []):
                self.stdout.write(f"  • {t}")
            self.stdout.write("(فقط گزارش بود؛ چیزی تغییر نکرد.)")
        if o["orders"]:
            from mirror.orders import push_all

            push_all(out=self.stdout.write)
