"""مقصد (فرشستان): گرفتن کاتالوگ از سایت منبع با عنوان، نامک، متن و عکس اختصاصی همین سایت.

هر نوبت (run_jobs، هر ۱۰ دقیقه):
۱. فهرست فشرده (قیمت، موجودی، فرصت ویژه) همهٔ فرش‌ها از منبع گرفته می‌شود.
۲. فرشی که فقط قیمت یا موجودی‌اش عوض شده، همان‌جا به‌روز می‌شود.
۳. فرش تازه یا ویرایش‌شده در منبع، با جزئیات کامل گرفته می‌شود (حداکثر «batch» فرش تازه در هر نوبت).
۴. فرشی که در منبع نیست، این‌جا پیش‌نویس می‌شود و نشانی‌اش ۳۰۱ به دسته‌اش می‌رود.
با «اعمال تغییرات» خاموش، فقط گزارش ساخته می‌شود و چیزی تغییر نمی‌کند.
"""
import io
import logging
import re
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .client import MirrorError, get_bytes, get_json
from .models import MirrorLink, MirrorMedia, MirrorSettings

log = logging.getLogger(__name__)
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
CHUNK = 30

COLOR_WORDS = sorted({
    "آبی", "اقیانوسی", "بنفش", "بژ", "ترمه ای", "ترمه", "تیتانیومی", "تیتانیوم", "دلفینی", "دودی", "روناسی", "زغالی", "سبز آبی", "سبزآبی",
    "سبز", "سربی", "سرمه ای", "سرمه", "سفید", "سیلور", "شکلاتی", "کرم صدفی", "صدفی", "طوسی", "فیلی", "قهوه ای", "لاکی",
    "قرمز", "متالیک", "مشکی", "موشی", "موکا", "نسکافه ای", "نقره ای", "کاربنی", "کرم", "یاسی", "گردویی", "گلبهی",
    "طلایی", "مسی", "یشمی", "فیروزه ای", "خاکستری", "استخوانی", "شیری", "عسلی", "بادمجانی", "زرشکی", "صورتی", "نارنجی",
}, key=len, reverse=True)


# ---------------------------------------------------------------- نام و عنوان
def norm(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").translate(_EN)
    s = re.sub(r"[\u064B-\u065F\u0670]", "", s)                 # اعراب (حوضِ ← حوض)
    s = re.sub(r"(?<=[^\d\s])(?=\d)|(?<=\d)(?=[^\d\s])", " ", s)  # زغالی1500 ← زغالی 1500
    return re.sub(r"\s+", " ", s).strip()


def _color_at(words, i):
    for n in (2, 1):
        w = " ".join(words[i:i + n])
        if len(words[i:i + n]) == n and w in COLOR_WORDS:
            return w, n
    return "", 0


def find_color(text):
    words = norm(text).split()
    for i in range(len(words)):
        c, _ = _color_at(words, i)
        if c:
            return c
    return ""


def _name(title):
    """نام نقشه و رنگ در عنوان: «فرش طرح فرح کرم حاشیه نقره ای 1200 شانه…» ← «فرح کرم حاشیه نقره ای»"""
    title = re.sub(r"(طرح|نقشه)\s+کد\s+(\d+)", r"\1 کد\2", title)   # «طرح کد 652 نقره ای» ← نقشهٔ «کد652»
    m = re.search(r"(?:طرح|نقشه)\s+(.+?)(?:\s+-\s+|\s+\d{3,4}\s*شانه|\s+(?:تمام|سایز|کد|تراکم)\s|\s+\d{3,4}\b|$)", title)
    if m:
        return m.group(1).strip()
    t = re.sub(r"^(?:تابلو\s*فرش|فرش)\s+", "", title)
    return re.split(r"\s+(?:کد|سایز)\s|\s+-\s+|\s+\d", t)[0].strip()


def parts(row):
    """(نقشه، رنگ، شانه، بافت) از دادهٔ منبع؛ اگر مشخصه‌ای خالی بود از عنوان خوانده می‌شود.
    نقشه = واژه‌های پیش از نخستین نام رنگ؛ رنگ = همان نخستین رنگ (رنگ زمینه)."""
    title = norm(row.get("t"))
    reeds = re.sub(r"\D", "", norm(row.get("r"))) or (re.search(r"(\d{3,4})\s*شانه", title) or [None, ""])[1]
    words = _name(title).split()
    design, color = " ".join(words), ""
    for i in range(len(words)):
        c, n = _color_at(words, i)
        if c and i > 0:
            design, color = " ".join(words[:i]), c
            break
    if row.get("d"):
        design = norm(row["d"])
    if row.get("c"):
        color = norm(row["c"])
    design = re.sub(r"\b(?:فرش|طرح|نقشه|زمینه|برجسته)\b", " ", design)
    design = re.sub(r"\s+", " ", design).strip()
    relief = "برجسته" if "برجسته" in title else ""
    return design, color, reeds, relief


def build_title(row, pattern):
    design, color, reeds, relief = parts(row)
    if not design:
        return re.sub(r"^فرش\s+(?:طرح|نقشه)\s+", "فرش ماشینی طرح ", norm(row.get("t")))[:300]
    t = pattern or MirrorSettings._meta.get_field("title_pattern").default
    if not color:
        t = re.sub(r"زمینه\s*\{رنگ\}", "", t)
    if not reeds:
        t = re.sub(r"\{شانه\}\s*شانه", "", t)
    for k, v in (("{نقشه}", design), ("{رنگ}", color), ("{شانه}", reeds), ("{بافت}", relief), ("{عنوان}", norm(row.get("t")))):
        t = t.replace(k, v)
    return re.sub(r"\s+", " ", t).strip()[:300]


def adj(price, s):
    """قیمت منبع ← قیمت این سایت (درصد و گرد کردن از پنل)."""
    if not price:
        return None
    pct = Decimal(s.price_percent or 0)
    if not pct:
        return int(price)
    r = max(1, int(s.round_to or 1))
    return int(round(Decimal(price) * (1 + pct / 100) / r) * r)


# ---------------------------------------------------------------- نگاشت داده‌های پایه
def _size(d):
    from pricing.models import Size

    sz = Size.objects.filter(slug=d["slug"]).first()
    if sz is None:
        sz = Size.objects.create(slug=d["slug"], label=d["label"], type=d.get("type") or "rect", width=Decimal(d.get("width") or 0),
                                 length=Decimal(d.get("length") or 0), diameter=Decimal(d.get("diameter") or 0),
                                 area=Decimal(d.get("area") or 0), default_pair_only=bool(d.get("pair")),
                                 needs_waste=bool(d.get("waste")), sort_order=d.get("order") or 0)
    return sz


def _category(d):
    from catalog.models import Category

    c = Category.objects.filter(slug=d["slug"]).first() or Category.objects.filter(name=d["name"]).first()
    if c is None:
        parent = Category.objects.filter(slug=d["parent"]).first() if d.get("parent") else None
        c = Category.objects.create(slug=d["slug"], name=d["name"], parent=parent)
    return c


def _term(d):
    from catalog.models import Attribute, AttributeTerm

    a = Attribute.objects.filter(slug=d["attr"]).first() or Attribute.objects.filter(label=d["label"]).first()
    if a is None:
        a = Attribute.objects.create(slug=d["attr"], label=d["label"], is_public=bool(d.get("public")),
                                     show_in_filters=bool(d.get("filter")))
    t = AttributeTerm.objects.filter(attribute=a, slug=d["slug"]).first() or AttributeTerm.objects.filter(attribute=a, name=d["name"]).first()
    if t is None:
        t = AttributeTerm.objects.create(attribute=a, slug=d["slug"], name=d["name"])
    return t


def _brand(d):
    from catalog.models import Brand

    if not d:
        return None
    b = Brand.objects.filter(slug=d["slug"]).first() or Brand.objects.filter(name=d["name"]).first()
    return b or Brand.objects.create(slug=d["slug"], name=d["name"])


def sync_albums(s):
    """آلبوم‌های منبع ← آلبوم‌های نمایشی این سایت (لیست قیمت). قیمت پایه صفر می‌ماند تا قیمت فرش‌ها از منبع بیاید."""
    from pricing.models import Album

    data = get_json("/api/mirror/v1/albums/", timeout=120)["albums"]
    seen = set()
    for d in data:
        seen.add(d["id"])
        a = Album.objects.filter(mirror_pk=d["id"]).first() or Album(mirror_pk=d["id"], base_price=0)
        for z in d.get("sizes", []):
            _size(z)
        a.base_size = _size(d["base_size"])
        a.name, a.company, a.public_name = d["name"][:160], d["company"][:120], d["public_name"][:160]
        code = d["code"] or f"ic{d['id']}"
        if Album.objects.filter(code=code).exclude(pk=a.pk).exists():
            code = f"ic-{code}"[:40]
        a.code = code
        slug = d["slug"]
        if slug:  # نامک صفحهٔ لیست قیمت؛ آلبوم قدیمی هم‌نام کنار می‌رود
            old = Album.objects.filter(slug=slug, mirror_pk__isnull=True).first()
            if old:
                Album.objects.filter(pk=old.pk).update(slug=f"{slug}-old-{old.pk}"[:160], is_active=False, in_price_list=False)
        a.slug, a.is_active, a.in_price_list, a.sort_order, a.embossed = slug, d["active"], d["in_list"], d["order"], d["embossed"]
        a.base_price = 0
        a.last_updated = parse_datetime(d["updated"]) or timezone.now()
        a.mirror_rows = [[slug_, adj(price, s), pair] for slug_, price, pair in d["rows"]]
        a.save()
    Album.objects.filter(mirror_pk__isnull=False).exclude(mirror_pk__in=seen).update(is_active=False)
    from pricing.pricelist import bump

    bump()
    return len(data)


def local_album(src_pk):
    from pricing.models import Album

    return Album.objects.filter(mirror_pk=src_pk).first() if src_pk else None


def _skip_set(s):
    return {norm(x) for x in (s.skip_categories or "").splitlines() if x.strip()}


def skipped(row, s):
    sk = _skip_set(s)
    return bool(sk) and any(norm(c["slug"]) in sk or norm(c["name"]) in sk for c in row.get("categories", []))


# ---------------------------------------------------------------- عکس
def local_media(img, title, slug, n):
    """عکس منبع ← نسخهٔ همین سایت: حاشیهٔ سفید بریده، اندازه و نام فایل تازه (فایل تکراری نیست)."""
    from PIL import Image, ImageChops, ImageOps

    from core.models import Media

    mm = MirrorMedia.objects.filter(source_pk=img["pk"]).select_related("media").first()
    if mm:
        return mm.media
    raw = get_bytes(img["url"])
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).convert("L").point(lambda x: 255 if x > 22 else 0).getbbox()
    if box:
        bw, bh = box[2] - box[0], box[3] - box[1]
        if bw * bh > im.width * im.height * .3:
            pad = int(max(bw, bh) * .025)
            box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
            im = im.crop(box)
    im.thumbnail((1600, 1600))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    now = timezone.localtime()
    path = default_storage.save(f"fs/{now:%Y/%m}/{slug[:70]}-{n}.jpg", ContentFile(buf.getvalue()))
    media = Media.objects.create(file=path, title=title[:500], alt=(title if n == 1 else f"{title} - عکس {n}")[:500],
                                 width=im.width, height=im.height, mime_type="image/jpeg")
    MirrorMedia.objects.create(source_pk=img["pk"], media=media)
    return media


# ---------------------------------------------------------------- قیمت، موجودی و فرصت ویژه
def apply_stock(p, link, row, s, sizes=None):
    """تنوع‌ها (قیمت از منبع، با درصد پنل) و فرصت‌های ویژه. اگر سایزی این‌جا نبود و sizes داده نشده، False."""
    from catalog.models import Variation
    from pricing.models import Size

    sizes = sizes or {}
    vmap, keep = {str(k): v for k, v in (link.vmap or {}).items()}, set()
    for vpk, sslug, final, sale, avail, qty, pair in row["v"]:
        size = None
        if sslug:
            size = Size.objects.filter(slug=sslug).first() or (_size(sizes[sslug]) if sslug in sizes else None)
            if size is None:
                return False
        v = (Variation.objects.filter(pk=vmap.get(str(vpk)), product=p).first()
             or (p.variations.filter(size=size).first() if size else None) or Variation(product=p, size=size))
        v.manual_price, v.override_price = adj(final, s), None
        v.sale_price = adj(sale, s) if sale else None
        v.is_available, v.stock_qty, v.pair_only = bool(avail), qty, pair
        v.save()
        vmap[str(vpk)] = v.pk
        keep.add(v.pk)
    p.variations.exclude(pk__in=keep).delete()
    link.vmap = {k: v for k, v in vmap.items() if v in keep}
    _apply_offers(p, link, row.get("o") or [], s)
    if p.sale_status != row["ss"]:
        type(p).objects.filter(pk=p.pk).update(sale_status=row["ss"])
        p.sale_status = row["ss"]
    alb = local_album(row.get("a"))
    if (alb.pk if alb else None) != p.album_id:
        type(p).objects.filter(pk=p.pk).update(album=alb)
        p.album = alb
    p.refresh_price_cache()
    link.stock_hash = row["h"]
    return True


def _apply_offers(p, link, rows, s):
    from pricing.models import Size
    from shop.models import SpecialOffer

    omap, live = {str(k): v for k, v in (link.omap or {}).items()}, set()
    for opk, sslug, price, regular, remaining, ends, starts in rows:
        size = Size.objects.filter(slug=sslug).first()
        if size is None:
            continue
        o = SpecialOffer.objects.filter(pk=omap.get(str(opk)), product=p).first() or SpecialOffer(product=p, size=size)
        sold = o.sold if o.pk else 0  # فروش همین سایت؛ باقی‌ماندهٔ واقعی را منبع می‌دهد
        o.size, o.fixed_price, o.base_price = size, adj(price, s), adj(regular, s)
        o.quantity = remaining + sold
        o.ends_at = parse_datetime(ends) if ends else None
        o.starts_at = parse_datetime(starts) or timezone.now()
        o.is_active = True
        o.note = o.note or "از ایران کارپت (همگام‌سازی)"
        o.save()
        omap[str(opk)] = o.pk
        live.add(o.pk)
    gone = [v for v in omap.values() if v not in live]
    if gone:
        SpecialOffer.objects.filter(pk__in=gone, product=p).update(is_active=False)
        from shop.offers import clear

        clear()
    link.omap = {k: v for k, v in omap.items() if v in live}


# ---------------------------------------------------------------- محصول کامل
def _retire(p, why=""):
    """محصول از فروش بیرون می‌رود: پیش‌نویس و ۳۰۱ نشانی‌اش به دستهٔ اصلی (یا فروشگاه)."""
    from seo.models import Redirect

    if p is None or p.status != "publish":
        return
    old = p.get_absolute_url()
    cat = p.primary_category or p.categories.first()
    target = cat.get_absolute_url() if cat else "/shop/"
    type(p).objects.filter(pk=p.pk).update(status="draft")
    src = Redirect.normalize(old)
    if src:
        Redirect.objects.update_or_create(source=src, match=Redirect.Match.EXACT, defaults={
            "target": target, "status_code": 301, "is_active": True, "origin": "mirror"})


@transaction.atomic
def apply_full(row, link, s):
    from catalog.models import Product, ProductImage
    from dashboard.ac import unique_slug
    from dashboard.views.crud import _redirect_old_url

    sizes = {d["slug"]: d for d in row.get("sizes", [])}
    p = link.product or Product()
    title = build_title(row, s.title_pattern)
    first_time = not link.synced_at
    old_url = p.get_absolute_url() if p.pk and p.status == "publish" else None
    if p.pk is None or (first_time and link.legacy):
        p.slug = unique_slug(Product, title)
    p.title = title
    p.design_name = norm(row.get("d"))[:120]
    p.english_name = (row.get("english_name") or "")[:300]
    p.color_count = row.get("color_count")
    p.video_url = row.get("video_url") or ""
    p.kind = row.get("kind") or p.kind
    p.status = "publish"
    p.sale_status = row["ss"]
    p.use_template = True       # متن از «قالب متن محصول» همین سایت؛ با منبع یکی نمی‌شود
    p.content = "" if p.pk is None else p.content
    p.album, p.custom_base_price, p.seller = local_album(row.get("a")), None, None
    p.brand = _brand(row.get("brand"))
    if p.pk is None:
        p.published_at = parse_datetime(row.get("published_at") or "") or timezone.now()
    p.modified_at = timezone.now()
    p.save()
    if old_url and old_url != p.get_absolute_url():
        _redirect_old_url(old_url, p)
    cats = [_category(c) for c in row.get("categories", [])]
    p.categories.set(cats)
    prim = next((c for c, d in zip(cats, row.get("categories", [])) if d["slug"] == row.get("primary_category")), None)
    if prim and p.primary_category_id != prim.pk:
        type(p).objects.filter(pk=p.pk).update(primary_category=prim)
        p.primary_category = prim
    p.specs.set([_term(t) for t in row.get("specs", [])])
    # عکس‌ها (اولی عکس اصلی)
    imgs = []
    for i, img in enumerate(row.get("images", [])[:8], 1):
        try:
            imgs.append(local_media(img, title, p.slug, i))
        except Exception as e:  # noqa: BLE001 — عکس خراب نباید کل فرش را نگه دارد
            log.warning("mirror image %s: %s", img.get("url"), e)
    if imgs:
        type(p).objects.filter(pk=p.pk).update(image=imgs[0])
        p.image = imgs[0]
        p.images.all().delete()
        ProductImage.objects.bulk_create([ProductImage(product=p, media=m, order=i) for i, m in enumerate(imgs[1:])])
    if not apply_stock(p, link, row, s, sizes):
        raise MirrorError("سایز فرش در منبع تعریف نشده است")
    link.product = p
    link.source_title = row["t"][:300]
    link.source_modified = row["m"]
    link.removed, link.error = False, ""
    link.synced_at = timezone.now()
    link.save()
    return p


# ---------------------------------------------------------------- یک نوبت
def run(report=None, out=None):
    """report=True: فقط گزارش. None: بر اساس «اعمال تغییرات» در پنل."""
    say = out or (lambda m: None)
    s = MirrorSettings.load()
    if not s.is_target:
        return None
    live = s.live if report is None else not report
    try:
        data = get_json("/api/mirror/v1/stock/", timeout=120)["products"]
    except MirrorError as e:
        s.last_result = {"error": str(e), "at": timezone.now().isoformat()}
        s.save(update_fields=["last_result"])
        say(f"خطا: {e}")
        return s.last_result
    if live:
        try:
            sync_albums(s)
        except MirrorError as e:
            say(f"آلبوم‌ها: {e}")
    links = {lk.source_pk: lk for lk in MirrorLink.objects.select_related("product")}
    seen, new, changed, stock = set(), [], [], []
    for row in data:
        seen.add(row["id"])
        lk = links.get(row["id"])
        if lk is None:
            new.append(row)
        elif lk.excluded:
            continue
        elif lk.removed or lk.product_id is None or lk.source_modified != row["m"]:
            changed.append(row)
        elif lk.stock_hash != row["h"]:
            stock.append(row)
    removed = [lk for pk, lk in links.items() if pk not in seen and not lk.removed and not lk.excluded and lk.product_id]
    res = {"at": timezone.now().isoformat(), "live": live, "source": len(data), "new": len(new), "changed": len(changed),
           "stock": len(stock), "removed": len(removed), "done": 0, "errors": 0,
           "sample_new": [build_title(r, s.title_pattern) for r in new[:8]],
           "sample_removed": [lk.source_title for lk in removed[:8]]}
    say(f"منبع: {len(data)} فرش · تازه: {len(new)} · ویرایش‌شده: {len(changed)} · فقط قیمت/موجودی: {len(stock)} · حذف‌شده در منبع: {len(removed)}")
    if live:
        for row in stock:
            lk = links[row["id"]]
            try:
                with transaction.atomic():
                    if apply_stock(lk.product, lk, row, s):
                        lk.synced_at = timezone.now()
                        lk.save(update_fields=["vmap", "omap", "stock_hash", "synced_at"])
                        res["done"] += 1
                    else:
                        changed.append(row)  # سایز تازه: با جزئیات کامل
            except Exception as e:  # noqa: BLE001
                res["errors"] += 1
                MirrorLink.objects.filter(pk=lk.pk).update(error=str(e)[:300])
                log.exception("mirror stock %s", row["id"])
        todo = changed + new[: max(0, s.batch)]
        rows_by_id = {r["id"]: r for r in todo}
        for i in range(0, len(todo), CHUNK):
            ids = [r["id"] for r in todo[i:i + CHUNK]]
            try:
                fulls = get_json("/api/mirror/v1/products/", {"ids": ",".join(map(str, ids))}, timeout=120)["products"]
            except MirrorError as e:
                res["errors"] += 1
                say(f"خطا: {e}")
                break
            for row in fulls:
                lk = links.get(row["id"]) or MirrorLink(source_pk=row["id"])
                try:
                    if lk.pk is None and skipped(row, s):
                        lk.excluded, lk.source_title = True, row["t"][:300]
                        lk.save()
                        continue
                    apply_full(row, lk, s)
                    res["done"] += 1
                except Exception as e:  # noqa: BLE001
                    res["errors"] += 1
                    lk.error = str(e)[:300]
                    lk.source_title = rows_by_id.get(row["id"], row)["t"][:300]
                    if lk.pk:
                        MirrorLink.objects.filter(pk=lk.pk).update(error=lk.error)
                    log.exception("mirror full %s", row["id"])
        for lk in removed:
            _retire(lk.product)
            MirrorLink.objects.filter(pk=lk.pk).update(removed=True, synced_at=timezone.now())
        if res["done"] or removed:
            from dashboard.auth import clear_site_cache

            clear_site_cache()
        say(f"اعمال شد: {res['done']} · خطا: {res['errors']}" + (f" · {max(0, len(new) - s.batch)} فرش تازه برای نوبت بعد ماند" if len(new) > s.batch else ""))
    s.last_sync_at = timezone.now()
    s.last_result = res
    s.save(update_fields=["last_sync_at", "last_result"])
    return res
