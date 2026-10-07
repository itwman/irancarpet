"""کم‌حجم کردن تصویرهای قبلی کتابخانهٔ رسانه (همان نام و نشانی می‌ماند).

    python manage.py optimize_media            ← فقط گزارش (چیزی تغییر نمی‌کند)
    python manage.py optimize_media --apply    ← اعمال

فقط JPEG و WEBP و PNG بزرگ‌تر از ۷۰۰ کیلوبایت یا با ضلع بیشتر از ۲۴۰۰ پیکسل. قالب فایل عوض نمی‌شود تا پیوندها نشکنند.
"""
import os

from django.core.management.base import BaseCommand

from core.images import MAX_BYTES, SIDES, optimize_bytes
from core.models import Media


class Command(BaseCommand):
    help = "کم‌حجم کردن تصویرهای بزرگ کتابخانهٔ رسانه"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="واقعاً فایل‌ها را جایگزین کن")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, apply=False, limit=0, **kw):
        n = before = after = 0
        qs = Media.objects.exclude(file="").order_by("pk")
        for m in qs.iterator():
            name = m.file.name
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".jpg", ".jpeg", ".webp", ".png"):
                continue
            try:
                path = m.file.path
                size = os.path.getsize(path)
            except (OSError, NotImplementedError, ValueError):
                continue
            if size <= MAX_BYTES and (m.width or 0) <= SIDES[0] and (m.height or 0) <= SIDES[0]:
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            fmt = {".png": "PNG", ".webp": "WEBP"}.get(ext, "JPEG")
            out, _new_name, w, h, changed = optimize_bytes(data, name, force_format="PNG" if fmt == "PNG" else "JPEG")
            if not changed or len(out) >= size:
                continue
            if fmt == "WEBP":  # نام .webp می‌ماند؛ محتوا هم WEBP
                from io import BytesIO

                from PIL import Image

                buf = BytesIO()
                Image.open(BytesIO(out)).save(buf, "WEBP", quality=84, method=5)
                out = buf.getvalue()
            n += 1
            before += size
            after += len(out)
            self.stdout.write(f"{name}: {size // 1024} KB → {len(out) // 1024} KB ({w}×{h})")
            if apply:
                tmp = path + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(out)
                os.replace(tmp, path)
                Media.objects.filter(pk=m.pk).update(width=w, height=h)
            if limit and n >= limit:
                break
        verb = "کم‌حجم شد" if apply else "کم‌حجم می‌شود (برای اعمال: --apply)"
        self.stdout.write(self.style.SUCCESS(
            f"{n} تصویر {verb}: {before // 1048576} MB → {after // 1048576} MB"))
