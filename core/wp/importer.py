"""ایمپورت کامل وردپرس/ووکامرس به جنگو.

idempotent است: هر رکورد با wp_id شناسایی می‌شود و اجرای دوباره فقط به‌روزرسانی می‌کند.
"""
import re
import statistics
import zlib
from collections import Counter, defaultdict
from decimal import Decimal
from urllib.parse import unquote

from django.conf import settings
from django.db import transaction

from blog.models import BlogCategory, BlogTag, Comment, Faq, Page, Post
from catalog.models import (
    Attribute, AttributeTerm, Brand, Category, Product, ProductImage, ProductTag, Review, Variation,
)
from core.models import Media, SiteSettings
from core.utils.php import as_list, php_unserialize
from pricing.models import Album, PricingSettings, Size, _num, seed_sizes
from seo.models import Redirect

from .html import clean_content
from .reader import WPReader, robots_from_meta, slug, wp_datetime

SEO_KEYS = ["rank_math_title", "rank_math_description", "rank_math_focus_keyword", "rank_math_robots", "rank_math_canonical_url"]
SKIP_SPEC_ATTRS = {"carpet-size", "width", "length"}


def seo_fields(meta):
    return {
        "seo_title": (meta.get("rank_math_title") or "")[:300],
        "seo_description": meta.get("rank_math_description") or "",
        "focus_keyword": (meta.get("rank_math_focus_keyword") or "")[:300],
        "robots": robots_from_meta(meta.get("rank_math_robots")),
        "canonical_url": (meta.get("rank_math_canonical_url") or "")[:500],
    }


def to_int(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def to_dec(v, default=None):
    try:
        return Decimal(str(v).strip())
    except Exception:  # noqa: BLE001
        return default


def norm_name(name):
    s = (name or "").replace("ي", "ی").replace("ك", "ک").replace("‌", "")
    s = re.sub(r"فرش|[0-9۰-۹\s\-_]", "", s)
    return s


def upsert(model, rows, fields=None, key="wp_id"):
    """درج یا به‌روزرسانی انبوه بر اساس wp_id. خروجی: {wp_id: pk}"""
    if not rows:
        return {}
    keys = [r[key] for r in rows]
    existing = {}
    for i in range(0, len(keys), 2000):
        existing.update(model.objects.filter(**{f"{key}__in": keys[i:i + 2000]}).values_list(key, "pk"))
    new, upd = [], []
    for r in rows:
        obj = model(**r)
        if r[key] in existing:
            obj.pk = existing[r[key]]
            upd.append(obj)
        else:
            new.append(obj)
    model.objects.bulk_create(new, batch_size=500)
    if upd:
        fields = fields or [f for f in rows[0] if f != key]
        model.objects.bulk_update(upd, fields, batch_size=500)
    result = {}
    for i in range(0, len(keys), 2000):
        result.update(model.objects.filter(**{f"{key}__in": keys[i:i + 2000]}).values_list(key, "pk"))
    return result


def set_m2m(through, owner_field, target_field, pairs, owner_ids):
    """جایگزینی کامل روابط چندبه‌چند برای مالکان داده‌شده."""
    owner_ids = list(owner_ids)
    for i in range(0, len(owner_ids), 2000):
        through.objects.filter(**{f"{owner_field}__in": owner_ids[i:i + 2000]}).delete()
    seen, objs = set(), []
    for o, t in pairs:
        if (o, t) in seen or o is None or t is None:
            continue
        seen.add((o, t))
        objs.append(through(**{owner_field: o, target_field: t}))
    through.objects.bulk_create(objs, batch_size=2000)


class Importer:
    def __init__(self, alias="wp", prefix="wp_", log=print):
        self.wp = WPReader(alias, prefix)
        self.log = log
        self.site = settings.SITE_URL.rstrip("/")
        self.media_map = {}
        self.report = Counter()

    # ------------------------------------------------------------------ util
    def media_pk(self, wp_id):
        wp_id = to_int(wp_id)
        if not wp_id:
            return None
        if not self.media_map:
            self.media_map = dict(Media.objects.exclude(wp_id=None).values_list("wp_id", "pk"))
        return self.media_map.get(wp_id)

    def relative_url(self, url):
        url = (url or "").strip()
        for prefix in (self.site, self.site.replace("https://", "http://"), self.site.replace("://", "://www.")):
            if url.startswith(prefix):
                return url[len(prefix):] or "/"
        return url

    # ------------------------------------------------------------ settings
    def import_settings(self):
        s = SiteSettings.load()
        s.site_name = self.wp.option("blogname") or s.site_name
        s.tagline = self.wp.option("blogdescription") or ""
        titles = php_unserialize(self.wp.option("rank-math-options-titles"), default={}) or {}
        templates = {k: v for k, v in titles.items() if isinstance(v, str) and (k.endswith("_title") or k.endswith("_description"))}
        s.title_templates = templates
        s.title_separator = titles.get("title_separator") or "-"
        s.home_title = titles.get("homepage_title", "")
        s.home_description = titles.get("homepage_description", "")
        mods = php_unserialize(self.wp.option("theme_mods_IranCarpet-theme"), default={}) or {}
        if isinstance(mods, dict):
            s.phone = s.phone or (mods.get("irancarpet_phone") or "")
            s.whatsapp = s.whatsapp or re.sub(r"\D", "", str(mods.get("irancarpet_whatsapp") or ""))
            s.email = s.email or (mods.get("irancarpet_email") or "")
            s.address = s.address or (mods.get("irancarpet_address") or "")
            if not s.trust_points:
                s.trust_points = [
                    [mods[f"irancarpet_strip_{i}_fa"], mods.get(f"irancarpet_strip_{i}_en") or ""]
                    for i in range(1, 5) if mods.get(f"irancarpet_strip_{i}_fa")
                ]
        s.save()
        PricingSettings.load()
        self.log(f"تنظیمات سایت: {len(templates)} قالب عنوان")

    # --------------------------------------------------------------- media
    def import_media(self):
        posts = self.wp.posts("attachment", ("inherit", "publish"))
        meta = self.wp.postmeta([p["ID"] for p in posts], ["_wp_attached_file", "_wp_attachment_image_alt", "_wp_attachment_metadata"])
        rows = []
        for p in posts:
            m = meta.get(p["ID"], {})
            path = m.get("_wp_attached_file") or ""
            if not path and "/uploads/" in (p["guid"] or ""):
                path = unquote(p["guid"].split("/uploads/", 1)[1])
            if not path:
                continue
            md = php_unserialize(m.get("_wp_attachment_metadata"), default={}) or {}
            rows.append(dict(
                wp_id=p["ID"], file=path[:500], title=(p["post_title"] or "")[:500],
                alt=(m.get("_wp_attachment_image_alt") or "")[:500], caption=p["post_excerpt"] or "",
                width=to_int(md.get("width")), height=to_int(md.get("height")),
                mime_type=(p["post_mime_type"] or "")[:100],
                created_at=wp_datetime(p["post_date_gmt"], p["post_date"]),
            ))
        self.media_map = upsert(Media, rows)
        self.log(f"رسانه: {len(rows)}")

    # ------------------------------------------------------------- taxonomy
    def import_categories(self):
        terms = self.wp.terms("product_cat")
        tmeta = self.wp.termmeta([t["term_id"] for t in terms])
        rows = []
        for t in terms:
            m = tmeta.get(t["term_id"], {})
            rows.append(dict(
                wp_id=t["term_id"], name=t["name"], slug=slug(t["slug"]), description=clean_content(t["description"]),
                image_id=self.media_pk(m.get("thumbnail_id")), order=to_int(m.get("order"), 0), **seo_fields(m),
            ))
        # ابتدا بدون والد (برای جلوگیری از تداخل unique_together)
        mapping = upsert(Category, rows)
        parents = [Category(pk=mapping[t["term_id"]], parent_id=mapping.get(t["parent"])) for t in terms]
        Category.objects.bulk_update(parents, ["parent"])
        self.cat_map = mapping
        self.log(f"دسته‌های محصول: {len(rows)}")

    def import_product_tags(self):
        terms = self.wp.terms("product_tag")
        tmeta = self.wp.termmeta([t["term_id"] for t in terms])
        rows = [dict(wp_id=t["term_id"], name=t["name"], slug=slug(t["slug"]), description=clean_content(t["description"]),
                     **seo_fields(tmeta.get(t["term_id"], {}))) for t in terms]
        self.tag_map = upsert(ProductTag, rows)
        self.log(f"برچسب‌های محصول: {len(rows)}")

    def import_brands(self):
        """برندهای product_brand اصلی‌اند؛ مقادیر pa_brand در آن‌ها ادغام می‌شوند."""
        main = self.wp.terms("product_brand")
        extra = self.wp.terms("pa_brand")
        tmeta = self.wp.termmeta([t["term_id"] for t in main + extra])
        rows, by_norm = [], {}
        for t in sorted(main, key=lambda x: -x["count"]):
            rows.append(dict(wp_id=t["term_id"], name=t["name"].strip(), slug=slug(t["slug"]),
                             description=clean_content(t["description"]), **seo_fields(tmeta.get(t["term_id"], {}))))
            by_norm.setdefault(norm_name(t["name"]), t["term_id"])
        used_slugs = {r["slug"] for r in rows}
        self.brand_alias = {}  # pa_brand term_id → product_brand term_id
        for t in extra:
            target = by_norm.get(norm_name(t["name"]))
            if target:
                self.brand_alias[t["term_id"]] = target
                continue
            s = slug(t["slug"])
            if s in used_slugs:
                s = f"{s}-{t['term_id']}"
            used_slugs.add(s)
            rows.append(dict(wp_id=t["term_id"], name=re.sub(r"\d+$", "", t["name"]).strip(), slug=s,
                             description="", **seo_fields(tmeta.get(t["term_id"], {}))))
            by_norm[norm_name(t["name"])] = t["term_id"]
        self.brand_map = upsert(Brand, rows)
        for alias, target in self.brand_alias.items():
            self.brand_map[alias] = self.brand_map[target]
        # ریدایرکت آدرس‌های برند تکراری به برند اصلی
        brands = {b.pk: b for b in Brand.objects.all()}
        for t in extra:
            if t["term_id"] in self.brand_alias:
                b = brands[self.brand_map[t["term_id"]]]
                old = slug(t["slug"])
                if old != b.slug:
                    self.add_redirect(f"brand/{old}", b.get_absolute_url(), "brand_merge")
        self.log(f"برندها: {Brand.objects.count()} (ادغام {len(self.brand_alias)} تکراری)")

    def import_attributes(self):
        attrs = self.wp.rows("SELECT * FROM {p}woocommerce_attribute_taxonomies ORDER BY attribute_id")
        public_slugs = set()
        rows = []
        for i, a in enumerate(attrs):
            public = bool(int(a["attribute_public"]))
            rows.append(dict(wp_id=a["attribute_id"], slug=a["attribute_name"], label=a["attribute_label"],
                             is_public=public, order=i, show_in_filters=a["attribute_name"] not in SKIP_SPEC_ATTRS))
            if public:
                public_slugs.add(a["attribute_name"])
        amap = upsert(Attribute, rows)
        self.term_map, self.term_slug_map = {}, {}
        total = 0
        for a in attrs:
            terms = self.wp.terms(f"pa_{a['attribute_name']}")
            tmeta = self.wp.termmeta([t["term_id"] for t in terms])
            trows = [dict(wp_id=t["term_id"], attribute_id=amap[a["attribute_id"]], name=t["name"], slug=slug(t["slug"]),
                          description=clean_content(t["description"]), order=to_int(tmeta.get(t["term_id"], {}).get("order"), 0),
                          **seo_fields(tmeta.get(t["term_id"], {}))) for t in terms]
            m = upsert(AttributeTerm, trows)
            self.term_map.update(m)
            for t in terms:
                self.term_slug_map[(a["attribute_name"], slug(t["slug"]))] = m[t["term_id"]]
            total += len(trows)
        self.log(f"ویژگی‌ها: {len(rows)} — مقادیر: {total}")

    # -------------------------------------------------------------- pricing
    def import_albums(self):
        """گروه‌های mnswmc → آلبوم‌های ICSD. قیمت پایه طوری محاسبه می‌شود که قیمت نهایی ≈ قیمت فعلی سایت."""
        seed_sizes()
        self.sizes_by_legacy = {}
        for s in Size.objects.all():
            for ls in s.legacy_slugs:
                self.sizes_by_legacy[ls] = s
        self.size_12 = Size.objects.get(slug="12-meter")
        groups = self.wp.posts("mnswmc")
        gmeta = self.wp.postmeta([g["ID"] for g in groups])
        self.group_rate = {}
        rows = []
        for g in groups:
            m = gmeta.get(g["ID"], {})
            rate = to_dec(m.get("_mnswmc_currency_rate") or m.get("_mnswmc_currency_value"), Decimal(0))
            self.group_rate[g["ID"]] = rate
            rows.append(dict(wp_id=g["ID"], name=g["post_title"][:160], code=f"MNS-{g['ID']}",
                             base_size_id=self.size_12.pk, sort_order=g["menu_order"] or 0))
        self.album_map = upsert(Album, rows, fields=["name", "base_size_id", "sort_order"])
        self.log(f"آلبوم‌ها: {len(rows)}")

    def purchase_from_live(self, live_price):
        st = PricingSettings.load()
        return max(Decimal(0), (Decimal(live_price) - st.shipping_fixed) / (1 + st.markup_percent / 100))

    # ------------------------------------------------------------- products
    def import_products(self):
        posts = self.wp.posts("product", ("publish", "draft", "private", "pending"))
        ids = [p["ID"] for p in posts]
        keys = SEO_KEYS + [
            "_sku", "_thumbnail_id", "_product_image_gallery", "_stock_status", "_price", "_regular_price", "_sale_price",
            "_wc_average_rating", "_wc_review_count", "rank_math_primary_product_cat", "product_english_name",
            "post_views_count_woo", "views", "_mnswmc_currency_id", "mnswmc_currency_id", "_mnswmc_regular_price",
        ]
        meta = self.wp.postmeta(ids, keys)
        taxes = ["product_cat", "product_tag", "product_brand", "pa_brand", "product_type"] + [
            f"pa_{a.slug}" for a in Attribute.objects.all()
        ]
        rel = self.wp.object_terms(ids, taxes)
        type_names = {t["term_id"]: t["slug"] for t in self.wp.terms("product_type")}

        rows = []
        for p in posts:
            m = meta.get(p["ID"], {})
            r = rel[p["ID"]]
            brand_terms = r.get("product_brand") or r.get("pa_brand") or []
            kind = "simple" if any(type_names.get(t) == "simple" for t in r.get("product_type", [])) else "variable"
            status = p["post_status"] if p["post_status"] in ("publish", "draft", "private") else "draft"
            rows.append(dict(
                wp_id=p["ID"], title=p["post_title"][:300], slug=slug(p["post_name"]) or str(p["ID"]),
                english_name=(m.get("product_english_name") or "")[:300],
                content=clean_content(p["post_content"]), short_description=clean_content(p["post_excerpt"]),
                status=status, kind=kind, sku=(m.get("_sku") or "")[:100],
                image_id=self.media_pk(m.get("_thumbnail_id")),
                primary_category_id=self.cat_map.get(to_int(m.get("rank_math_primary_product_cat"))),
                brand_id=self.brand_map.get(brand_terms[0]) if brand_terms else None,
                stock_status=m.get("_stock_status") or "instock",
                sale_status="unavailable" if m.get("_stock_status") == "outofstock" else "available",
                rating_avg=to_dec(m.get("_wc_average_rating"), Decimal(0)) or 0,
                rating_count=to_int(m.get("_wc_review_count"), 0),
                views=to_int(m.get("post_views_count_woo") or m.get("views"), 0) or 0,
                menu_order=p["menu_order"] or 0,
                published_at=wp_datetime(p["post_date_gmt"], p["post_date"]),
                modified_at=wp_datetime(p["post_modified_gmt"], p["post_modified"]),
                **seo_fields(m),
            ))
        self.product_map = upsert(Product, rows)
        pmap = self.product_map
        # روابط
        set_m2m(Product.categories.through, "product_id", "category_id",
                [(pmap[i], self.cat_map.get(t)) for i in ids for t in rel[i].get("product_cat", [])], pmap.values())
        set_m2m(Product.tags.through, "product_id", "producttag_id",
                [(pmap[i], self.tag_map.get(t)) for i in ids for t in rel[i].get("product_tag", [])], pmap.values())
        spec_pairs = []
        for a in Attribute.objects.exclude(slug__in=SKIP_SPEC_ATTRS):
            for i in ids:
                for t in rel[i].get(f"pa_{a.slug}", []):
                    spec_pairs.append((pmap[i], self.term_map.get(t)))
        set_m2m(Product.specs.through, "product_id", "attributeterm_id", spec_pairs, pmap.values())
        # گالری
        gallery = []
        for i in ids:
            for n, mid in enumerate(str(meta.get(i, {}).get("_product_image_gallery") or "").split(",")):
                mpk = self.media_pk(mid)
                if mpk:
                    gallery.append(ProductImage(product_id=pmap[i], media_id=mpk, order=n))
        ProductImage.objects.filter(product_id__in=list(pmap.values())).delete()
        ProductImage.objects.bulk_create(gallery, batch_size=2000)
        self.product_posts, self.product_meta = posts, meta
        self.log(f"محصولات: {len(rows)} — تصاویر گالری: {len(gallery)}")

    def import_variations(self):
        posts = self.wp.posts("product_variation", ("publish", "private"))
        ids = [p["ID"] for p in posts]
        meta = self.wp.postmeta(ids)
        st = PricingSettings.load()

        # --- تشخیص آلبوم هر محصول (رایج‌ترین گروه mnswmc در تنوع‌هایش)
        by_parent = defaultdict(list)
        for p in posts:
            by_parent[p["post_parent"]].append(p)
        product_album = {}
        for parent, vs in by_parent.items():
            c = Counter(to_int(meta[v["ID"]].get("_mnswmc_currency_id")) for v in vs if meta[v["ID"]].get("_mnswmc_active") == "yes")
            c.pop(None, None)
            if c:
                product_album[parent] = c.most_common(1)[0][0]
        for p in self.product_posts:  # محصولات ساده
            gid = to_int(self.product_meta.get(p["ID"], {}).get("_mnswmc_currency_id") or self.product_meta.get(p["ID"], {}).get("mnswmc_currency_id"))
            if p["ID"] not in product_album and gid in self.album_map:
                product_album[p["ID"]] = gid

        # --- سایزهای ناشناخته (۲ تخته، کناره برشی و...) → سایز سفارشی با مساحت از ضریب mnswmc
        def size_key(m):
            s = m.get("attribute_pa_carpet-size")
            if s:
                return ("carpet-size", slug(s))
            w, l = m.get("attribute_pa_width"), m.get("attribute_pa_length")
            if w and l:
                return ("cut", f"{slug(w)}x{slug(l)}")
            return None

        unknown_units = defaultdict(list)
        for p in posts:
            m = meta[p["ID"]]
            k = size_key(m)
            if k and not (k[0] == "carpet-size" and k[1] in self.sizes_by_legacy):
                u = to_dec(m.get("_mnswmc_regular_price"))
                if u:
                    unknown_units[k].append(u)
        term_names = {s: t.name for (attr, s), t in (
            ((k, AttributeTerm.objects.get(pk=pk)) for k, pk in self.term_slug_map.items() if k[0] == "carpet-size"))}
        order = 300
        for k in sorted(unknown_units, key=str):
            if k[0] == "carpet-size":
                label = term_names.get(k[1], k[1])
                digits = re.findall(r"\d+(?:\.\d+)?", k[1])
                if "تخته" in k[1] and digits:
                    sslug = f"pair-{digits[-1]}-meter"
                else:
                    sslug = f"wp-{zlib.crc32(k[1].encode()) % 100000}"
                typ = Size.Type.RECT
                w = l = 0
            else:
                wv, lv = (to_int(re.sub(r"\D", "", x)) or 0 for x in k[1].split("x"))
                w = Decimal(wv) / (100 if "cm" in k[1].split("x")[0] else 1)
                l = Decimal(lv) / (100 if "cm" in k[1].split("x")[1] else 1)
                label = f"برشی {_num(w)} × {_num(l)} متر"
                sslug = f"cut-{k[1]}"
                typ = Size.Type.CUSTOM
            area = (w * l) if (w and l) else (statistics.median(unknown_units[k]) / 100).quantize(Decimal("0.0001"))
            size, _ = Size.objects.get_or_create(slug=sslug[:64], defaults=dict(
                label=label[:160], type=typ, width=w, length=l, area=area, sort_order=order, legacy_slugs=[k[1]],
            ))
            self.sizes_by_legacy[k[1]] = size
            order += 1

        # --- قیمت پایهٔ آلبوم‌ها از روی قیمت‌های فعلی
        albums = {a.wp_id: a for a in Album.objects.select_related("base_size")}
        per_album_norm = defaultdict(list)    # ضریب هر متر مربع (معمولاً ۱۰۰)
        per_album_waste = defaultdict(list)
        per_product_norm = defaultdict(list)
        for p in posts:
            m = meta[p["ID"]]
            k = size_key(m)
            size = self.sizes_by_legacy.get(k[1]) if k else None
            u = to_dec(m.get("_mnswmc_regular_price"))
            gid = product_album.get(p["post_parent"])
            if not (size and u and gid and size.area) or size.needs_waste:
                continue
            derived = size.slug.startswith(("wp-", "pair-"))  # مساحت از خود ضریب‌ها استخراج شده
            if not derived:
                per_product_norm[p["post_parent"]].append(u / size.area)
            if size.type != Size.Type.CUSTOM and not derived:
                per_album_norm[gid].append(u / size.area)
        for p in posts:
            m = meta[p["ID"]]
            k = size_key(m)
            size = self.sizes_by_legacy.get(k[1]) if k else None
            gid = product_album.get(p["post_parent"])
            u = to_dec(m.get("_mnswmc_regular_price"))
            if size and size.needs_waste and u and per_album_norm.get(gid):
                norm = statistics.median(per_album_norm[gid])
                per_album_waste[gid].append(u / (norm * size.area) - 1)

        for gid, album in albums.items():
            rate = self.group_rate.get(gid, Decimal(0))
            norm = statistics.median(per_album_norm[gid]) if per_album_norm.get(gid) else Decimal(100)
            live_base = norm * album.base_size.area * rate
            album.base_price = self.purchase_from_live(live_base).quantize(Decimal("1"))
            waste = statistics.median(per_album_waste[gid]) if per_album_waste.get(gid) else Decimal(0)
            album.waste_type = Album.WasteType.PERCENT
            album.waste_value = (Decimal(waste) * 100).quantize(Decimal("0.01")) if waste > Decimal("0.001") else Decimal(0)
            album._norm = norm
        Album.objects.bulk_update(list(albums.values()), ["base_price", "waste_type", "waste_value"])

        # --- اتصال محصول به آلبوم + قیمت پایهٔ اختصاصی
        prod_updates = []
        for wp_pid, gid in product_album.items():
            if wp_pid not in self.product_map or gid not in albums:
                continue
            album = albums[gid]
            custom = None
            if per_product_norm.get(wp_pid):
                pn = statistics.median(per_product_norm[wp_pid])
                if abs(pn / album._norm - 1) > Decimal("0.01"):
                    custom = self.purchase_from_live(pn * album.base_size.area * self.group_rate[gid]).quantize(Decimal("1"))
            prod_updates.append(Product(pk=self.product_map[wp_pid], album_id=album.pk, custom_base_price=custom))
        Product.objects.bulk_update(prod_updates, ["album", "custom_base_price"], batch_size=1000)
        product_obj = {p.pk: p for p in Product.objects.select_related("album__base_size")}
        for p in product_obj.values():
            if p.album is not None:
                p.album._norm = albums[p.album.wp_id]._norm

        # --- تنوع‌ها
        rows, attr_pairs = [], []
        for p in posts:
            parent_pk = self.product_map.get(p["post_parent"])
            if not parent_pk:
                continue
            m = meta[p["ID"]]
            k = size_key(m)
            size = self.sizes_by_legacy.get(k[1]) if k else None
            regular = to_int(m.get("_regular_price") or m.get("_price"))
            sale = to_int(m.get("_sale_price"))
            row = dict(
                wp_id=p["ID"], product_id=parent_pk, size_id=size.pk if size else None,
                sku=(m.get("_sku") or "")[:100], image_id=self.media_pk(m.get("_thumbnail_id")),
                description=m.get("_variation_description") or "", menu_order=p["menu_order"] or 0,
                is_available=(m.get("_stock_status") or "instock") != "outofstock",
                override_price=None, manual_price=regular, sale_price=None, pair_only=None,
            )
            # مقایسهٔ قیمت فرمول با قیمت فعلی؛ در صورت اختلاف، override
            u = to_dec(m.get("_mnswmc_regular_price"))
            gid = to_int(m.get("_mnswmc_currency_id"))
            prod = product_obj[parent_pk]
            if u and gid in self.group_rate and m.get("_mnswmc_active") == "yes":
                # مقایسه در «فضای ضریب»: آیا این سایز از همان فرمول محصول پیروی می‌کند؟
                album = prod.album
                ok = False
                if album and size and size.area and gid == album.wp_id:
                    norm = statistics.median(per_product_norm[p["post_parent"]]) if per_product_norm.get(p["post_parent"]) else album._norm
                    expected_u = norm * size.area
                    if size.needs_waste:
                        expected_u *= 1 + album.waste_value / 100
                    ok = abs(u - expected_u) <= expected_u * Decimal("0.02")
                if not ok:
                    row["override_price"] = self.purchase_from_live(u * self.group_rate[gid]).quantize(Decimal("1"))
                    self.report["variation_override"] += 1
            if sale and regular and sale < regular:
                row["_sale_ratio"] = Decimal(sale) / Decimal(regular)
            for key, val in m.items():
                if key.startswith("attribute_pa_") and key not in ("attribute_pa_carpet-size", "attribute_pa_width", "attribute_pa_length"):
                    tpk = self.term_slug_map.get((key[len("attribute_pa_"):], slug(val)))
                    if tpk:
                        attr_pairs.append((p["ID"], tpk))
            rows.append(row)
        ratios = {r["wp_id"]: r.pop("_sale_ratio") for r in rows if "_sale_ratio" in r}
        vmap = upsert(Variation, rows)
        set_m2m(Variation.attributes.through, "variation_id", "attributeterm_id",
                [(vmap[w], t) for w, t in attr_pairs], vmap.values())

        # محصولات سادهٔ دارای آلبوم: یک تنوع بدون سایز
        simple_rows = []
        for p in self.product_posts:
            if p["ID"] in by_parent or p["ID"] not in self.product_map:
                continue
            m = self.product_meta.get(p["ID"], {})
            regular = to_int(m.get("_regular_price") or m.get("_price"))
            row = dict(wp_id=p["ID"] + 10_000_000, product_id=self.product_map[p["ID"]], size_id=None, sku=(m.get("_sku") or "")[:100],
                       is_available=(m.get("_stock_status") or "instock") != "outofstock", manual_price=regular, override_price=None)
            u = to_dec(m.get("_mnswmc_regular_price"))
            gid = product_album.get(p["ID"])
            if u and gid in self.group_rate:
                row["override_price"] = self.purchase_from_live(u * self.group_rate[gid]).quantize(Decimal("1"))
            simple_rows.append(row)
        upsert(Variation, simple_rows)

        # محاسبهٔ قیمت نهایی همه
        Variation.reprice_queryset(Variation.objects.filter(product_id__in=list(self.product_map.values())))
        sales = []
        for v in Variation.objects.filter(wp_id__in=list(ratios)):
            if v.final_price:
                v.sale_price = int(round(v.final_price * float(ratios[v.wp_id]), -4)) or None
                sales.append(v)
        Variation.objects.bulk_update(sales, ["sale_price"])
        self.variation_meta = meta
        self.log(f"تنوع‌ها: {len(rows)} + {len(simple_rows)} ساده — override قیمت: {self.report['variation_override']} — حراج: {len(sales)}")
        self.price_check(posts, meta)

    def price_check(self, posts, meta):
        """مقایسهٔ قیمت جدید با قیمت فعلی سایت برای تنوع‌های موجود."""
        vmap = {v.wp_id: v for v in Variation.objects.filter(is_available=True, wp_id__lt=10_000_000)}
        diffs = []
        for p in posts:
            m = meta[p["ID"]]
            v = vmap.get(p["ID"])
            u, gid = to_dec(m.get("_mnswmc_regular_price")), to_int(m.get("_mnswmc_currency_id"))
            if not (v and v.final_price and u and gid in self.group_rate):
                continue
            live = u * self.group_rate[gid]
            if live > 0:
                diffs.append(float((Decimal(v.final_price) - live) / live * 100))
        if diffs:
            diffs.sort()
            q = lambda f: diffs[int(f * (len(diffs) - 1))]  # noqa: E731
            within1 = sum(abs(d) <= 1 for d in diffs) / len(diffs) * 100
            self.log(f"مقایسهٔ قیمت با سایت فعلی ({len(diffs)} تنوع موجود): میانه {q(.5):+.2f}٪، "
                     f"۵٪ پایین {q(.05):+.2f}٪، ۹۵٪ بالا {q(.95):+.2f}٪ — اختلاف ≤۱٪: {within1:.1f}٪")

    def import_reviews(self):
        rows_raw = self.wp.rows(
            "SELECT c.* FROM {p}comments c JOIN {p}posts p ON p.ID=c.comment_post_ID "
            "WHERE p.post_type='product' AND c.comment_approved IN ('0','1') ORDER BY c.comment_ID"
        )
        ratings = {}
        ids = [r["comment_ID"] for r in rows_raw]
        for i in range(0, len(ids), 2000):
            part = ids[i:i + 2000]
            ph = ",".join(["%s"] * len(part))
            for r in self.wp.rows(f"SELECT comment_id, meta_value FROM {{p}}commentmeta WHERE meta_key='rating' AND comment_id IN ({ph})", part):
                ratings[r["comment_id"]] = to_int(r["meta_value"])
        rows = [dict(wp_id=r["comment_ID"], product_id=self.product_map[r["comment_post_ID"]],
                     author_name=(r["comment_author"] or "کاربر")[:200], author_email=(r["comment_author_email"] or "")[:254],
                     rating=ratings.get(r["comment_ID"]) or None, content=r["comment_content"] or "",
                     is_approved=r["comment_approved"] == "1", created_at=wp_datetime(r["comment_date_gmt"], r["comment_date"]))
                for r in rows_raw if r["comment_post_ID"] in self.product_map]
        m = upsert(Review, rows)
        parents = [Review(pk=m[r["comment_ID"]], parent_id=m.get(r["comment_parent"])) for r in rows_raw if r["comment_ID"] in m and r["comment_parent"]]
        Review.objects.bulk_update(parents, ["parent"])
        self.log(f"نظرات محصول: {len(rows)}")

    # ----------------------------------------------------------------- blog
    def import_blog(self):
        terms = self.wp.terms("category")
        tmeta = self.wp.termmeta([t["term_id"] for t in terms])
        cmap = upsert(BlogCategory, [dict(wp_id=t["term_id"], name=t["name"], slug=slug(t["slug"]), description=clean_content(t["description"]),
                                          **seo_fields(tmeta.get(t["term_id"], {}))) for t in terms])
        BlogCategory.objects.bulk_update([BlogCategory(pk=cmap[t["term_id"]], parent_id=cmap.get(t["parent"])) for t in terms], ["parent"])
        tags = self.wp.terms("post_tag")
        tgmeta = self.wp.termmeta([t["term_id"] for t in tags])
        tmap = upsert(BlogTag, [dict(wp_id=t["term_id"], name=t["name"][:255], slug=slug(t["slug"]), description=t["description"] or "",
                                     **seo_fields(tgmeta.get(t["term_id"], {}))) for t in tags])

        posts = self.wp.posts("post", ("publish", "pending", "draft", "private"))
        ids = [p["ID"] for p in posts]
        meta = self.wp.postmeta(ids, SEO_KEYS + ["_thumbnail_id", "rank_math_primary_category", "views", "post_views_count"])
        authors = {r["ID"]: r["display_name"] for r in self.wp.rows("SELECT ID, display_name FROM {p}users")} if self._has_table("users") else {}
        rows = []
        for p in posts:
            m = meta.get(p["ID"], {})
            rows.append(dict(
                wp_id=p["ID"], title=p["post_title"][:300], slug=slug(p["post_name"]) or str(p["ID"]),
                content=clean_content(p["post_content"]), excerpt=p["post_excerpt"] or "",
                image_id=self.media_pk(m.get("_thumbnail_id")), status=p["post_status"],
                primary_category_id=cmap.get(to_int(m.get("rank_math_primary_category"))),
                author_name=authors.get(p["post_author"], "")[:200], views=to_int(m.get("views") or m.get("post_views_count"), 0) or 0,
                published_at=wp_datetime(p["post_date_gmt"], p["post_date"]),
                modified_at=wp_datetime(p["post_modified_gmt"], p["post_modified"]), **seo_fields(m),
            ))
        self.post_map = upsert(Post, rows)
        rel = self.wp.object_terms(ids, ["category", "post_tag"])
        set_m2m(Post.categories.through, "post_id", "blogcategory_id",
                [(self.post_map[i], cmap.get(t)) for i in ids for t in rel[i].get("category", [])], self.post_map.values())
        set_m2m(Post.tags.through, "post_id", "blogtag_id",
                [(self.post_map[i], tmap.get(t)) for i in ids for t in rel[i].get("post_tag", [])], self.post_map.values())

        # برگه‌ها
        pages = self.wp.posts("page", ("publish", "draft", "private"))
        pmeta = self.wp.postmeta([p["ID"] for p in pages], SEO_KEYS + ["_thumbnail_id"])
        front = to_int(self.wp.option("page_on_front"))
        shop = to_int(self.wp.option("woocommerce_shop_page_id"))
        prow = []
        for p in pages:
            raw = p["post_content"] or ""
            tpl = "home" if p["ID"] == front else "shop" if p["ID"] == shop else ""
            for sc, name in (("woocommerce_cart", "cart"), ("woocommerce_checkout", "checkout"),
                             ("woocommerce_my_account", "account"), ("woocommerce_order_tracking", "tracking")):
                if f"[{sc}" in raw:
                    tpl = name
            m = pmeta.get(p["ID"], {})
            prow.append(dict(wp_id=p["ID"], title=p["post_title"][:300], slug=slug(p["post_name"]) or str(p["ID"]),
                             content=clean_content(raw), image_id=self.media_pk(m.get("_thumbnail_id")), status=p["post_status"],
                             template=tpl, menu_order=p["menu_order"] or 0,
                             published_at=wp_datetime(p["post_date_gmt"], p["post_date"]),
                             modified_at=wp_datetime(p["post_modified_gmt"], p["post_modified"]), **seo_fields(m)))
        self.page_map = upsert(Page, prow)
        Page.objects.bulk_update([Page(pk=self.page_map[p["ID"]], parent_id=self.page_map.get(p["post_parent"])) for p in pages], ["parent"])

        # دیدگاه‌ها
        crows = self.wp.rows("SELECT c.* FROM {p}comments c JOIN {p}posts p ON p.ID=c.comment_post_ID "
                             "WHERE p.post_type='post' AND c.comment_approved IN ('0','1') AND c.comment_type IN ('', 'comment')")
        cm = upsert(Comment, [dict(wp_id=c["comment_ID"], post_id=self.post_map[c["comment_post_ID"]], author_name=(c["comment_author"] or "کاربر")[:200],
                                   author_email=(c["comment_author_email"] or "")[:254], content=c["comment_content"] or "",
                                   is_approved=c["comment_approved"] == "1", created_at=wp_datetime(c["comment_date_gmt"], c["comment_date"]))
                              for c in crows if c["comment_post_ID"] in self.post_map])
        Comment.objects.bulk_update([Comment(pk=cm[c["comment_ID"]], parent_id=cm.get(c["comment_parent"])) for c in crows if c["comment_ID"] in cm], ["parent"])

        # پرسش‌های متداول
        frows = []
        for ptype in ("ufaq", "product-faq", "nkfaq"):
            for p in self.wp.posts(ptype, ("publish",)):
                frows.append(dict(wp_id=p["ID"], question=p["post_title"][:500], answer=clean_content(p["post_content"]),
                                  group=ptype, order=p["menu_order"] or 0))
        upsert(Faq, frows)
        self.log(f"مقالات: {len(rows)} — برگه‌ها: {len(prow)} — دیدگاه‌ها: {len(cm)} — پرسش‌ها: {len(frows)}")

    def _has_table(self, name):
        return bool(self.wp.rows("SHOW TABLES LIKE %s", [self.wp.t(name)]))

    # ------------------------------------------------------------ redirects
    def add_redirect(self, source, target, origin, code=301, match=Redirect.Match.EXACT):
        source = Redirect.normalize(source)
        if not source:
            return
        Redirect.objects.update_or_create(
            source=source, match=match, defaults=dict(target=target, status_code=code, origin=origin, is_active=True)
        )

    def fix_target(self, url):
        """مقصدهای خراب Rank Math مثل /post=15870/slug/ را به آدرس واقعی تبدیل می‌کند."""
        m = re.match(r"^/post=(\d+)/", url)
        if m:
            wp_id = int(m.group(1))
            for model in (Post, Product, Page):
                obj = model.objects.filter(wp_id=wp_id).first()
                if obj:
                    return obj.get_absolute_url()
        url = re.sub(r"^/post=", "/", url)
        # ساختار قدیمی آدرس مقالات: /1396/09/21/slug/ → /slug/
        m = re.match(r"^/\d{4}/\d{2}/\d{2}/([^/]+)/?$", url)
        if m:
            key = unquote(m.group(1))
            obj = Post.objects.filter(slug=key).first() or (Post.objects.filter(wp_id=int(key)).first() if key.isdigit() else None)
            if obj:
                return obj.get_absolute_url()
        return url

    def flatten_redirects(self):
        """اسلش انتهایی مقصد را اضافه و زنجیرهٔ ریدایرکت (A→B→C) را به A→C تبدیل می‌کند."""
        exact = {r.source: r for r in Redirect.objects.filter(match=Redirect.Match.EXACT, is_active=True)}
        for r in exact.values():
            t = r.target
            for _ in range(5):
                if not t.startswith("/") or "?" in t:
                    break
                if not t.endswith("/") and not re.search(r"\.[a-z0-9]{2,5}$", t):
                    t += "/"
                nxt = exact.get(Redirect.normalize(t))
                if not nxt or nxt.pk == r.pk:
                    break
                if nxt.status_code == 410:
                    r.status_code = 410
                    t = ""
                    break
                t = nxt.target
            if t != r.target:
                r.target = t
                r.save(update_fields=["target", "status_code"])

    def import_redirects(self):
        n = 0
        if self._has_table("rank_math_redirections"):
            for r in self.wp.rows("SELECT * FROM {p}rank_math_redirections WHERE status='active'"):
                code = to_int(r["header_code"], 301)
                code = code if code in (301, 302, 410) else 301
                target = self.fix_target(self.relative_url(r["url_to"]))
                for src in as_list(php_unserialize(r["sources"], default=[])):
                    pattern, comp = (src.get("pattern") or ""), (src.get("comparison") or "exact")
                    if not pattern:
                        continue
                    if comp == "exact":
                        self.add_redirect(pattern, target, "rankmath", code)
                    elif comp == "start":
                        self.add_redirect(pattern, target, "rankmath", code, Redirect.Match.START)
                    elif comp == "regex":
                        self.add_redirect(pattern, target, "rankmath", code, Redirect.Match.REGEX)
                    elif comp in ("contains", "end"):
                        rx = re.escape(Redirect.normalize(pattern)) + ("$" if comp == "end" else "")
                        Redirect.objects.update_or_create(source=rx, match=Redirect.Match.REGEX, defaults=dict(
                            target=target, status_code=code, origin="rankmath"))
                    n += 1
        # نامک‌های قدیمی
        current_products = set(Product.objects.values_list("slug", flat=True))
        current_posts = set(Post.objects.values_list("slug", flat=True)) | set(Page.objects.filter(parent=None).values_list("slug", flat=True))
        old = 0
        for wp_type, model, prefix, current in (("product", Product, "product/", current_products), ("post", Post, "", current_posts)):
            objs = {o.wp_id: o for o in model.objects.exclude(wp_id=None)}
            olds = self.wp.postmeta_all(list(objs), "_wp_old_slug")
            for wp_id, slugs in olds.items():
                obj = objs[wp_id]
                for s in set(slug(x) for x in slugs):
                    if s and s != obj.slug and s not in current:
                        self.add_redirect(prefix + s, obj.get_absolute_url(), "old_slug")
                        old += 1
        self.flatten_redirects()
        self.log(f"ریدایرکت‌ها: {n} از Rank Math + {old} نامک قدیمی — کل: {Redirect.objects.count()}")

    # ------------------------------------------------------------------ run
    STEPS = ["settings", "media", "taxonomies", "pricing", "products", "reviews", "blog", "redirects"]

    def run(self, only=None):
        steps = only or self.STEPS
        if "settings" in steps:
            self.import_settings()
        if "media" in steps:
            self.import_media()
        need_tax = any(s in steps for s in ("taxonomies", "products"))
        if need_tax:
            with transaction.atomic():
                self.import_categories()
                self.import_product_tags()
                self.import_brands()
                self.import_attributes()
        if any(s in steps for s in ("pricing", "products")):
            self.import_albums()
        if "products" in steps:
            with transaction.atomic():
                self.import_products()
                self.import_variations()
        if "reviews" in steps:
            if not hasattr(self, "product_map"):
                self.product_map = dict(Product.objects.exclude(wp_id=None).values_list("wp_id", "pk"))
            self.import_reviews()
        if "blog" in steps:
            with transaction.atomic():
                self.import_blog()
        if "redirects" in steps:
            self.import_redirects()
