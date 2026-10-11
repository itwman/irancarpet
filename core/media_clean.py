"""رسانه‌های بی‌استفاده: پیدا کردن، انتقال به سطل بازیافت (۳۰ روز) و برگرداندن.

«استفاده‌شده» یعنی یکی از این‌ها:
  - هر فیلد ForeignKey / ManyToMany هر مدلی که به رسانه اشاره می‌کند (تصویر و گالری فرش، تصویر مقاله، تنظیمات، …)
  - هر FileField/ImageField دیگر (عکس نظرها و …)
  - نام فایل در هر متن پایگاه داده (متن مقاله‌ها و برگه‌ها و فرش‌ها، توضیح دسته‌ها، JSON تنظیمات، صفحه‌های فرود، …)؛
    نسخه‌های کوچک‌شدهٔ وردپرس (مثل -768x1024) هم به فایل اصلی نسبت داده می‌شوند.
فقط پوشه‌های سال/ماه (مثل 2021/05) بررسی می‌شوند؛ فایل‌های ساخته‌شدهٔ خود سایت (app-thumbs، rajyar و …) دست نمی‌خورند.
فایل‌هایی که کمتر از ۷ روز پیش آپلود شده‌اند هم کنار گذاشته می‌شوند (شاید هنوز در حال استفاده باشند).
"""
import json
import logging
import os
import re
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import unquote

from django.apps import apps
from django.conf import settings
from django.db import models
from django.utils import timezone

log = logging.getLogger(__name__)
EXT = r"(?:jpe?g|png|webp|gif|svg|pdf|mp4|avif)"
REF_RE = re.compile(r"(?:wp-content/uploads/|app-img/\d+/)([^\s\"'<>()?#\\]+?\." + EXT + r")", re.I)
SIZE_RE = re.compile(r"-\d{2,5}x\d{2,5}(?=\.[A-Za-z0-9]+$)")
YEAR_DIR = re.compile(r"^\d{4}/\d{2}/")
SKIP_MODELS = {"sessions.session", "stats.hit", "stats.dailypage", "admin.logentry", "dashboard.activitylog", "crm.smslog",
               "crm.shortlink", "growth.searchlog", "contenttypes.contenttype", "auth.permission", "core.trashedfile"}
SKIP_APPS = {"stats", "sessions", "admin", "contenttypes"}
MIN_AGE_DAYS = 7
TRASH_DAYS = 30


def root():
    return Path(settings.MEDIA_ROOT)


def trash_root():
    return Path(settings.PRIVATE_ROOT) / "media-trash"


def state_file():
    return Path(settings.PRIVATE_ROOT) / "media-scan.json"


def base_of(rel):
    """نسخهٔ کوچک‌شدهٔ وردپرس ← فایل اصلی: 2020/03/a-768x1024.jpg ← 2020/03/a.jpg"""
    return SIZE_RE.sub("", rel)


def referenced():
    """(شناسه‌های رسانهٔ استفاده‌شده، مسیرهای دقیق، مسیرهای پایه)"""
    from .models import Media

    ids, exact = set(), set()
    for model in apps.get_models():
        label = model._meta.label_lower
        if label in SKIP_MODELS or model is Media or model._meta.app_label in SKIP_APPS:
            continue
        for f in model._meta.get_fields():
            try:
                if f.is_relation and f.related_model is Media and (f.many_to_one or f.one_to_one) and f.concrete:
                    ids |= set(model.objects.exclude(**{f.attname: None}).values_list(f.attname, flat=True))
                elif f.is_relation and f.related_model is Media and f.many_to_many and f.concrete:
                    ids |= {x for x in model.objects.values_list(f.name, flat=True) if x}
                elif isinstance(f, models.FileField):
                    exact |= {x for x in model.objects.exclude(**{f.name: ""}).values_list(f.name, flat=True) if x}
                elif isinstance(f, (models.TextField, models.JSONField)) or (isinstance(f, models.CharField) and (f.max_length or 0) >= 100):
                    qs = model.objects.all()
                    if not isinstance(f, models.JSONField):
                        qs = qs.filter(**{f"{f.name}__icontains": "."})
                    for v in qs.values_list(f.name, flat=True).iterator(chunk_size=500):
                        if not v:
                            continue
                        text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                        if "uploads/" in text or "app-img/" in text:
                            exact |= {unquote(m) for m in REF_RE.findall(text)}
            except Exception:  # noqa: BLE001  (جدول اختیاری یا فیلد خاص)
                log.debug("media refs %s.%s", label, getattr(f, "name", "?"), exc_info=True)
    tpl = Path(settings.BASE_DIR) / "templates"
    for p in list(tpl.rglob("*.html")) + list((Path(settings.BASE_DIR) / "static").rglob("*.css")):
        try:
            exact |= {unquote(m) for m in REF_RE.findall(p.read_text(encoding="utf-8", errors="ignore"))}
        except OSError:
            pass
    return ids, exact, {base_of(x) for x in exact}


def scan():
    """فهرست رسانه‌ها و فایل‌های بی‌استفاده با حجمشان (برای صفحهٔ پنل)."""
    from .models import Media

    ids, exact, bases = referenced()
    r = root()
    now = time.time()
    min_age = now - MIN_AGE_DAYS * 86400
    media_files = {}
    unused_media = []
    for m in Media.objects.values("pk", "file", "title", "created_at").iterator(chunk_size=2000):
        rel = m["file"] or ""
        media_files[rel] = m["pk"]
        if m["pk"] in ids or rel in exact or rel in bases:
            continue
        created = m["created_at"].timestamp() if m["created_at"] else 0
        if created and created > min_age:
            continue
        p = r / rel
        size = p.stat().st_size if p.is_file() else 0
        if p.is_file() and p.stat().st_mtime > min_age and not created:
            continue
        unused_media.append({"id": m["pk"], "path": rel, "title": m["title"] or os.path.basename(rel), "size": size})
    orphans = []
    if r.is_dir():
        for dirpath, _dirs, files in os.walk(r):
            rel_dir = os.path.relpath(dirpath, r).replace(os.sep, "/")
            if not YEAR_DIR.match(rel_dir + "/"):
                continue
            for name in files:
                rel = f"{rel_dir}/{name}"
                if rel in media_files or rel in exact:
                    continue
                try:
                    st = os.stat(os.path.join(dirpath, name))
                except OSError:
                    continue
                if st.st_mtime > min_age:
                    continue
                orphans.append({"path": rel, "size": st.st_size, "variant_of": base_of(rel) if base_of(rel) != rel else ""})
    unused_media.sort(key=lambda x: -x["size"])
    orphans.sort(key=lambda x: -x["size"])
    return {"media": unused_media, "orphans": orphans,
            "media_size": sum(x["size"] for x in unused_media), "orphans_size": sum(x["size"] for x in orphans),
            "referenced": len(ids) + len(exact)}


# ------------------------------------------------------------------ اجرا در پس‌زمینه
def read_state():
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(d):
    f = state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def start_scan():
    st = read_state()
    if st.get("running") and time.time() - st.get("started", 0) < 1800:
        return False
    _write_state({**st, "running": True, "started": time.time()})

    def run():
        from django.db import close_old_connections

        close_old_connections()
        try:
            res = scan()
            _write_state({"running": False, "done": time.time(), **res})
        except Exception as e:  # noqa: BLE001
            log.exception("media scan")
            _write_state({"running": False, "error": str(e)[:300]})
        finally:
            close_old_connections()

    threading.Thread(target=run, daemon=True).start()
    return True


# ------------------------------------------------------------------ سطل بازیافت
def _drop_thumbs(rel):
    for d in (root() / "app-thumbs").glob("*"):
        t = d / (rel + ".webp")
        if t.is_file():
            try:
                t.unlink()
            except OSError:
                pass


def trash(paths, media_ids, user=None):
    """انتقال به سطل بازیافت؛ پیش از انتقال دوباره بررسی می‌شود که هنوز استفاده نشده باشند."""
    from .models import Media, TrashedFile

    ids, exact, bases = referenced()
    moved, skipped = 0, 0
    items = [(m.file.name, m) for m in Media.objects.filter(pk__in=media_ids)] + [(p, None) for p in paths]
    # نسخه‌های کوچک‌شدهٔ وردپرس هر رسانهٔ بی‌استفاده هم (اگر جایی استفاده نشده‌اند) همراهش می‌روند
    extra = []
    for rel, m in items:
        if m is None or not rel:
            continue
        folder = (root() / rel).parent
        stem, ext = os.path.splitext(os.path.basename(rel))
        if folder.is_dir():
            for f in folder.glob(f"{stem}-*x*{ext}"):
                v = f"{os.path.dirname(rel)}/{f.name}"
                if base_of(v) == rel and v not in exact and v not in paths:
                    extra.append((v, None))
    items += extra
    for rel, m in items:
        rel = (rel or "").lstrip("/")
        if not rel or ".." in rel or not YEAR_DIR.match(rel):
            skipped += 1
            continue
        if (m is not None and m.pk in ids) or rel in exact or (m is not None and rel in bases):
            skipped += 1
            continue
        src = root() / rel
        dst = trash_root() / rel
        data = None
        if m is not None:
            data = {"pk": m.pk, "file": m.file.name, "title": m.title, "alt": m.alt, "caption": m.caption, "width": m.width,
                    "height": m.height, "mime_type": m.mime_type, "wp_id": m.wp_id,
                    "created_at": m.created_at.isoformat() if m.created_at else None}
        size = src.stat().st_size if src.is_file() else 0
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        _drop_thumbs(rel)
        TrashedFile.objects.create(path=rel, size=size, media=data, by=user if getattr(user, "pk", None) else None)
        if m is not None:
            Media.objects.filter(pk=m.pk).delete()
        moved += 1
    st = read_state()
    if st:
        gone = set(paths) | {r for r, _ in items}
        st["media"] = [x for x in st.get("media", []) if x["path"] not in gone]
        st["orphans"] = [x for x in st.get("orphans", []) if x["path"] not in gone]
        st["media_size"] = sum(x["size"] for x in st["media"])
        st["orphans_size"] = sum(x["size"] for x in st["orphans"])
        _write_state(st)
    return moved, skipped


def restore(pks):
    from datetime import datetime

    from .models import Media, TrashedFile

    n = 0
    for t in TrashedFile.objects.filter(pk__in=pks):
        src, dst = trash_root() / t.path, root() / t.path
        if src.is_file() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        if t.media and not Media.objects.filter(file=t.path).exists():
            d = dict(t.media)
            created = d.pop("created_at", None)
            pk = d.pop("pk", None)
            if pk and Media.objects.filter(pk=pk).exists():
                pk = None
            if d.get("wp_id") and Media.objects.filter(wp_id=d["wp_id"]).exists():
                d["wp_id"] = None
            Media.objects.create(pk=pk, created_at=datetime.fromisoformat(created) if created else None, **d)
        t.delete()
        n += 1
    return n


def purge(now=None):
    """فایل‌های بیش از ۳۰ روز در سطل بازیافت برای همیشه پاک می‌شوند."""
    from .models import TrashedFile

    cutoff = (now or timezone.now()) - timezone.timedelta(days=TRASH_DAYS)
    n = 0
    for t in TrashedFile.objects.filter(trashed_at__lt=cutoff)[:2000]:
        p = trash_root() / t.path
        try:
            if p.is_file():
                p.unlink()
        except OSError:
            continue
        t.delete()
        n += 1
    return n
