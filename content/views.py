"""پنل: ساخت گروهی فرش‌های یک نقشه، پیش‌نمایش قالب، جایگزینی متن و پاک‌سازی لینک‌ها."""
import re
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import escape

from catalog.models import Attribute, AttributeTerm, Category, Product
from core.models import Media
from core.templatetags.fa import fa_num
from dashboard.ac import unique_slug
from dashboard.auth import clear_site_cache, staff_required
from dashboard.models import log
from pricing.models import Album

from . import render as R
from .models import ContentEdit, ContentTemplate


# ================================================================== کمک‌ها
def color_attribute():
    a = Attribute.objects.filter(label__contains="رنگ زمینه").first() or Attribute.objects.filter(slug__contains="color").first()
    return a or Attribute.objects.filter(label__contains="رنگ").order_by("order").first()


def template_for_album(album_id, category_ids=()):
    qs = ContentTemplate.objects.filter(is_active=True)
    t = qs.filter(albums=album_id).order_by("-updated_at").first() if album_id else None
    if t is None and category_ids:
        t = qs.filter(categories__in=list(category_ids)).order_by("-updated_at").first()
    return t or qs.filter(is_default=True).order_by("-updated_at").first()


class ValuesCtx:
    """برای ساخت عنوان پیش از وجود فرش."""

    def __init__(self, values):
        self.values = {R.norm_key(k): v for k, v in values.items()}
        self.used = set()

    def get(self, name):
        return self.values.get(R.norm_key(name), "")


def make_title(pattern, values):
    return R.render_title(pattern or "فرش {شانه} شانه[[ {برجسته}]] نقشه {نقشه} زمینه {رنگ}", ValuesCtx(values))


def match_images(medias, colors):
    """medias: [(id, نام فایل)]، colors: [نام] ← {اندیس رنگ: [شناسهٔ تصویرها]} — بلندترین نام رنگی که در نام فایل باشد."""
    out = {i: [] for i in range(len(colors))}
    norms = [(i, R.norm_text(c)) for i, c in enumerate(colors) if R.norm_text(c)]
    for mid, name in medias:
        fn = R.norm_text(name)
        hits = [(len(n), i) for i, n in norms if n in fn]
        if hits:
            out[max(hits)[1]].append(mid)
    return out


def sample_of(album, sample_id=None):
    if sample_id:
        p = Product.objects.filter(pk=sample_id).first()
        if p:
            return p
    if album:
        return (Product.objects.filter(album=album).exclude(specs=None).order_by("-status", "-published_at").first()
                or Product.objects.filter(album=album).order_by("-published_at").first())
    return None


def spec_value(terms, *keys):
    for t in terms:
        label = (t.attribute.label or "").replace("‌", " ")
        if any(k in label for k in keys):
            return t.name
    return ""


# ================================================================== ساخت گروهی
@staff_required
def bulk(request):
    attr = color_attribute()
    colors = list(AttributeTerm.objects.filter(attribute=attr).order_by("order", "name")) if attr else []
    albums = list(Album.objects.filter(is_active=True).order_by("sort_order", "name"))
    from rajyar.models import RajyarSettings

    rs = RajyarSettings.load()
    rajyar = {"enabled": bool(rs.enabled and rs.api_key and rs.channel_ids), "auto": rs.auto_new}
    P = request.POST
    step = P.get("step") or "start"
    ctx = {"albums": albums, "colors": colors, "attr": attr, "rajyar": rajyar, "data": P.dict(),
           "sel_colors": P.getlist("colors"), "spec_ids": [x for x in P.getlist("specs") if x.isdigit()]}

    if request.method == "POST" and step in ("preview", "create"):
        album = Album.objects.filter(pk=P.get("album") or 0).first()
        design = re.sub(r"\s+", " ", (P.get("design") or "").strip())[:120]
        errors = []
        if not album:
            errors.append("آلبوم را انتخاب کنید.")
        if not design:
            errors.append("نام نقشه را بنویسید.")
        chosen = _chosen_colors(P, colors, attr)
        if not chosen:
            errors.append("دست‌کم یک رنگ زمینه انتخاب کنید.")
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, "content/bulk.html", ctx)
        sample = sample_of(album, P.get("sample"))
        terms = list(sample.specs.select_related("attribute")) if sample else []
        extra_terms = list(AttributeTerm.objects.filter(pk__in=[x for x in P.getlist("specs") if x.isdigit()]).select_related("attribute"))
        if extra_terms:  # مشخصاتی که کاربر داده جای همان ویژگی‌های نمونه را می‌گیرد
            attrs = {t.attribute_id for t in extra_terms}
            terms = [t for t in terms if t.attribute_id not in attrs] + extra_terms
        terms = [t for t in terms if not attr or t.attribute_id != attr.pk]
        cats = list(Category.objects.filter(pk__in=[x for x in P.getlist("categories") if x.isdigit()]))
        if not cats and sample:
            cats = list(sample.categories.all())
        tpl = template_for_album(album.pk, [c.pk for c in cats])
        media_ids = [int(x) for x in (P.get("media_ids") or "").split(",") if x.strip().isdigit()]
        medias = list(Media.objects.filter(pk__in=media_ids))
        medias.sort(key=lambda m: media_ids.index(m.pk))
        base = {
            "شانه": fa_num(spec_value(terms, "شانه")), "تراکم": fa_num(spec_value(terms, "تراکم")), "نقشه": design,
            "برجسته": "برجسته" if P.get("embossed") else "",
            "برند": (sample.brand.name if sample and sample.brand_id else spec_value(terms, "برند")) or album.company,
        }
        if step == "preview":
            auto = match_images([(m.pk, m.title or m.file.name.rsplit("/", 1)[-1]) for m in medias], [c.name for c in chosen])
            rows = []
            for i, c in enumerate(chosen):
                title = fa_num(make_title(tpl.title_pattern if tpl else "", {**base, "رنگ": c.name}))
                rows.append({"i": i, "color": c, "title": title, "imgs": auto.get(i, []),
                             "dup": Product.objects.filter(title__in=[title, title.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))]).first()})
            ctx.update({"step": "preview", "album": album, "design": design, "rows": rows, "medias": medias, "sample": sample,
                        "terms": terms, "cats": cats, "tpl": tpl, "unmatched": [m for m in medias if not any(m.pk in r["imgs"] for r in rows)]})
            return render(request, "content/bulk.html", ctx)

        # ---------------------------------------------------------- ساخت
        created = []
        with transaction.atomic():
            for i, c in enumerate(chosen):
                if not P.get(f"make_{i}"):
                    continue
                if not c.pk:
                    c.slug = unique_slug(AttributeTerm, c.name)
                    c = AttributeTerm.objects.filter(attribute=attr, name=c.name).first() or AttributeTerm.objects.create(
                        attribute=attr, name=c.name, slug=c.slug)
                title = (P.get(f"title_{i}") or "").strip()[:300] or make_title(tpl.title_pattern if tpl else "", {**base, "رنگ": c.name})
                imgs = [int(x) for x in P.getlist(f"img_{i}") if x.isdigit()]
                imgs = [m for m in imgs if m in media_ids]
                p = Product(
                    title=title, slug=unique_slug(Product, title), album=album, status="publish" if P.get("status") == "publish" else "draft",
                    use_template=True, design_name=design, color_count=int(P["color_count"]) if (P.get("color_count") or "").isdigit() else None,
                    custom_note=(P.get("note") or "").strip(), brand=sample.brand if sample else None,
                    primary_category=(sample.primary_category if sample and sample.primary_category in cats else (cats[0] if cats else None)),
                    image_id=imgs[0] if imgs else None, published_at=timezone.now(), modified_at=timezone.now(),
                    english_name="", video_url="",
                )
                p.save()
                p.specs.set(terms + [c])
                p.categories.set(cats)
                if sample:
                    p.tags.set(sample.tags.all())
                from catalog.models import ProductImage

                ProductImage.objects.bulk_create([ProductImage(product=p, media_id=m, order=k) for k, m in enumerate(imgs)])
                Media.objects.filter(pk__in=imgs, alt="").update(alt=title[:500])
                created.append(p)
            if created:
                from pricing.albums import sync_album_variations

                sync_album_variations(list(Product.objects.filter(pk__in=[p.pk for p in created]).select_related("album")))
                for p in Product.objects.filter(pk__in=[p.pk for p in created]).select_related("album"):
                    p.refresh_price_cache()
        for p in created:
            log(request, "create", "محصولات", p, "ساخت گروهی")
        clear_site_cache()
        R.clear_cache()
        msg = f"{fa_num(len(created))} فرش نقشهٔ «{design}» ساخته شد"
        msg += "" if P.get("status") == "publish" else " (پیش‌نویس)"
        if created and P.get("rajyar") and rajyar["enabled"] and not rajyar["auto"] and P.get("status") == "publish":
            msg += "؛ " + _send_rajyar(created, rs)
        messages.success(request, msg + ".")
        return redirect(f"/panel/products/?album={album.pk}&sort=-published_at")

    return render(request, "content/bulk.html", {**ctx, "step": "start"})


def _chosen_colors(P, colors, attr):
    by = {str(c.pk): c for c in colors}
    if (P.get("rows_n") or "").isdigit():  # مرحلهٔ ساخت: همان ترتیب پیش‌نمایش
        out = []
        for i in range(min(int(P["rows_n"]), 60)):
            v = P.get(f"row_{i}") or ""
            out.append(by.get(v) if v in by else AttributeTerm(attribute=attr, name=v[4:104]) if v.startswith("new:") else None)
        return [c for c in out if c is not None]
    chosen = [c for c in colors if str(c.pk) in P.getlist("colors")]
    for n in [x.strip() for x in re.split(r"[،,\n]", P.get("new_colors") or "") if x.strip()]:
        if not any(R.norm_text(c.name) == R.norm_text(n) for c in chosen):
            hit = next((c for c in colors if R.norm_text(c.name) == R.norm_text(n)), None)
            chosen.append(hit or AttributeTerm(attribute=attr, name=n[:100]))
    return chosen


def _send_rajyar(products, s):
    from rajyar.client import RajyarError, send

    gap = timezone.timedelta(minutes=max(s.interval_minutes, 1))
    ok = 0
    for i, p in enumerate(products):
        try:
            post = send(Product.objects.get(pk=p.pk), publish_at=timezone.now() + gap * i if i else None, s=s)
        except RajyarError as e:
            return f"ارسال به کانال‌ها انجام نشد: {e}"
        ok += post.status != "failed"
    return f"{fa_num(ok)} پست برای کانال‌ها زمان‌بندی شد (هر {fa_num(s.interval_minutes)} دقیقه یکی)"


# ================================================================== پیش‌نمایش قالب
@staff_required
def preview(request, pk):
    tpl = get_object_or_404(ContentTemplate, pk=pk)
    pid = request.GET.get("product")
    p = Product.objects.filter(pk=pid).first() if (pid or "").isdigit() else None
    if p is None:
        albums = list(tpl.albums.values_list("pk", flat=True))
        qs = Product.objects.published().exclude(variations=None)
        p = (qs.filter(album__in=albums) if albums else qs.filter(album__isnull=False)).order_by("-published_at").first() or qs.first()
    if p is None:
        raise Http404
    ctx = R.Ctx(p)
    data = {"html": R.render(tpl.body, ctx), "bullets": R.render(tpl.bullets, ctx), "blocks": []}
    for b in R.blocks_for(p):
        h = R.render(b.body, ctx)
        if re.sub(r"<[^>]+>|\s", "", h):
            data["blocks"].append({"title": b.title, "html": h, "open": b.is_open})
    title = make_title(tpl.title_pattern, {k: ctx.get(k) for k in ("شانه", "تراکم", "نقشه", "رنگ", "برجسته", "برند")})
    return render(request, "content/preview.html", {"tpl": tpl, "p": p, "doc": data, "title_sample": title})


# ================================================================== جایگزینی متن و لینک‌ها
FIELDS = {"content": "توضیحات کامل", "short_description": "توضیح کوتاه"}
VAGUE = ("اینجا", "کلیک کنید", "اینجا کلیک", "این لینک", "بیشتر بخوانید", "click here", "here")
A_RE = re.compile(r"<a\b[^>]*?href=(['\"])(.*?)\1[^>]*>(.*?)</a>", re.I | re.S)
H_RE = re.compile(r"<h[1-6]\b[^>]*>.*?</h[1-6]>", re.I | re.S)


def _scope(P):
    qs = Product.objects.filter(use_template=False) if P.get("only_manual", "1") == "1" else Product.objects.all()
    if (P.get("album") or "").isdigit():
        qs = qs.filter(album_id=P["album"])
    return qs


def _snippet(text, find, repl=None, width=60):
    i = text.find(find)
    if i < 0:
        return ""
    a, b = max(0, i - width), min(len(text), i + len(find) + width)
    before, after = escape(text[a:i]), escape(text[i + len(find):b])
    mid = f"<del>{escape(find)}</del>" + (f"<ins>{escape(repl)}</ins>" if repl is not None else "")
    return ("…" if a else "") + before + mid + after + ("…" if b < len(text) else "")


def _internal_path(href):
    u = urlparse(href.strip())
    host = urlparse(settings.SITE_URL).netloc
    if u.scheme in ("mailto", "tel", "javascript"):
        return None
    if u.netloc and u.netloc.replace("www.", "") != host.replace("www.", ""):
        return None
    return unquote(u.path or "/") or "/"


def _check(paths):
    """{مسیر: (کد، مقصد)} — بررسی واقعی نشانی‌ها با کلاینت داخلی جنگو."""
    from django.test import Client

    c = Client(HTTP_HOST=urlparse(settings.SITE_URL).netloc or "localhost")
    out = {}
    for path in list(paths)[:200]:
        try:
            r = c.get(path, secure=settings.SITE_URL.startswith("https"))
            out[path] = (r.status_code, r.get("Location", "") if r.status_code in (301, 302, 307, 308) else "")
        except Exception:  # noqa: BLE001
            out[path] = (0, "")
    return out


def audit(qs, check=True):
    """مشکل‌های لینک در متن دستی فرش‌ها."""
    kinds = {k: {"label": l, "n": 0, "products": []} for k, l in (
        ("home", "پیوند کلمه به صفحهٔ اول سایت"), ("heading", "پیوند داخل تیتر"), ("vague", "متن پیوند نامفهوم (اینجا، کلیک کنید)"),
        ("repeat", "پیوند تکراری به یک نشانی در یک صفحه"), ("broken", "پیوند خراب (۴۰۴ یا ۴۱۰)"), ("redirect", "پیوند به نشانی قدیمی که منتقل شده"))}
    paths = {}
    rows = list(qs.only("pk", "title", "content", "short_description"))
    for p in rows:
        for field in FIELDS:
            for m in A_RE.finditer(getattr(p, field) or ""):
                path = _internal_path(m.group(2))
                if path:
                    paths.setdefault(path, set()).add(p.pk)
    status = _check(paths) if check else {}
    for p in rows:
        found = set()
        for field in FIELDS:
            html = getattr(p, field) or ""
            seen = set()
            for m in A_RE.finditer(html):
                href, text = m.group(2), re.sub(r"<[^>]+>", "", m.group(3)).strip()
                path = _internal_path(href)
                if path == "/":
                    found.add("home")
                if text.strip(" .،") in VAGUE:
                    found.add("vague")
                if path in seen:
                    found.add("repeat")
                seen.add(path)
                code = status.get(path, (200, ""))[0] if path else 200
                if code in (404, 410):
                    found.add("broken")
                elif code in (301, 302, 307, 308):
                    found.add("redirect")
            if any(A_RE.search(h) for h in H_RE.findall(html)):
                found.add("heading")
        for k in found:
            kinds[k]["n"] += 1
            if len(kinds[k]["products"]) < 8:
                kinds[k]["products"].append(p)
    return kinds, status, len(rows)


def fix_links(html, kinds, status):
    """پیوندهای مشکل‌دار ← متن ساده (یا نشانی تازه برای منتقل‌شده‌ها)."""
    seen = set()

    def unlink(m):
        return m.group(3)

    def one(m):
        href, inner = m.group(2), m.group(3)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        path = _internal_path(href)
        code, loc = status.get(path, (200, "")) if path else (200, "")
        if "home" in kinds and path == "/":
            return inner
        if "vague" in kinds and text.strip(" .،") in VAGUE:
            return inner
        if "broken" in kinds and code in (404, 410):
            return inner
        if "repeat" in kinds and path is not None:
            if path in seen:
                return inner
            seen.add(path)
        if "redirect" in kinds and code in (301, 302, 307, 308) and loc:
            return m.group(0).replace(href, loc.replace(settings.SITE_URL, ""), 1)
        return m.group(0)

    if "heading" in kinds:
        html = H_RE.sub(lambda h: A_RE.sub(unlink, h.group(0)), html)
    return A_RE.sub(one, html)


@staff_required
def tools(request):
    P = request.POST if request.method == "POST" else request.GET
    albums = Album.objects.order_by("sort_order", "name")
    ctx = {"albums": albums, "data": P.dict(), "fields": FIELDS,
           "stats": {"template": Product.objects.filter(use_template=True).count(), "manual": Product.objects.filter(use_template=False).count()},
           "edits": ContentEdit.objects.select_related("user")[:8], "hits": None,
           "find": P.get("find", ""), "repl": P.get("replace", ""), "album_sel": P.get("album", ""), "chosen_fields": P.getlist("field")}
    do = P.get("do")
    if do in ("preview", "replace"):
        find, repl = P.get("find") or "", P.get("replace") or ""
        fields = [f for f in P.getlist("field") if f in FIELDS] or ["content"]
        if len(find.strip()) < 2:
            messages.error(request, "عبارت جستجو دست‌کم ۲ حرف باشد.")
            return render(request, "content/tools.html", ctx)
        hits = []
        for p in _scope(P).only("pk", "title", *fields):
            for f in fields:
                txt = getattr(p, f) or ""
                n = txt.count(find)
                if n:
                    hits.append((p, f, n, _snippet(txt, find, repl)))
        if do == "replace" and request.method == "POST":
            backup = []
            with transaction.atomic():
                for p, f, _n, _s in hits:
                    old = getattr(p, f)
                    backup.append({"id": p.pk, "field": f, "old": old})
                    Product.objects.filter(pk=p.pk).update(**{f: old.replace(find, repl), "modified_at": timezone.now()})
                edit = ContentEdit.objects.create(user=request.user, backup=backup,
                                                  summary=f"«{find[:60]}» ← «{repl[:60]}» در {len({h[0].pk for h in hits})} فرش")
            log(request, "update", "محصولات", None, edit.summary)
            clear_site_cache()
            messages.success(request, f"جایگزین شد: {edit.summary}. اگر اشتباه بود، از «سابقهٔ تغییرها» برگردانید.")
            return redirect("/panel/content-tools/")
        ctx.update({"hits": hits[:40], "hit_products": len({h[0].pk for h in hits}), "hit_total": sum(h[2] for h in hits),
                    "find": find, "repl": repl, "chosen_fields": fields})
    elif do in ("audit", "fix"):
        qs = _scope(P)
        kinds, status, n = audit(qs)
        if do == "fix" and request.method == "POST":
            chosen = [k for k in P.getlist("kind") if k in kinds]
            backup, changed = [], 0
            with transaction.atomic():
                for p in qs.only("pk", *FIELDS):
                    upd = {}
                    for f in FIELDS:
                        old = getattr(p, f) or ""
                        new = fix_links(old, chosen, status)
                        if new != old:
                            upd[f] = new
                            backup.append({"id": p.pk, "field": f, "old": old})
                    if upd:
                        Product.objects.filter(pk=p.pk).update(**upd, modified_at=timezone.now())
                        changed += 1
                if backup:
                    edit = ContentEdit.objects.create(user=request.user, backup=backup,
                                                      summary=f"اصلاح لینک‌ها ({'، '.join(kinds[k]['label'] for k in chosen)}) در {changed} فرش")
                    log(request, "update", "محصولات", None, edit.summary)
            clear_site_cache()
            messages.success(request, f"لینک‌های {fa_num(changed)} فرش اصلاح شد." if changed else "لینکی برای اصلاح پیدا نشد.")
            return redirect("/panel/content-tools/?do=audit" + (f"&album={P['album']}" if (P.get("album") or "").isdigit() else ""))
        ctx.update({"kinds": kinds, "audited": n,
                    "bad_paths": sorted(((p, c, l) for p, (c, l) in status.items() if c not in (200,)), key=lambda x: -x[1])[:40]})
    elif do == "undo" and request.method == "POST":
        edit = get_object_or_404(ContentEdit, pk=P.get("edit"), undone=False)
        with transaction.atomic():
            for row in reversed(edit.backup):
                if row.get("field") in FIELDS:
                    Product.objects.filter(pk=row["id"]).update(**{row["field"]: row["old"]})
            edit.undone = True
            edit.save(update_fields=["undone"])
        log(request, "update", "محصولات", None, f"برگرداندن: {edit.summary}")
        clear_site_cache()
        messages.success(request, f"برگردانده شد: {edit.summary}")
        return redirect("/panel/content-tools/")
    return render(request, "content/tools.html", ctx)
