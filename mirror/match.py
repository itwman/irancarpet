"""مقصد: جفت کردن کالاهای قدیمی فرشستان با فرش‌های ایران کارپت (نقشه + رنگ زمینه + شانه).

جفت‌شده: همان محصول قدیمی (با نظرها، سفارش‌ها و علاقه‌مندی‌هایش) به فرش منبع وصل می‌شود؛ در همگام‌سازی بعدی عنوان و
نامک تازه می‌گیرد و نشانی قدیمی ۳۰۱ به نشانی تازه می‌رود.
بی‌جفت: پیش‌نویس می‌شود و نشانی‌اش ۳۰۱ به دستهٔ اصلی خودش (یا فروشگاه) می‌رود.
"""
import csv
import os
import re

from django.conf import settings
from django.db import transaction

from .client import get_json
from .models import MirrorLink, MirrorSettings
from .sync import _retire, norm, parts


def key(row):
    design, color, reeds, relief = parts(row)
    color = re.sub(r"\s*ای$", "", color)   # «سرمه ای» و «سرمه» یکی‌اند
    return re.sub(r"\s+", "", design), re.sub(r"\s+", "", color), reeds, relief


def legacy_products():
    from catalog.models import Product

    return Product.objects.published().filter(mirror__isnull=True, seller__isnull=True).order_by("pk")


def plan():
    """[(محصول قدیمی، ردیف منبع یا None، توضیح)]"""
    rows = get_json("/api/mirror/v1/stock/", {"all": "1"}, timeout=180)["products"]
    full, loose = {}, {}
    for r in rows:
        d, c, n, rel = key(r)
        if not d:
            continue
        full.setdefault((d, c, n), []).append((r, rel))
        loose.setdefault((d, c), []).append((r, rel))
    out, used = [], {}
    for p in legacy_products():
        d, c, n, rel = key({"t": p.title, "d": p.design_name})
        cands = full.get((d, c, n)) if n else loose.get((d, c))
        why = "نقشه، رنگ و شانه یکی است" if n else "نقشه و رنگ یکی است (شانه در عنوان قدیمی نبود)"
        if not cands:
            out.append((p, None, "فرش هم‌نقشه و هم‌رنگ در ایران کارپت پیدا نشد"))
            continue
        same = [x for x in cands if x[1] == rel] or cands
        r = same[0][0]
        if r["id"] in used:
            out.append((p, r, f"تکراری؛ همین فرش قبلاً با «{used[r['id']]}» جفت شد"))
            continue
        used[r["id"]] = p.title
        out.append((p, r, why + ("" if len(same) == 1 else f" ({len(same)} گزینه؛ اولی انتخاب شد)")))
    return out


def report_csv(items):
    path = os.path.join(str(getattr(settings, "PRIVATE_ROOT", settings.BASE_DIR)), "mirror-match.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["شناسهٔ فرشستان", "عنوان فرشستان", "نشانی", "شناسهٔ ایران کارپت", "عنوان ایران کارپت", "نتیجه"])
        for p, r, why in items:
            w.writerow([p.pk, p.title, p.get_absolute_url(), r["id"] if r else "", r["t"] if r else "", why])
    return path


@transaction.atomic
def apply(items):
    matched = retired = 0
    links = {lk.source_pk: lk for lk in MirrorLink.objects.select_related("product")}
    for p, r, why in items:
        if r is None or why.startswith("تکراری"):
            _retire(p)
            retired += 1
            continue
        lk = links.get(r["id"])
        if lk and lk.product_id and lk.product_id != p.pk:
            # این فرش منبع قبلاً محصول جدا گرفته است؛ نشانی قدیمی به همان می‌رود
            _retire(p)
            from seo.models import Redirect

            Redirect.objects.filter(source=Redirect.normalize(p.get_absolute_url())).update(target=lk.product.get_absolute_url())
            retired += 1
            continue
        lk = lk or MirrorLink(source_pk=r["id"])
        lk.product, lk.legacy, lk.source_title = p, True, r["t"][:300]
        lk.source_modified, lk.stock_hash, lk.synced_at = "", "", None   # همگام‌سازی بعدی کامل می‌گیرد
        lk.save()
        matched += 1
    return matched, retired


def run(do_apply=False, out=print):
    s = MirrorSettings.load()
    if not s.is_target:
        out("اول در پنل ← تنظیمات ← همگام‌سازی کاتالوگ، نشانی منبع و کلید را وارد و «محصولات از سایت منبع گرفته شوند» را روشن کنید.")
        return None
    items = plan()
    ok = [x for x in items if x[1] is not None and not x[2].startswith("تکراری")]
    none = [x for x in items if x[1] is None]
    dup = [x for x in items if x[2].startswith("تکراری")]
    path = report_csv(items)
    out(f"کالاهای قدیمی فرشستان: {len(items)} · جفت‌شده: {len(ok)} · بی‌جفت: {len(none)} · تکراری: {len(dup)}")
    for p, r, why in ok[:12]:
        out(f"  ✔ {norm(p.title)}  ←  {norm(r['t'])}")
    if none:
        out("نمونهٔ بی‌جفت‌ها (پیش‌نویس می‌شوند و ۳۰۱ به دسته‌شان می‌روند):")
        for p, _r, _w in none[:12]:
            out(f"  ✖ {norm(p.title)}")
    out(f"فهرست کامل: {path}")
    if do_apply:
        ids = [r["id"] for _p, r, why in ok]
        for i in range(0, len(ids), 500):  # این فرش‌ها در ایران کارپت برای فرشستان انتخاب می‌شوند
            get_json("/api/mirror/v1/pick/", body={"ids": ids[i:i + 500]}, timeout=60)
        m, r = apply(items)
        out(f"اعمال شد: {m} جفت، {r} پیش‌نویس با ۳۰۱. همگام‌سازی بعدی عنوان، نامک و قیمت جفت‌شده‌ها را از ایران کارپت می‌گیرد.")
    else:
        out("هنوز چیزی تغییر نکرده است. برای اعمال: manage.py mirror_match --apply")
    return items
