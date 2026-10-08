"""ساخت متن هر فرش از روی قالب.

قواعد نوشتن قالب (برای کاربر پنل ساده نگه داشته شده):
  {متغیر}            مقدار؛ اگر خالی باشد کل آن خط نمایش داده نمی‌شود.
  [[ ... ]]          بخش اختیاری؛ فقط وقتی می‌آید که همهٔ متغیرهای داخلش مقدار داشته باشند.
  {لینک:دسته}        پیوند با متن پیش‌فرض؛ {لینک:دسته|متن دلخواه} با متن دلخواه.
                     هر نشانی در کل صفحه فقط یک بار پیوند می‌شود (دفعه‌های بعد متن ساده).
  ## تیتر  /  ### تیتر کوچک  /  - مورد فهرست  /  **پررنگ**  /  خط خالی = پاراگراف تازه
"""
import re
from dataclasses import dataclass

from django.core.cache import cache
from django.utils.html import escape

from core.templatetags.fa import fa_num, toman

VAR_RE = re.compile(r"\{([^{}\n]{1,80})\}")
OPT_RE = re.compile(r"\[\[(.*?)\]\]")
SOFT = {"برجسته"}  # خالی بودنشان خط را حذف نمی‌کند
BLOCK_VARS = {"قیمت_سایزها", "اقساط"}


def norm_key(name):
    return (name or "").strip().replace("ي", "ی").replace("ك", "ک").replace("‌", "_").replace(" ", "_")


def norm_text(s):
    """برای مقایسهٔ نام رنگ و نام فایل: بدون فاصله، نیم‌فاصله، خط تیره و حروف عربی."""
    s = (s or "").lower().replace("ي", "ی").replace("ك", "ک").replace("ة", "ه").replace("أ", "ا").replace("آ", "ا")
    return re.sub(r"[\s‌\-_.()]+", "", s)


def spec(p, *keys):
    for t in p.specs.all():
        label = (t.attribute.label or "").replace("‌", " ")
        if any(k in label for k in keys):
            return t.name
    return ""


def design_from_title(title):
    m = re.search(r"نقشه\s+(.+?)(?:\s+(?:زمینه|رنگ|سایز)\b|$)", title or "")
    return m.group(1).strip(" -–") if m else ""


def design_of(p):
    return (p.design_name or "").strip() or design_from_title(p.title)


def color_of(p):
    """رنگ زمینه؛ اگر در عنوان آمده («… زمینه کرم») همان، چون مشتری همان را می‌بیند."""
    m = re.search(r"زمینه\s+(.+?)(?:\s+(?:سایز|طرح|کد)\b|\s+[0-9۰-۹]|$)", p.title or "")
    return (m.group(1).strip(" -–") if m else "") or spec(p, "رنگ زمینه") or spec(p, "رنگ")


def brand_of(p):
    if p.brand_id:
        return p.brand.name
    b = spec(p, "برند", "کارخانه")
    if b:
        return b
    return (p.album.company or "").strip() if p.album_id else ""


def pile_of(p):
    pile = spec(p, "خاب")
    pile = re.sub(r"\s*(?:شده)?\s*با ضمانت.*$", "", pile).strip()
    return fa_num(pile.replace("%", "٪"))


@dataclass
class Link:
    href: str
    text: str


# ------------------------------------------------------------------ قالب هر فرش
def template_for(p):
    from .models import ContentTemplate

    key = f"ctpl:{_ver()}:{p.album_id or 0}:{p.primary_category_id or 0}"
    pk = cache.get(key)
    if pk is None:
        qs = ContentTemplate.objects.filter(is_active=True)
        t = None
        if p.album_id:
            t = qs.filter(albums=p.album_id).order_by("-updated_at").first()
        if t is None:
            cats = [p.primary_category_id] if p.primary_category_id else []
            cats += list(p.categories.values_list("pk", flat=True)) if p.pk else []
            if cats:
                t = qs.filter(categories__in=cats).order_by("-updated_at").first()
        if t is None:
            t = qs.filter(is_default=True).order_by("-updated_at").first()
        pk = t.pk if t else 0
        cache.set(key, pk, 300)
    return ContentTemplate.objects.filter(pk=pk).first() if pk else None


def _ver():
    v = cache.get("content:ver")
    if v is None:
        v = 1
        cache.set("content:ver", v, None)
    return v


def clear_cache():
    """بعد از تغییر قالب یا بخش‌های مشترک."""
    try:
        cache.incr("content:ver")
    except ValueError:
        cache.set("content:ver", 2, None)


# ------------------------------------------------------------------ متغیرها
class Ctx:
    """مقدار متغیرها، تنبل (فقط وقتی قالب لازمشان دارد حساب می‌شوند)."""

    def __init__(self, p, variations=None, page_url=""):
        from shop.models import ShopSettings

        from .models import ContentSettings

        self.p = p
        self._vars = variations
        self.page_url = page_url or p.get_absolute_url()
        self.cs = ContentSettings.load()
        self.shop = ShopSettings.load()
        self.used = {self.page_url}
        self._cache = {}

    # -------------------------------------------------- کمک‌ها
    def variations(self):
        if self._vars is None:
            self._vars = list(self.p.variations.select_related("size").order_by("size__sort_order", "menu_order"))
        return self._vars

    def priced(self):
        return [v for v in self.variations() if v.is_available and v.price and v.size_id]

    def attr_value(self, key):
        k = norm_key(key)
        for t in self.p.specs.all():
            if norm_key(t.attribute.label) == k:
                return fa_num(t.name)
        return None

    # -------------------------------------------------- مقدار یک متغیر
    def get(self, name):
        name = norm_key(name)
        if name in self._cache:
            return self._cache[name]
        val = self._compute(name)
        self._cache[name] = val
        return val

    def _compute(self, name):  # noqa: C901
        p, cs, shop = self.p, self.cs, self.shop
        if name.startswith("لینک:") or name.startswith("لینک_"):
            target, _, text = name[5:].partition("|")
            return self.link(target, text.replace("_", " ").strip())
        from core.autodesc import short_price

        simple = {
            "عنوان": lambda: fa_num(p.title),
            "نقشه": lambda: design_of(p),
            "رنگ": lambda: color_of(p),
            "شانه": lambda: fa_num(spec(p, "شانه")),
            "تراکم": lambda: fa_num(spec(p, "تراکم")),
            "جنس_نخ": lambda: pile_of(p),
            "دستگاه": lambda: spec(p, "دستگاه"),
            "درجه": lambda: spec(p, "درجه"),
            "برند": lambda: brand_of(p),
            "تعداد_رنگ": lambda: fa_num(p.color_count) if p.color_count else "",
            "برجسته": lambda: "برجسته" if "برجسته" in p.title else "",
            "یادداشت": lambda: (p.custom_note or "").strip(),
            "آلبوم": lambda: fa_num(p.album.title) if p.album_id else "",
            "دسته": lambda: p.primary_category.name if p.primary_category_id else "",
            "ماه": lambda: " ".join(__import__("pricing.pricelist", fromlist=["month_year"]).month_year()),
            "زمان_آماده_سازی": lambda: cs.prep_time,
            "هزینه_ارسال": lambda: cs.shipping_cost,
            "جریمه_لغو": lambda: fa_num(cs.cancel_penalty) if cs.cancel_penalty else "",
            "ضمانت": lambda: cs.warranty,
            "بیعانه": lambda: f"{fa_num(shop.deposit_percent)}٪" if shop.allow_deposit and shop.deposit_percent else "",
            "حد_ارسال_رایگان": lambda: f"{short_price(shop.free_shipping_min)} تومان" if shop.free_shipping_min else "",
            "ارسال_رایگان": self._free_shipping,
            "جفتی": self._pair,
            "گره": self._knots,
            "قیمت_پایه": lambda: self._base()[1],
            "سایز_پایه": lambda: self._base()[0],
        }
        if name in simple:
            return simple[name]() or ""
        if name == "قیمت_سایزها":
            return self._sizes_inline()
        if name == "اقساط":
            return self._plans_inline()
        v = self.attr_value(name)  # هر ویژگی با نام خودش، مثل {دستگاه_بافت}
        return v or ""

    def _free_shipping(self):
        shop = self.shop
        if not shop.allow_full:
            return ""
        if not shop.free_shipping_min:
            return "ارسال رایگان با پرداخت کامل آنلاین"
        from core.autodesc import short_price

        return f"ارسال رایگان با پرداخت کامل آنلاین (برای سفارش‌های بالای {short_price(shop.free_shipping_min)} تومان)"

    def _pair(self):
        c = color_of(self.p)
        if not c:
            return ""
        nc = norm_text(c)
        if any(norm_text(x) and (norm_text(x) == nc or nc.startswith(norm_text(x))) for x in self.cs.pair_list()):
            return self.cs.pair_note.replace("{رنگ}", c)
        return ""

    def _knots(self):
        try:
            r, d = int(re.sub(r"\D", "", spec(self.p, "شانه"))), int(re.sub(r"\D", "", spec(self.p, "تراکم")))
        except ValueError:
            return ""
        return toman(r * d) if r and d else ""

    def _base(self):
        p = self.p
        rows = self.priced()
        if not rows:
            return "", ""
        base = None
        if p.album_id:
            base = next((v for v in rows if v.size_id == p.album.base_size_id), None)
        base = base or max(rows, key=lambda v: float(v.size.area or 0))
        return fa_num((base.size.label or "").split("(")[0].strip()), toman(base.price)

    def size_rows(self):
        out, seen = [], set()
        for v in self.priced():
            lbl = (v.size.label or "").split("(")[0].strip()
            if lbl in seen:
                continue
            seen.add(lbl)
            out.append((fa_num(lbl), fa_num(v.size.dimensions or ""), v))
        return out

    def _sizes_inline(self):
        from core.autodesc import short_price

        return "، ".join(f"{lbl} {short_price(v.price)}" for lbl, _d, v in self.size_rows()[:6]) + (" تومان" if self.priced() else "")

    def sizes_block(self):
        rows = self.size_rows()
        if not rows:
            return ""
        lis = []
        for lbl, dims, v in rows:
            price = f"<strong>{toman(v.price)}</strong> تومان"
            if v.on_sale:
                price = f"<del>{toman(v.final_price)}</del> " + price
            dim = f" <small>({escape(dims)})</small>" if dims and dims not in lbl else ""
            lis.append(f"<li><span>{escape(lbl)}{dim}</span> <span>{price}</span></li>")
        return '<ul class="price-lines">' + "".join(lis) + "</ul>"

    def plans(self):
        from installments.services import active_plans, describe

        return [(pl.title, describe(pl)) for pl in active_plans()]

    def _plans_inline(self):
        return "، ".join(t for t, _ in self.plans())

    def plans_block(self):
        rows = self.plans()
        if not rows:
            return ""
        return "<ul>" + "".join(f"<li><strong>{escape(t)}</strong>: {escape(d)}</li>" for t, d in rows) + "</ul>"

    # -------------------------------------------------- پیوندها
    def link(self, target, text=""):
        target = norm_key(target).replace("_", "")
        href, default = self._link_target(target)
        text = text or default
        if not href or not text:
            return ""
        return Link(href, text)

    def _link_target(self, t):
        p = self.p
        if t in ("دسته", "گروه"):
            c = p.primary_category if p.primary_category_id else p.categories.first()
            return (c.get_absolute_url(), fa_num(c.name)) if c else ("", "")
        if t in ("لیستقیمت", "آلبوم"):
            a = p.album if p.album_id else None
            if a and a.slug and a.in_price_list and a.is_active:
                return a.get_absolute_url(), f"لیست قیمت {fa_num(a.title)}"
            return "", ""
        if t in ("۱۲متری", "12متری", "سایزپایه"):
            return self._landing_base()
        if t in ("اقساطی", "اقساط"):
            from installments.services import active_plans, page_url

            url = page_url() if active_plans() else ""
            return url, "خرید اقساطی فرش"
        if t == "برند":
            b = p.brand if p.brand_id else None
            return (b.get_absolute_url(), b.name) if b else ("", "")
        if t == "رنگ":
            for term in p.specs.all():
                if "رنگ" in (term.attribute.label or "") and term.attribute.is_public:
                    return term.get_absolute_url(), f"فرش {term.name}"
            return "", ""
        return "", ""

    def _landing_base(self):
        p = self.p
        if not p.album_id:
            return "", ""
        reeds = [t.pk for t in p.specs.all() if "شانه" in (t.attribute.label or "")]
        if not reeds:
            return "", ""
        from landing.build import live

        lp = live().filter(reeds_id__in=reeds, size_id=p.album.base_size_id, color=None, style=None).first()
        return (lp.get_absolute_url(), fa_num(lp.title)) if lp else ("", "")


# ------------------------------------------------------------------ موتور
def _value_html(ctx, val):
    if isinstance(val, Link):
        if val.href in ctx.used:
            return escape(val.text)
        ctx.used.add(val.href)
        return f'<a href="{escape(val.href)}">{escape(val.text)}</a>'
    return escape(val)


def _fill(ctx, text):
    """(html، خالی‌ماند؟) — جایگذاری متغیرهای یک تکه متن."""
    out, pos, missing = [], 0, False
    for m in VAR_RE.finditer(text):
        out.append(escape(text[pos:m.start()]))
        name = norm_key(m.group(1))
        val = ctx.get(name)
        if not val and name not in SOFT:
            missing = True
        out.append(_value_html(ctx, val) if val else "")
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out), missing


def _line(ctx, raw):
    """یک خط قالب ← html یا None (اگر باید حذف شود)."""
    # بخش‌های اختیاری؛ اول بررسی می‌شوند تا پیوندهای حذف‌شده «مصرف» نشوند
    parts, pos = [], 0
    for m in OPT_RE.finditer(raw):
        parts.append(("t", raw[pos:m.start()]))
        parts.append(("o", m.group(1)))
        pos = m.end()
    parts.append(("t", raw[pos:]))
    # اگر متغیر لازمی خالی است، خط بی‌آنکه پیوندی «مصرف» شود حذف می‌شود
    for kind, txt in parts:
        if kind == "t" and any(not ctx.get(n) and n not in SOFT for n in map(norm_key, VAR_RE.findall(txt))):
            return None
    html = []
    for kind, txt in parts:
        if kind == "o" and any(not ctx.get(n) for n in map(norm_key, VAR_RE.findall(txt))):
            continue
        html.append(_fill(ctx, txt)[0])
    out = re.sub(r"[ \t]{2,}", " ", "".join(html)).strip()
    # «- ، دستگاه …» وقتی بخش اختیاری اول حذف شده
    return re.sub(r"^((?:#{2,3}|-|•)\s+)?[،؛,:\s]+", lambda m: m.group(1) or "", out)


def _inline(html):
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)


def render(src, ctx):
    """متن قالب ← HTML"""
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            items.clear()

    for raw in (src or "").replace("\r\n", "\n").split("\n"):
        s = raw.strip()
        if not s:
            flush()
            continue
        key = norm_key(s[1:-1]) if s.startswith("{") and s.endswith("}") and s.count("{") == 1 else ""
        if key in BLOCK_VARS:
            flush()
            block = ctx.sizes_block() if key == "قیمت_سایزها" else ctx.plans_block()
            if block:
                out.append(block)
            continue
        h = _line(ctx, s)
        if not h or not re.sub(r"[\s.،؛:\-#•]", "", h):
            continue
        if h.startswith("### "):
            flush()
            out.append(f"<h3>{_inline(h[4:].strip())}</h3>")
        elif h.startswith("## "):
            flush()
            out.append(f"<h2>{_inline(h[3:].strip())}</h2>")
        elif h.startswith("- ") or h.startswith("• "):
            if para:
                out.append("<p>" + " ".join(para) + "</p>")
                para.clear()
            items.append(_inline(h[2:].strip()))
        else:
            if items:
                flush()
            para.append(_inline(h))
    flush()
    # تیتری که زیرش چیزی نماند حذف شود
    cleaned = []
    for i, block in enumerate(out):
        if block.startswith("<h") and (i + 1 == len(out) or out[i + 1].startswith("<h")):
            continue
        cleaned.append(block)
    return "\n".join(cleaned)


def render_title(pattern, ctx):
    h = _line(ctx, pattern or "") or ""
    import html as _html

    return _html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def blocks_for(p):
    from .models import InfoBlock

    key = f"cblk:{_ver()}:{p.album_id or 0}"
    ids = cache.get(key)
    if ids is None:
        qs = InfoBlock.objects.filter(is_active=True).prefetch_related("albums")
        ids = [b.pk for b in qs if not b.albums.all() or any(a.pk == p.album_id for a in b.albums.all())]
        cache.set(key, ids, 300)
    by = {b.pk: b for b in InfoBlock.objects.filter(pk__in=ids)}
    return [by[i] for i in ids if i in by]


def build(p, variations=None):
    """{"html": توضیحات، "bullets": خلاصه، "blocks": [{title, html, open}], "templated": bool}"""
    ctx = Ctx(p, variations)
    templated = False
    html, bullets = p.content or "", p.short_description or ""
    if p.use_template:
        t = template_for(p)
        if t:
            templated = True
            html = render(t.body, ctx)
            b = render(t.bullets, ctx)
            if b and not b.startswith("<ul>"):  # خلاصه همیشه فهرست
                b = b.replace("<p>", "<ul><li>").replace("</p>", "</li></ul>")
            bullets = b
    else:
        # پیوندهایی که در متن دستی هست هم «مصرف‌شده» حساب شوند تا بخش‌های پایین تکرارشان نکنند
        for href in re.findall(r'href="([^"]+)"', html):
            from django.conf import settings

            ctx.used.add(href.replace(settings.SITE_URL, "") or "/")
    blocks = []
    if getattr(p, "seller_id", None):  # کالای فروشندهٔ مارکت‌پلیس: شرایط خود فروشنده، نه متن‌های ایران کارپت
        from market.render import seller_block

        return {"html": html, "bullets": bullets, "blocks": [seller_block(p)], "templated": False}
    for b in blocks_for(p):
        h = render(b.body, ctx)
        if re.sub(r"<[^>]+>|\s", "", h):
            blocks.append({"title": b.title, "html": h, "open": b.is_open})
    return {"html": html, "bullets": bullets, "blocks": blocks, "templated": templated}


def to_text(html):
    """HTML ← متن ساده با شکستن خط (برای اپ و پیام‌رسان‌ها)."""
    import html as _html

    s = html or ""
    s = re.sub(r"(?i)<li[^>]*>", "• ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(?:p|li|h[1-6]|ul|div|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", x).strip() for x in s.split("\n")]
    out = []
    for x in lines:
        if x or (out and out[-1]):
            out.append(x)
    return "\n".join(out).strip()


def full_text(data):
    parts = [to_text(data["html"])]
    for b in data["blocks"]:
        parts.append(f"{b['title']}\n{to_text(b['html'])}")
    return "\n\n".join(x for x in parts if x)


def summary_text(p, data=None):
    data = data or build(p)
    return to_text(data["bullets"])


# ------------------------------------------------------------------ رنگ‌های دیگر همین نقشه
def color_siblings(p, limit=16):
    from catalog.models import Product

    design = design_of(p)
    if not design or not p.album_id:
        return []
    qs = (Product.objects.published().filter(album_id=p.album_id)
          .filter(models_q_design(design)).select_related("image").prefetch_related("specs__attribute").order_by("title"))
    items = [x for x in qs[:limit + 1] if norm_text(design_of(x)) == norm_text(design)]
    if len(items) < 2:
        return []
    return [{"product": x, "color": color_of(x) or x.title, "current": x.pk == p.pk} for x in items[:limit]]


def models_q_design(design):
    from django.db.models import Q

    return Q(design_name__iexact=design) | Q(design_name="", title__contains=f"نقشه {design}")
