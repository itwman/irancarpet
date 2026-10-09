"""سبد خرید در سشن: {شناسهٔ تنوع: تعداد}. قیمت همیشه از قیمت روز محاسبه می‌شود."""
from catalog.models import Variation

KEY = "cart"
MAX_QTY = 20


class Line:
    def __init__(self, variation, qty):
        self.variation = variation
        self.product = variation.product
        self.qty = qty
        self.unit_price = variation.price or 0
        self.problem = ""
        if not self.product.is_purchasable or not variation.is_available:
            self.problem = "این سایز الان موجود نیست."
        elif not self.unit_price:
            self.problem = "قیمت این سایز استعلامی است."
        elif self.product.seller_id and self.product.status != "publish":
            self.problem = "این کالا الان فروخته نمی‌شود."
        from .offers import apply_to_line

        apply_to_line(self)

    @property
    def total(self):
        return self.unit_price * self.qty

    @property
    def size_label(self):
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

    def add(self, variation, qty=1):
        key = str(variation.pk)
        self.data[key] = self.fix_qty(variation, self.data.get(key, 0) + qty)
        self.save()
        return self.data[key]

    def set(self, variation, qty):
        if qty <= 0:
            self.remove(variation.pk)
            return 0
        self.data[str(variation.pk)] = self.fix_qty(variation, qty)
        self.save()
        return self.data[str(variation.pk)]

    def remove(self, variation_id):
        self.data.pop(str(variation_id), None)
        self.save()

    def clear(self):
        self.data = {}
        self.save()

    @property
    def count(self):
        return sum(self.data.values())

    def lines(self):
        ids = [int(k) for k in self.data]
        vs = Variation.objects.filter(pk__in=ids).select_related("product__image", "product__seller", "size").prefetch_related("attributes")
        by_id = {v.pk: v for v in vs}
        out = []
        for k, q in self.data.items():
            v = by_id.get(int(k))
            if v:
                out.append(Line(v, q))
        if len(out) != len(self.data):
            self.data = {str(line.variation.pk): line.qty for line in out}
            self.save()
        return out

    def summary(self):
        lines = self.lines()
        ok = [line for line in lines if not line.problem]
        from .offers import offer_total

        return {"lines": lines, "total": sum(line.total for line in ok), "has_problem": any(line.problem for line in lines),
                "offer_total": offer_total(ok)}
