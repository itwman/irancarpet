"""سبد خرید در سشن: {کلید: تعداد}. قیمت همیشه از قیمت روز محاسبه می‌شود.

کلید: شناسهٔ تنوع («۱۲۳»)، یا برای فرش متری شناسه با عرض و طول («123@0.50x15.45»).
"""
from catalog.models import Variation

KEY = "cart"
MAX_QTY = 20


class Line:
    def __init__(self, variation, qty, width=None, length=None):
        self.variation = variation
        self.product = variation.product
        self.qty = qty
        self.width, self.length = width, length
        self.unit_price = variation.price or 0
        self.problem = ""
        self.m2 = None
        if width is not None:  # فرش متری: یک تخته = عرض × طول × قیمت هر متر مربع
            from pricing import m2

            r = m2.rules(self.product)
            self.m2 = {"area": m2.area(width, length), "per_m2": self.unit_price}
            err = m2.check(r, width, length) if r else "این فرش متری نیست."
            self.unit_price = m2.price(self.unit_price, width, length, r["round"] if r else 0) if self.unit_price else 0
            if err:
                self.problem = err
        elif self.product.is_m2:
            self.problem = "برای این فرش عرض و طول را در صفحهٔ فرش انتخاب کنید."
        if self.problem:
            pass
        elif not self.product.is_purchasable or not variation.is_available:
            self.problem = "این سایز الان موجود نیست."
        elif not self.unit_price:
            self.problem = "قیمت این سایز استعلامی است."
        elif self.product.seller_id and self.product.status != "publish":
            self.problem = "این کالا الان فروخته نمی‌شود."
        if width is None:
            from .offers import apply_to_line

            apply_to_line(self)

    @property
    def key(self):
        if self.width is not None:
            from pricing.m2 import key

            return key(self.variation.pk, self.width, self.length)
        return str(self.variation.pk)

    @property
    def total(self):
        return self.unit_price * self.qty

    @property
    def size_label(self):
        if self.width is not None:
            from pricing.m2 import label

            return label(self.width, self.length)
        v = self.variation
        parts = [v.size.label] if v.size else []
        parts += [a.name for a in v.attributes.all()]
        return "، ".join(parts) or v.sku


class Cart:
    def __init__(self, request):
        self.request = request
        self.session = request.session
        self.data = {str(k): int(v) for k, v in (self.session.get(KEY) or {}).items()}

    def save(self):
        self.session[KEY] = self.data
        self.session.modified = True
        try:  # سبد مشتری واردشده برای یادآوری و دستگاه‌های دیگر (باشگاه مشتریان)
            from crm.carts import track

            track(self.request, self.data)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def fix_qty(variation, qty):
        qty = max(1, min(int(qty or 1), MAX_QTY))
        if variation.stock_qty is not None:  # کالای فروشنده با تعداد موجودی مشخص
            qty = max(1, min(qty, variation.stock_qty))
        if variation.is_pair_only and qty % 2:
            from .offers import allows_qty

            if not allows_qty(variation, qty):  # فرصت ویژه: تعدادهای مجاز تخته‌های انبار
                qty += 1
        return qty

    def add(self, variation, qty=1, width=None, length=None):
        if width is not None:
            from pricing.m2 import key as m2key

            key = m2key(variation.pk, width, length)
            self.data[key] = max(1, min(int(self.data.get(key, 0)) + int(qty or 1), MAX_QTY))
        else:
            key = str(variation.pk)
            self.data[key] = self.fix_qty(variation, self.data.get(key, 0) + qty)
        self.save()
        return self.data[key]

    def set(self, variation, qty, key=None):
        key = key or str(variation.pk)
        if qty <= 0:
            self.remove(key)
            return 0
        self.data[key] = self.fix_qty(variation, qty) if "@" not in key else max(1, min(int(qty), MAX_QTY))
        self.save()
        return self.data[key]

    def remove(self, key):
        self.data.pop(str(key), None)
        self.save()

    def clear(self):
        self.data = {}
        self.save()

    @property
    def count(self):
        return sum(self.data.values())

    def lines(self):
        from pricing.m2 import parse_key

        keys = {k: parse_key(k) for k in self.data}
        ids = [p[0] for p in keys.values() if p[0]]
        vs = (Variation.objects.filter(pk__in=ids).select_related("product__image", "product__seller", "product__album", "size")
              .prefetch_related("attributes", "product__variations__size"))
        by_id = {v.pk: v for v in vs}
        out = []
        for k, q in self.data.items():
            vid, w, ln = keys[k]
            v = by_id.get(vid)
            if v:
                out.append(Line(v, q, w, ln))
        if len(out) != len(self.data):
            self.data = {line.key: line.qty for line in out}
            self.save()
        return out

    def summary(self):
        lines = self.lines()
        ok = [line for line in lines if not line.problem]
        from .offers import offer_total

        return {"lines": lines, "total": sum(line.total for line in ok), "has_problem": any(line.problem for line in lines),
                "offer_total": offer_total(ok)}
