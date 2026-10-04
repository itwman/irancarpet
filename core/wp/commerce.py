"""انتقال مشتریان و سفارش‌های ووکامرس (هم ساختار قدیمی posts و هم HPOS).

اطلاعات شخصی مستقیم روی همان سرور از دیتابیس وردپرس خوانده می‌شود و جایی فرستاده نمی‌شود.
قابل اجرای مکرر است: هر رکورد با wp_id شناسایی و به‌روزرسانی می‌شود.
"""
import re
from collections import defaultdict
from datetime import datetime, timezone as dt_tz
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import Profile
from accounts.utils import normalize_mobile
from catalog.models import Product, Variation
from core.utils.php import php_unserialize
from shop.models import Order, OrderItem, Payment

from .reader import chunks, wp_datetime

# کد استان‌های ایران در ووکامرس
IR_STATES = {
    "THR": "تهران", "ESF": "اصفهان", "KHZ": "خوزستان", "FRS": "فارس", "EAZ": "آذربایجان شرقی", "WAZ": "آذربایجان غربی",
    "ADL": "اردبیل", "ABZ": "البرز", "ILM": "ایلام", "BHR": "بوشهر", "CHB": "چهارمحال و بختیاری", "SKH": "خراسان جنوبی",
    "RKH": "خراسان رضوی", "NKH": "خراسان شمالی", "ZJN": "زنجان", "SMN": "سمنان", "SBN": "سیستان و بلوچستان", "GZN": "قزوین",
    "QHM": "قم", "KRD": "کردستان", "KRN": "کرمان", "KRH": "کرمانشاه", "KBD": "کهگیلویه و بویراحمد", "GLS": "گلستان",
    "GIL": "گیلان", "LRS": "لرستان", "MZN": "مازندران", "MKZ": "مرکزی", "HRZ": "هرمزگان", "HDN": "همدان", "YZD": "یزد",
}

STATUS_MAP = {
    "wc-pending": "pending", "wc-checkout-draft": "pending", "wc-on-hold": "processing", "wc-processing": "processing",
    "wc-completed": "completed", "wc-cancelled": "cancelled", "wc-failed": "cancelled", "wc-refunded": "refunded",
}
PAID_WP = {"wc-completed"}  # بقیه فقط اگر تاریخ پرداخت داشته باشند پرداخت‌شده حساب می‌شوند


def money(v):
    try:
        return int(Decimal(str(v or "0").replace(",", "")))
    except (InvalidOperation, ValueError):
        return 0


def to_dt(v, gmt=False):
    if not v:
        return None
    s = str(v).strip()
    if s.isdigit():
        return datetime.fromtimestamp(int(s), tz=dt_tz.utc)
    if s.startswith("0000"):
        return None
    return wp_datetime(v, None) if gmt else wp_datetime(None, v)


def state_name(v):
    v = (v or "").strip()
    return IR_STATES.get(v.upper(), v)[:60]


def clean(v, n):
    return (str(v or "")).strip()[:n]


class CommerceImporter:
    """با Importer اصلی استفاده می‌شود (self.wp و self.log از آن می‌آید)."""

    def __init__(self, wp, log):
        self.wp, self.log = wp, log
        rate = (wp.option("woocommerce_currency") or "IRT").upper()
        self.div = 10 if rate == "IRR" else 1  # همه‌چیز به تومان

    def table_exists(self, name):
        return bool(self.wp.rows("SHOW TABLES LIKE %s", [self.wp.t(name)]))

    # -------------------------------------------------------------- مشتریان
    def import_customers(self):
        User = get_user_model()
        users = self.wp.rows("SELECT ID, user_login, user_pass, user_email, user_registered, display_name FROM {p}users ORDER BY ID")
        keys = ["first_name", "last_name", "billing_first_name", "billing_last_name", "billing_phone", "billing_email",
                "billing_state", "billing_city", "billing_address_1", "billing_address_2", "billing_postcode",
                "digits_phone", "digits_phone_no", "digt_countrycode", "mobile", "phone", "user_phone", f"{self.wp.p}capabilities"]
        meta = defaultdict(dict)
        ids = [u["ID"] for u in users]
        for part in chunks(ids):
            ph = ",".join(["%s"] * len(part))
            kph = ",".join(["%s"] * len(keys))
            for r in self.wp.rows(f"SELECT user_id, meta_key, meta_value FROM {{p}}usermeta WHERE user_id IN ({ph}) AND meta_key IN ({kph})", [*part, *keys]):
                meta[r["user_id"]].setdefault(r["meta_key"], r["meta_value"])

        existing = {p.wp_id: p for p in Profile.objects.exclude(wp_id=None).select_related("user")}
        used_mobiles = dict(Profile.objects.exclude(mobile=None).values_list("mobile", "wp_id"))
        taken_usernames = set(User.objects.values_list("username", flat=True))
        created = updated = no_mobile = 0
        admins = []
        with transaction.atomic():
            for u in users:
                m = meta.get(u["ID"], {})
                mobile = ""
                for k in ("digits_phone", "digits_phone_no", "billing_phone", "mobile", "phone", "user_phone"):
                    mobile = normalize_mobile(m.get(k))
                    if mobile:
                        break
                if not mobile:
                    mobile = normalize_mobile(u["user_login"])
                if mobile and used_mobiles.get(mobile, u["ID"]) != u["ID"]:
                    mobile = ""  # این شماره قبلاً برای حساب دیگری ثبت شده
                caps = php_unserialize(m.get(f"{self.wp.p}capabilities"), default={}) or {}
                if isinstance(caps, dict) and (caps.get("administrator") or caps.get("shop_manager")):
                    admins.append(u["user_login"])
                prof = existing.get(u["ID"])
                user = prof.user if prof else None
                if user is None:
                    uname = clean(u["user_login"], 150) or f"wp{u['ID']}"
                    if uname in taken_usernames:
                        uname = f"{uname[:140]}-wp{u['ID']}"
                    user = User(username=uname)
                    taken_usernames.add(uname)
                    created += 1
                else:
                    updated += 1
                user.email = clean(u["user_email"] or m.get("billing_email"), 254)
                user.first_name = clean(m.get("first_name") or m.get("billing_first_name"), 150)
                user.last_name = clean(m.get("last_name") or m.get("billing_last_name"), 150)
                if not user.first_name and not user.last_name and u.get("display_name") and u["display_name"] != u["user_login"]:
                    user.first_name = clean(u["display_name"], 150)
                pw = u["user_pass"] or ""
                user.password = f"phpass${pw}" if pw.startswith(("$P$", "$H$", "$wp$", "$2y$", "$2b$")) else "!"
                user.date_joined = wp_datetime(None, u["user_registered"])
                user.save()
                prof = prof or Profile(user=user, wp_id=u["ID"])
                prof.user = user
                prof.mobile = mobile or None
                prof.province = state_name(m.get("billing_state"))
                prof.city = clean(m.get("billing_city"), 80)
                prof.address = " ".join(x for x in (m.get("billing_address_1"), m.get("billing_address_2")) if x).strip()
                prof.postal_code = re.sub(r"\D", "", str(m.get("billing_postcode") or ""))[:10]
                prof.save()
                if mobile:
                    used_mobiles[mobile] = u["ID"]
                else:
                    no_mobile += 1
        self.log(f"مشتریان: {created} تازه، {updated} به‌روز، {no_mobile} بدون موبایل معتبر")
        if admins:
            self.log(f"  مدیران وردپرس (دسترسی پنل خودکار داده نشد): {', '.join(admins[:15])}")

    # -------------------------------------------------------------- سفارش‌ها
    def hpos(self):
        return (self.wp.option("woocommerce_custom_orders_table_enabled") == "yes") and self.table_exists("wc_orders")

    def load_orders(self):
        """فهرست سفارش‌ها به شکل یکسان، از هر دو ساختار ووکامرس."""
        out = []
        if self.hpos():
            rows = self.wp.rows("SELECT * FROM {p}wc_orders WHERE type='shop_order' ORDER BY id")
            ids = [r["id"] for r in rows]
            addr, ops, meta = {}, {}, defaultdict(dict)
            for part in chunks(ids):
                ph = ",".join(["%s"] * len(part))
                for a in self.wp.rows(f"SELECT * FROM {{p}}wc_order_addresses WHERE order_id IN ({ph})", part):
                    addr[(a["order_id"], a["address_type"])] = a
                if self.table_exists("wc_order_operational_data"):
                    for o in self.wp.rows(f"SELECT * FROM {{p}}wc_order_operational_data WHERE order_id IN ({ph})", part):
                        ops[o["order_id"]] = o
                for mrow in self.wp.rows(f"SELECT order_id, meta_key, meta_value FROM {{p}}wc_orders_meta WHERE order_id IN ({ph}) "
                                         "AND meta_key IN ('_order_number','_billing_mobile','billing_mobile')", part):
                    meta[mrow["order_id"]].setdefault(mrow["meta_key"], mrow["meta_value"])
            for r in rows:
                b = addr.get((r["id"], "billing"), {})
                s = addr.get((r["id"], "shipping"), {})
                op = ops.get(r["id"], {})
                out.append(dict(
                    id=r["id"], status=r["status"], total=r["total_amount"], customer=r["customer_id"],
                    created=wp_datetime(r.get("date_created_gmt")), paid=op.get("date_paid_gmt"), paid_gmt=True,
                    payment=r.get("payment_method_title") or r.get("payment_method") or "", txn=r.get("transaction_id") or "",
                    note=r.get("customer_note") or "", number=meta[r["id"]].get("_order_number"),
                    first=b.get("first_name") or s.get("first_name"), last=b.get("last_name") or s.get("last_name"),
                    phone=b.get("phone") or s.get("phone") or meta[r["id"]].get("_billing_mobile") or meta[r["id"]].get("billing_mobile"),
                    email=b.get("email") or r.get("billing_email"),
                    state=s.get("state") or b.get("state"), city=s.get("city") or b.get("city"),
                    addr=" ".join(x for x in (s.get("address_1") or b.get("address_1"), s.get("address_2") or b.get("address_2")) if x),
                    postcode=s.get("postcode") or b.get("postcode"),
                ))
            return out
        statuses = list(STATUS_MAP) + ["wc-deposit", "wc-partially-paid"]
        posts = self.wp.rows("SELECT ID, post_status, post_date, post_date_gmt, post_excerpt FROM {p}posts WHERE post_type='shop_order' ORDER BY ID")
        keys = ["_order_total", "_customer_user", "_payment_method_title", "_payment_method", "_transaction_id", "_paid_date",
                "_date_paid", "_order_number", "_billing_first_name", "_billing_last_name", "_billing_phone", "_billing_mobile",
                "billing_mobile", "_billing_email", "_billing_state", "_billing_city", "_billing_address_1", "_billing_address_2",
                "_billing_postcode", "_shipping_first_name", "_shipping_last_name", "_shipping_state", "_shipping_city",
                "_shipping_address_1", "_shipping_address_2", "_shipping_postcode", "_shipping_phone"]
        meta = self.wp.postmeta([p["ID"] for p in posts], keys)
        for p in posts:
            m = meta.get(p["ID"], {})
            out.append(dict(
                id=p["ID"], status=p["post_status"], total=m.get("_order_total"), customer=m.get("_customer_user"),
                created=wp_datetime(p["post_date_gmt"], p["post_date"]), paid=m.get("_paid_date") or m.get("_date_paid"),
                payment=m.get("_payment_method_title") or m.get("_payment_method") or "", txn=m.get("_transaction_id") or "",
                note=p.get("post_excerpt") or "", number=m.get("_order_number"),
                first=m.get("_billing_first_name") or m.get("_shipping_first_name"),
                last=m.get("_billing_last_name") or m.get("_shipping_last_name"),
                phone=m.get("_billing_phone") or m.get("_billing_mobile") or m.get("billing_mobile") or m.get("_shipping_phone"),
                email=m.get("_billing_email"),
                state=m.get("_shipping_state") or m.get("_billing_state"), city=m.get("_shipping_city") or m.get("_billing_city"),
                addr=" ".join(x for x in (m.get("_shipping_address_1") or m.get("_billing_address_1"),
                                          m.get("_shipping_address_2") or m.get("_billing_address_2")) if x),
                postcode=m.get("_shipping_postcode") or m.get("_billing_postcode"),
            ))
        return out

    def load_items(self, order_ids):
        items = defaultdict(list)
        for part in chunks(order_ids):
            ph = ",".join(["%s"] * len(part))
            rows = self.wp.rows(f"SELECT order_item_id, order_item_name, order_item_type, order_id FROM {{p}}woocommerce_order_items "
                                f"WHERE order_id IN ({ph}) ORDER BY order_item_id", part)
            meta = defaultdict(dict)
            iids = [r["order_item_id"] for r in rows]
            for ip in chunks(iids):
                iph = ",".join(["%s"] * len(ip))
                for mr in self.wp.rows(f"SELECT order_item_id, meta_key, meta_value FROM {{p}}woocommerce_order_itemmeta WHERE order_item_id IN ({iph})", ip):
                    meta[mr["order_item_id"]].setdefault(mr["meta_key"], mr["meta_value"])
            for r in rows:
                r["meta"] = meta.get(r["order_item_id"], {})
                items[r["order_id"]].append(r)
        return items

    def import_orders(self):
        orders = self.load_orders()
        if not orders:
            self.log("سفارش‌ها: سفارشی در وردپرس پیدا نشد.")
            return
        items = self.load_items([o["id"] for o in orders])
        users = dict(Profile.objects.exclude(wp_id=None).values_list("wp_id", "user_id"))
        products = dict(Product.objects.exclude(wp_id=None).values_list("wp_id", "pk"))
        variations = dict(Variation.objects.exclude(wp_id=None).values_list("wp_id", "pk"))
        existing = {o.wp_id: o for o in Order.objects.exclude(wp_id=None)}
        used_numbers = set(Order.objects.filter(wp_id=None).values_list("number", flat=True))
        n_new = n_upd = 0
        unknown = defaultdict(int)
        with transaction.atomic():
            for d in orders:
                status = STATUS_MAP.get(d["status"])
                if status is None:
                    unknown[d["status"]] += 1
                    status = "processing"
                total = money(d["total"]) // self.div
                try:
                    number = int(str(d["number"] or d["id"]).strip())
                except ValueError:
                    number = d["id"]
                if number in used_numbers:
                    number = d["id"] if d["id"] not in used_numbers else 100000000 + d["id"]
                used_numbers.add(number)
                o = existing.get(d["id"]) or Order(wp_id=d["id"])
                is_new = o.pk is None
                o.number = number
                o.user_id = users.get(int(d["customer"] or 0))
                o.status = status
                o.wp_status = clean(d["status"], 40)
                o.wp_payment = clean(d["payment"], 200)
                o.first_name, o.last_name = clean(d["first"], 100), clean(d["last"], 100)
                o.mobile = normalize_mobile(d["phone"]) or clean(re.sub(r"\D", "", str(d["phone"] or "")), 11)
                o.email = clean(d["email"], 254)
                o.province, o.city = state_name(d["state"]), clean(d["city"], 80)
                o.address = (d["addr"] or "").strip()
                o.postal_code = re.sub(r"\D", "", str(d["postcode"] or ""))[:10]
                o.note = d["note"] or ""
                o.payment_mode = "full"
                o.shipping_mode = "cod"
                o.items_total = total
                o.online_amount = total
                paid = d["status"] in PAID_WP or bool(d["paid"])
                o.paid_amount = total if paid and status not in ("cancelled", "refunded", "pending") else 0
                o.created_at = d["created"]
                o.paid_at = to_dt(d["paid"], d.get("paid_gmt"))
                o.save()
                OrderItem.objects.filter(order=o).delete()
                lines = []
                for it in items.get(d["id"], []):
                    m = it["meta"]
                    t = it["order_item_type"]
                    if t == "line_item":
                        qty = max(money(m.get("_qty")), 1)
                        line = money(m.get("_line_total")) // self.div
                        size = "، ".join(str(v) for k, v in m.items() if not k.startswith("_") and v and len(str(v)) < 80)
                        lines.append(OrderItem(order=o, product_id=products.get(money(m.get("_product_id"))),
                                               variation_id=variations.get(money(m.get("_variation_id"))),
                                               title=clean(it["order_item_name"], 300), size_label=clean(size, 150),
                                               unit_price=line // qty if qty else line, quantity=qty))
                    elif t in ("shipping", "fee"):
                        cost = money(m.get("cost") or m.get("_line_total")) // self.div
                        if cost:
                            lines.append(OrderItem(order=o, title=clean(("ارسال: " if t == "shipping" else "") + (it["order_item_name"] or ""), 300),
                                                   unit_price=cost, quantity=1))
                OrderItem.objects.bulk_create(lines)
                Payment.objects.filter(order=o, gateway="wordpress").delete()
                if o.paid_amount:
                    Payment.objects.create(order=o, gateway="wordpress", amount=o.paid_amount, status="ok", ref_id=clean(d["txn"], 100),
                                           message=clean(d["payment"], 300), created_at=o.paid_at or o.created_at, verified_at=o.paid_at or o.created_at)
                n_new += is_new
                n_upd += not is_new
        self.log(f"سفارش‌ها ({'HPOS' if self.hpos() else 'posts'}): {n_new} تازه، {n_upd} به‌روز")
        if unknown:
            self.log("  وضعیت‌های ناشناخته (در حال آماده‌سازی گذاشته شد): " + ", ".join(f"{k}×{v}" for k, v in unknown.items()))
