import os

from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

from core.models import Media

from ..auth import staff_required
from ..models import log

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".mp4"}
MAX_SIZE = 15 * 1024 * 1024


@staff_required
@require_POST
def upload(request):
    out, errors = [], []
    for f in request.FILES.getlist("file"):
        f: UploadedFile
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED:
            errors.append(f"{f.name}: این نوع فایل مجاز نیست.")
            continue
        if f.size > MAX_SIZE:
            errors.append(f"{f.name}: حجم بیش از ۱۵ مگابایت است.")
            continue
        w = h = None
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            try:
                with Image.open(f) as im:
                    w, h = im.size
                    im.verify()
            except Exception:  # noqa: BLE001
                errors.append(f"{f.name}: تصویر خراب است.")
                continue
            f.seek(0)
        title = os.path.splitext(f.name)[0][:500]
        try:
            m = Media.objects.create(file=f, title=title, alt=request.POST.get("alt", "")[:500], width=w, height=h,
                                     mime_type=(f.content_type or "")[:100])
        except OSError as e:
            errors.append(f"{f.name}: ذخیرهٔ فایل روی سرور ممکن نشد ({e.strerror}). دسترسی پوشهٔ uploads را بررسی کنید.")
            continue
        log(request, "create", "رسانه", m)
        out.append({"value": str(m.pk), "text": m.title, "url": m.url, "thumb": m.url})
    return JsonResponse({"files": out, "errors": errors}, status=200 if out or not errors else 400)
