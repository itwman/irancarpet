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


import difflib

GENERIC = {"فرش", "طرح", "نقشه", "زمینه", "برجسته", "بافت", "ممتاز", "تمام", "آکریلیک", "اکریلیک", "پلی", "استر", "ماشینی"}
FUZZY_MIN = .84


def _color(c):
    return re.sub(r"\s+", "", re.sub(r"\s*ای$", "", c or ""))   # «سرمه ای» و «سرمه» یکی‌اند


def key(row):
    """(واژه‌های نقشه به ترتیب الفبا، رنگ، شانه، بافت) — ترتیب واژه‌ها مهم نیست: «وینتیج ورساچه» = «ورساچه وینتیج»."""
    design, color, reeds, relief = parts(row)
    words = tuple(sorted(w for w in norm(design).split() if w not in GENERIC))
    return words, _color(color), reeds, relief


def _sim(a, b):
    """شباهت دو نقشه: زیرمجموعه (مثل «باغ ارم» و «باغ ارم VIP») ۰٫۹، وگرنه شباهت نویسه‌ای."""
    if not a or not b:
        return 0
    sa, sb = set(a), set(b)
    if (sa <= sb or sb <= sa) and len("".join(min(a, b, key=len))) >= 3:
        return .9
    return difflib.SequenceMatcher(None, "".join(a), "".join(b)).ratio()


def _live(r):
    return r.get("ss") == "available" and any(v[4] for v in r.get("v", []))


def legacy_products():
    from catalog.models import Product

    return Product.objects.published().filter(mirror__isnull=True, seller__isnull=True).order_by("pk")


def plan():
    """[(محصول قدیمی، ردیف منبع یا None، توضیح، بهترین نامزد برای بی‌جفت‌ها)]
    ترتیب: ۱) نقشه + رنگ + شانه دقیق ۲) اگر شانه یا رنگ در عنوان قدیمی نبود، بدون همان ۳) نقشهٔ نزدیک با رنگ و شانهٔ یکسان."""
    rows = get_json("/api/mirror/v1/stock/", {"all": "1"}, timeout=180)["products"]
    keyed = [(r, key(r)) for r in rows]
    full, by_cn, by_dn, by_dc = {}, {}, {}, {}
    for r, (d, c, n, rel) in keyed:
        if not d:
            continue
        full.setdefault((d, c, n), []).append((r, rel))
        by_cn.setdefault((c, n), []).append((r, rel, d))
        by_dn.setdefault((d, n), []).append((r, rel))
        by_dc.setdefault((d, c), []).append((r, rel))
    out, used = [], {}
    for p in legacy_products():
        d, c, n, rel = key({"t": p.title, "d": p.design_name})
        cands, why, best = None, "", None
        if d and c and n:
            cands, why = full.get((d, c, n)), "نقشه، رنگ و شانه یکی است"
        elif d and c:
            cands, why = by_dc.get((d, c)), "نقشه و رنگ یکی است (شانه در عنوان قدیمی نبود)"
        elif d and n:
            cands, why = by_dn.get((d, n)), "نقشه و شانه یکی است (رنگ در عنوان قدیمی نبود)"
        if not cands and d and c and n:
            scored = sorted(((_sim(d, d2), r, rel2, d2) for r, rel2, d2 in by_cn.get((c, n), [])), key=lambda x: -x[0])
            top = [x for x in scored if scored and x[0] == scored[0][0]]
            # چند نامزد هم‌امتیاز: اگر همه یک نقشه‌اند (مثلاً دو محصول از یک فرش)، بافت یکسان و موجود اول
            if top and top[0][0] >= FUZZY_MIN and len({x[3] for x in top}) == 1:
                top.sort(key=lambda x: (x[2] != rel, not _live(x[1]), x[1]["id"]))
                cands = [(top[0][1], top[0][2])]
                why = f"نقشهٔ نزدیک ({round(top[0][0] * 100)}٪)، رنگ و شانه یکی است"
            elif scored:
                best = scored[0][:2]
        if not cands:
            if best is None and d:  # برای گزارش: نزدیک‌ترین فرش با همان شانه، هر رنگی
                pool = [(_sim(d, d2), r) for r, (d2, c2, n2, _) in keyed if n2 == n and d2]
                best = max(pool, key=lambda x: x[0], default=None)
            out.append((p, None, "فرش هم‌نقشه و هم‌رنگ در ایران کارپت پیدا نشد", best))
            continue
        same = sorted([x for x in cands if x[1] == rel] or cands, key=lambda x: (not _live(x[0]), x[0]["id"]))
        r = same[0][0]
        if r["id"] in used:
            out.append((p, r, f"تکراری؛ همین فرش قبلاً با «{used[r['id']]}» جفت شد", None))
            continue
        used[r["id"]] = p.title
        out.append((p, r, why + ("" if len(same) == 1 else f" ({len(same)} گزینه؛ اولی انتخاب شد)"), None))
    return out


def report_csv(items):
    path = os.path.join(str(getattr(settings, "PRIVATE_ROOT", settings.BASE_DIR)), "mirror-match.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["شناسهٔ فرشستان", "عنوان فرشستان", "نشانی", "شناسهٔ ایران کارپت", "عنوان ایران کارپت", "نتیجه",
                    "نزدیک‌ترین فرش ایران کارپت (برای بی‌جفت‌ها)", "شباهت"])
        for p, r, why, best in items:
            w.writerow([p.pk, p.title, p.get_absolute_url(), r["id"] if r else "", r["t"] if r else "", why,
                        best[1]["t"] if best else "", f"{round(best[0] * 100)}٪" if best else ""])
    return path


def _unavailable(p):
    """کالای قدیمی بی‌جفت: صفحه می‌ماند (رتبهٔ گوگل) ولی ناموجود می‌شود؛ «خبرم کن» فعال است."""
    from catalog.models import Variation

    Variation.objects.filter(product=p).update(is_available=False)
    type(p).objects.filter(pk=p.pk).update(sale_status="unavailable")
    p.sale_status = "unavailable"
    p.refresh_price_cache()


def _redirect_to(p, target):
    """تکراری: همان فرش دو بار در فرشستان بود؛ دومی پیش‌نویس و ۳۰۱ به اولی."""
    from seo.models import Redirect

    _retire(p)
    Redirect.objects.filter(source=Redirect.normalize(p.get_absolute_url())).update(target=target.get_absolute_url())


@transaction.atomic
def apply(items):
    from catalog.models import Product

    matched = unavailable = merged = 0
    links = {lk.source_pk: lk for lk in MirrorLink.objects.select_related("product")}
    first = {}  # شناسهٔ منبع ← کالای قدیمی جفت‌شده
    for p, r, why, _best in items:
        if r is not None and not why.startswith("تکراری"):
            first[r["id"]] = p
    for p, r, why, _best in items:
        if r is None:
            _unavailable(p)
            unavailable += 1
            continue
        if why.startswith("تکراری"):
            _redirect_to(p, first.get(r["id"]) or p)
            merged += 1
            continue
        lk = links.get(r["id"])
        if lk and lk.product_id and lk.product_id != p.pk:
            # این فرش منبع قبلاً محصول جدا گرفته است؛ نشانی قدیمی به همان می‌رود
            _redirect_to(p, Product.objects.get(pk=lk.product_id))
            merged += 1
            continue
        lk = lk or MirrorLink(source_pk=r["id"])
        lk.product, lk.legacy, lk.source_title = p, True, r["t"][:300]
        lk.source_modified, lk.stock_hash, lk.synced_at = "", "", None   # همگام‌سازی بعدی کامل می‌گیرد
        lk.save()
        matched += 1
    return matched, unavailable, merged


def run(do_apply=False, out=print):
    s = MirrorSettings.load()
    if not s.is_target:
        out("اول در پنل ← تنظیمات ← همگام‌سازی کاتالوگ، نشانی منبع و کلید را وارد و «محصولات از سایت منبع گرفته شوند» را روشن کنید.")
        return None
    items = plan()
    ok = [x for x in items if x[1] is not None and not x[2].startswith("تکراری")]
    none = [x for x in items if x[1] is None]
    dup = [x for x in items if x[2].startswith("تکراری")]
    fuzzy = [x for x in ok if x[2].startswith("نقشهٔ نزدیک")]
    path = report_csv(items)
    out(f"کالاهای قدیمی فرشستان: {len(items)} · جفت‌شده: {len(ok)} (با نقشهٔ نزدیک: {len(fuzzy)}) · بی‌جفت: {len(none)} · تکراری: {len(dup)}")
    for p, r, why, _b in (fuzzy[:10] + [x for x in ok if x not in fuzzy][:4]):
        out(f"  ✔ {norm(p.title)}  ←  {norm(r['t'])}" + (f"  [{why}]" if why.startswith("نقشهٔ نزدیک") else ""))
    if none:
        out("نمونهٔ بی‌جفت‌ها (صفحه می‌ماند ولی ناموجود می‌شود) و نزدیک‌ترین فرش ایران کارپت:")
        for p, _r, _w, best in none[:15]:
            out(f"  ✖ {norm(p.title)}" + (f"   ~ {norm(best[1]['t'])} ({round(best[0] * 100)}٪)" if best else ""))
    out(f"فهرست کامل: {path}")
    if do_apply:
        ids = [r["id"] for _p, r, _w, _b in ok]
        for i in range(0, len(ids), 500):  # این فرش‌ها در ایران کارپت برای فرشستان انتخاب می‌شوند
            get_json("/api/mirror/v1/pick/", body={"ids": ids[i:i + 500]}, timeout=60)
        m, u, g = apply(items)
        out(f"اعمال شد: {m} جفت، {u} ناموجود (صفحه ماند)، {g} تکراری ۳۰۱ به فرش اصلی. "
            "همگام‌سازی بعدی عنوان، نامک، قیمت و موجودی جفت‌شده‌ها را از ایران کارپت می‌گیرد.")
    else:
        out("هنوز چیزی تغییر نکرده است. برای اعمال: manage.py mirror_match --apply")
    return items
