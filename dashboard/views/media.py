import os

from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image

from django.conf import settings

from core.models import Media

from ..auth import staff_required
from ..models import log

ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".mp4"}
MAX_SIZE = 19 * 1024 * 1024  # محدودیت nginx ۲۰ مگابایت؛ بعد از آپلود کم‌حجم می‌شود


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
            errors.append(f"{f.name}: حجم بیش از ۱۹ مگابایت است.")
            continue
        w = h = None
        title = os.path.splitext(f.name)[0][:500]
        mime = (f.content_type or "")[:100]
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            try:
                with Image.open(f) as im:
                    w, h = im.size
                    im.verify()
            except Exception:  # noqa: BLE001
                errors.append(f"{f.name}: تصویر خراب است.")
                continue
            f.seek(0)
            from core.images import optimize_upload

            f, w2, h2 = optimize_upload(f)  # کم‌حجم: ضلع حداکثر ۲۴۰۰، زیر ۷۰۰ کیلوبایت، بدون دفرمه شدن
            w, h = w2 or w, h2 or h
            if f.name.lower().endswith(".jpg"):
                mime = "image/jpeg"
        try:
            m = Media.objects.create(file=f, title=title, alt=request.POST.get("alt", "")[:500], width=w, height=h,
                                     mime_type=mime)
        except OSError as e:
            errors.append(f"{f.name}: ذخیرهٔ فایل روی سرور ممکن نشد ({e.strerror}). دسترسی پوشهٔ uploads را بررسی کنید.")
            continue
        log(request, "create", "رسانه", m)
        out.append({"value": str(m.pk), "text": m.title, "url": m.url, "thumb": m.url})
    return JsonResponse({"files": out, "errors": errors}, status=200 if out or not errors else 400)


@staff_required
def library(request):
    """کتابخانهٔ رسانه برای پنجرهٔ انتخاب تصویر: ۳۰ مورد در هر صفحه، جدیدترین اول، با جستجو."""
    from django.db.models import Q

    from core.templatetags.fa import thumb

    q = (request.GET.get("q") or "").strip()[:100]
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    qs = Media.objects.filter(Q(mime_type__startswith="image/") | Q(mime_type="") | Q(file__iregex=r"\.(jpe?g|png|webp|gif)$"))
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(alt__icontains=q) | Q(file__icontains=q))
    qs = qs.order_by("-created_at", "-pk")
    per = 30
    rows = list(qs[(page - 1) * per: page * per + 1])
    items = [{"value": str(m.pk), "text": m.title or os.path.basename(m.file.name), "url": m.url, "thumb": thumb(m, 240),
              "alt": m.alt or m.title, "w": m.width, "h": m.height} for m in rows[:per]]
    return JsonResponse({"items": items, "more": len(rows) > per})


@staff_required
def unused(request):
    """رسانه‌ها و فایل‌های بی‌استفاده، و سطل بازیافت."""
    from django.contrib import messages
    from django.core.paginator import Paginator
    from django.shortcuts import redirect, render

    from core import media_clean as mc
    from core.models import TrashedFile
    from core.templatetags.fa import fa_num

    if request.method == "POST":
        do = request.POST.get("do")
        if do == "scan":
            if mc.start_scan():
                messages.success(request, "بررسی شروع شد؛ چند دقیقه بعد صفحه را تازه کنید.")
            else:
                messages.info(request, "بررسی قبلی هنوز در حال انجام است.")
        elif do in ("trash", "trash_all_media", "trash_all_orphans"):
            st = mc.read_state()
            if do == "trash":
                paths = request.POST.getlist("path")
                ids = [int(x) for x in request.POST.getlist("media") if x.isdigit()]
            elif do == "trash_all_media":
                paths, ids = [], [x["id"] for x in st.get("media", [])]
            else:
                paths, ids = [x["path"] for x in st.get("orphans", [])], []
            moved, skipped = mc.trash(paths, ids, request.user)
            log(request, "delete", "رسانه‌های بی‌استفاده", f"{moved} فایل به سطل بازیافت")
            messages.success(request, f"{fa_num(moved)} فایل به سطل بازیافت رفت" + (f"؛ {fa_num(skipped)} فایل استفاده‌شده بود و ماند." if skipped else "."))
        elif do == "restore":
            n = mc.restore([int(x) for x in request.POST.getlist("trashed") if x.isdigit()])
            messages.success(request, f"{fa_num(n)} فایل برگشت.")
        return redirect(request.path + ("?tab=trash" if do == "restore" else ""))
    st = mc.read_state()
    tab = request.GET.get("tab") or "media"
    rows = st.get("orphans" if tab == "orphans" else "media", []) if tab != "trash" else []
    page = Paginator(rows, 60).get_page(request.GET.get("page"))
    trash = Paginator(TrashedFile.objects.all(), 60).get_page(request.GET.get("page")) if tab == "trash" else None
    from django.db.models import Count, Sum

    tsum = TrashedFile.objects.aggregate(n=Count("pk"), s=Sum("size"))
    return render(request, "dashboard/media_unused.html", {
        "st": st, "tab": tab, "page": page, "trash": trash, "tsum": tsum, "trash_days": mc.TRASH_DAYS,
        "media_url": settings.MEDIA_URL, "tab_qs": f"tab={tab}",
    })
