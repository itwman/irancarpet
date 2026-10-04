"""بررسی منبع قیمت‌ها در وردپرس (فقط خواندنی): افزونهٔ ICSD Price Manager در برابر افزونهٔ ارزی (mnswmc)

    venv/bin/python manage.py pricing_check --product 4681
"""
import json
from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Product
from core.utils.php import php_unserialize
from core.wp.reader import WPReader
from pricing.models import Album


def n(x):
    try:
        return f"{Decimal(x):,.0f}"
    except Exception:  # noqa: BLE001
        return str(x)


class Command(BaseCommand):
    help = "مقایسهٔ داده‌های قیمت ICSD و افزونهٔ ارزی در وردپرس با سایت جنگو (بدون تغییر)"

    def add_arguments(self, parser):
        parser.add_argument("--product", type=int, help="شناسهٔ محصول در پنل جنگو")

    def out(self, *a):
        self.stdout.write(" ".join(str(x) for x in a))

    def handle(self, *args, product=None, **kw):
        wp = WPReader()
        has = lambda t: bool(wp.rows("SHOW TABLES LIKE %s", [wp.t(t)]))  # noqa: E731

        self.out("==== تنظیمات ICSD")
        for k in ("icsd_pm_db_version", "icsd_pm_markup_percent", "icsd_pm_shipping_fixed", "icsd_pm_round_to", "icsd_pm_round_method"):
            self.out(f"  {k} = {wp.option(k)}")
        active = wp.option("active_plugins") or ""
        self.out("  افزونهٔ ICSD فعال:", "icsd-price-manager" in active, "| افزونهٔ ارزی فعال:", "mnswmc" in active or "currency" in active.lower())

        plugins = php_unserialize(wp.option("active_plugins") or "", default=[]) or []
        plugins = list(plugins.values()) if isinstance(plugins, dict) else list(plugins)
        self.out("  افزونه‌های قیمتی فعال:", ", ".join(x for x in plugins if any(k in x for k in ("pricing", "mns", "icsd", "torob", "nosan"))) or "—")

        icap = wp.posts("icap_album", ("publish", "draft", "private"))
        am = wp.postmeta([a["ID"] for a in icap])
        linked = wp.rows("SELECT meta_value AS a, COUNT(*) AS c FROM {p}postmeta WHERE meta_key='_icap_album_id' GROUP BY meta_value")
        cnt = {str(r["a"]): r["c"] for r in linked}
        self.out(f"\n==== آلبوم‌های افزونهٔ قیمت‌گذاری آلبومی ایران‌کارپت ({len(icap)}) — محصولات وصل‌شده: {sum(cnt.values())}")
        for a in icap:
            m = am.get(a["ID"], {})
            sizes = php_unserialize(m.get("_icap_enabled_sizes") or "", default=[]) or []
            sizes = list(sizes.values()) if isinstance(sizes, dict) else sizes
            self.out(f"  #{a['ID']} {a['post_title']} | خرید {n(m.get('_icap_buy_price'))} | سود {m.get('_icap_profit_percent')}٪ "
                     f"| ارسال {n(m.get('_icap_shipping_fixed'))} | پرتی {m.get('_icap_waste_type')} {m.get('_icap_waste_value')} "
                     f"| گرد {n(m.get('_icap_round_to'))} | سایزها {','.join(map(str, sizes))} | محصول {cnt.get(str(a['ID']), 0)}")
        self.out("  سایزهای استاندارد:", wp.option("icap_standard_sizes", "")[:600])

        icsd_albums = {}
        if has("icsd_albums"):
            sizes = {r["id"]: r for r in wp.rows("SELECT * FROM {p}icsd_sizes")} if has("icsd_sizes") else {}
            rows = wp.rows("SELECT * FROM {p}icsd_albums ORDER BY sort_order, name")
            self.out(f"\n==== آلبوم‌های ICSD ({len(rows)})")
            for a in rows:
                icsd_albums[a["id"]] = a
                bs = sizes.get(a["base_size_id"], {})
                self.out(f"  #{a['id']} {a['name']} | پایه {n(a['base_price'])} ({bs.get('slug', a['base_size_id'])}) "
                         f"| پرتی {a['waste_type']} {n(a['waste_value'])} | فعال {a['is_active']} | {a.get('last_updated')}")
        else:
            self.out("\n!! جدول آلبوم‌های ICSD در وردپرس وجود ندارد.")

        if has("icsd_product_album"):
            pa = wp.rows("SELECT * FROM {p}icsd_product_album")
            self.out(f"\n==== اتصال محصول↔آلبوم ICSD: {len(pa)} محصول | با قیمت پایهٔ اختصاصی: "
                     f"{sum(1 for r in pa if r['custom_price'] is not None)} | با override سایز: "
                     f"{sum(1 for r in pa if r['size_overrides'] and r['size_overrides'] not in ('[]', '{}', 'null'))}")

        groups = wp.posts("mnswmc")
        gm = wp.postmeta([g["ID"] for g in groups])
        self.out(f"\n==== گروه‌های افزونهٔ ارزی ({len(groups)}) — آلبوم فعلی جنگو")
        dj = {a.wp_id: a for a in Album.objects.all()}
        for g in groups:
            m = gm.get(g["ID"], {})
            a = dj.get(g["ID"])
            self.out(f"  #{g['ID']} {g['post_title']} | نرخ {n(m.get('_mnswmc_currency_rate') or m.get('_mnswmc_currency_value'))}"
                     f" | جنگو: {n(a.base_price) if a else '—'}")

        if not product:
            return
        p = Product.objects.select_related("album").get(pk=product)
        self.out(f"\n==== محصول {p.pk} (وردپرس {p.wp_id}): {p.title}")
        self.out(f"  جنگو: آلبوم {p.album.name if p.album else '—'} | پایهٔ آلبوم {n(p.album.base_price) if p.album else '—'} | پایهٔ اختصاصی {n(p.custom_base_price) if p.custom_base_price is not None else '—'}")
        if p.wp_id:
            pm = wp.postmeta([p.wp_id], ["_icap_album_id", "_icap_size_map", "_mnswmc_currency_id", "_mnswmc_active"]).get(p.wp_id, {})
            self.out(f"  وردپرس: آلبوم ایران‌کارپت {pm.get('_icap_album_id', '—')} | نقشهٔ سایز {pm.get('_icap_size_map', '—')} | ارزی {pm.get('_mnswmc_currency_id', '—')} {pm.get('_mnswmc_active', '')}")
        if has("icsd_product_album") and p.wp_id:
            r = wp.rows("SELECT * FROM {p}icsd_product_album WHERE product_id=%s", [p.wp_id])
            if r:
                r = r[0]
                a = icsd_albums.get(r["album_id"], {})
                self.out(f"  ICSD: آلبوم #{r['album_id']} {a.get('name')} | پایهٔ آلبوم {n(a.get('base_price'))} | پایهٔ اختصاصی {n(r['custom_price']) if r['custom_price'] is not None else '—'} | وضعیت {r['status']}")
                if r["size_overrides"]:
                    self.out("  ICSD override سایزها:", json.dumps(json.loads(r["size_overrides"]), ensure_ascii=False))
            else:
                self.out("  ICSD: این محصول به هیچ آلبوم ICSD وصل نیست.")
        vs = wp.rows("SELECT ID FROM {p}posts WHERE post_parent=%s AND post_type='product_variation'", [p.wp_id or 0])
        vm = wp.postmeta([v["ID"] for v in vs])
        djv = {v.wp_id: v for v in p.variations.select_related("size")}
        self.out("  سایز | ارزی: ضریب×گروه | وردپرس: قیمت/حراج | جنگو: خرید اختصاصی/نهایی/حراج")
        for v in vs:
            m = vm.get(v["ID"], {})
            d = djv.get(v["ID"])
            self.out(f"  {m.get('attribute_pa_carpet-size') or m.get('attribute_pa_width', '')} | "
                     f"{m.get('_mnswmc_regular_price')}×#{m.get('_mnswmc_currency_id')} ({m.get('_mnswmc_active')}) | "
                     f"{n(m.get('_regular_price'))}/{n(m.get('_sale_price')) if m.get('_sale_price') else '—'} | "
                     + (f"{n(d.override_price) if d.override_price is not None else '—'}/{n(d.final_price)}/{n(d.sale_price) if d.sale_price else '—'}" if d else "—"))
