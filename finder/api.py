"""API اپ فرش‌یاب (زیر /api/app/v1/finder/)."""
import json
from pathlib import Path

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.http import FileResponse, Http404
from django.utils import timezone

from api import serializers as S
from api.views import _int, endpoint, fail, ok
from catalog.views import card_queryset

from . import engine, services
from .models import FinderRequest, Need

PER_PAGE = 20
BUDGETS = [15, 25, 40, 60, 90, 130]  # میلیون تومان
EXAMPLES = [
    "فرش ضخیم و کلفت قرمز",
    "فرش سنتی ۹ متری زیر ۶۰ میلیون",
    "فرش ۶ متری زیر ۴۰ میلیون",
    "فرش کرم مدرن برای پذیرایی",
    "فرش اتاق کودک",
    "۱۲۰۰ شانه سرمه‌ای",
]


def _sizes():
    from pricing.models import Size

    out = []
    for s in Size.objects.filter(is_active=True, type__in=["rect", "runner", "round"]).order_by("sort_order", "pk"):
        out.append({"id": s.pk, "label": s.label, "type": s.type, "area": float(s.area or 0)})
    return out


@endpoint()
def config(request):
    data = cache.get("finder:config")
    if data is None:
        needs = engine.active_needs()
        groups = []
        for key, title in Need.Group.choices:
            items = [{"id": n.pk, "title": n.title, "subtitle": n.subtitle, "swatch": n.swatch, "icon": n.icon,
                      "count": engine.need_count(n)} for n in needs if n.group == key]
            items = [x for x in items if x["count"]]  # نیازی که الان فرشی ندارد نمایش داده نمی‌شود
            if items:
                groups.append({"key": key, "title": title, "needs": items})
        data = {"groups": groups, "sizes": _sizes(), "budgets": [b * 1_000_000 for b in BUDGETS], "examples": EXAMPLES}
        cache.set("finder:config", data, 600)
    return ok(data)


def wish_from(g):
    wish = engine.understand(g.get("q", "")[:300]) if g.get("q") else engine.Wish()
    ids = [_int(x) for x in (g.get("needs") or "").split(",") if x.strip()]
    if ids:
        extra = [n for n in engine.active_needs() if n.pk in ids and n not in wish.needs]
        wish.needs += extra
    if g.get("size"):
        from pricing.models import Size

        s = Size.objects.filter(pk=_int(g["size"])).first()
        if s:
            wish.sizes, wish.size_label = [s], s.label
    rids = [_int(x) for x in (g.get("reeds") or "").split(",") if x.strip()]
    if rids:
        from catalog.models import AttributeTerm

        wish.reeds += [t for t in AttributeTerm.objects.filter(pk__in=rids) if t not in wish.reeds]
    if g.get("max"):
        wish.max_price = _int(g["max"])
    if g.get("min"):
        wish.min_price = _int(g["min"])
    return wish


@endpoint()
def search(request):
    g = request.GET
    wish = wish_from(g)
    qs, relaxed = engine.search(wish, g.get("sort", "best"))
    page = max(1, _int(g.get("page"), 1))
    p = Paginator(card_queryset(qs), PER_PAGE)
    try:
        items = list(p.page(page).object_list) if p.count else []
    except EmptyPage:
        items = []
    if g.get("q") and page == 1:
        from growth.search_log import log as log_search

        log_search(g["q"], "finder", 0 if relaxed else p.count)
    ids = [x.pk for x in items]
    prices = engine.size_prices(ids, wish.sizes)
    whys = engine.why(ids, wish.needs) if wish.needs else {}
    results = []
    for x in items:
        c = S.card(x)
        if x.pk in prices:
            c["price"], c["price_is_from"] = prices[x.pk], False
            c["size_label"] = wish.size_label
        c["why"] = whys.get(x.pk, [])
        results.append(c)
    return ok({
        "understood": wish.chips(), "unknown": wish.words if not (wish.needs or wish.sizes or wish.reeds or wish.max_price) else "",
        # همان خواسته‌ها به شکل پارامتر، تا اپ بتواند یکی‌یکی حذفشان کند
        "applied": {"needs": [n.pk for n in wish.needs], "size": wish.sizes[0].pk if wish.sizes else None,
                    "min": wish.min_price or None, "max": wish.max_price or None, "reeds": [t.pk for t in wish.reeds]},
        "relaxed": relaxed, "count": p.count, "page": page, "pages": p.num_pages if p.count else 0, "results": results,
    })


def _req_row(r, request):
    products = list(card_queryset(r.products.published()))
    auto = []
    if r.auto_products:
        from catalog.models import Product

        by = {p.pk: p for p in card_queryset(Product.objects.published().filter(pk__in=r.auto_products))}
        auto = [S.card(by[i]) for i in r.auto_products if i in by]
    return {
        "id": r.pk, "kind": r.kind, "status": r.status, "status_label": r.get_status_display(), "text": r.text,
        "wanted": services.need_titles((r.wanted or {}).get("needs")), "query": (r.wanted or {}).get("q", ""),
        "photo": f"{settings.SITE_URL}/api/app/v1/finder/requests/{r.pk}/photo/?t={photo_token(r)}" if r.photo else "",
        "colors": [{"hex": c["hex"], "share": c.get("share", 0)} for c in r.colors if "hex" in c][:5],
        "color_names": [c["title"] for c in r.colors if "title" in c],
        "reply": r.reply, "products": [S.card(p) for p in products], "auto": auto,
        "created_at": timezone.localtime(r.created_at).isoformat(),
        "answered_at": timezone.localtime(r.answered_at).isoformat() if r.answered_at else None,
        "unread": bool(r.answered_at and not r.seen_at),
    }


@endpoint(methods=("GET", "POST"), login=True)
def requests(request):
    user = request.api_user
    if request.method == "GET":
        rows = FinderRequest.objects.filter(user=user).prefetch_related("products")[:50]
        data = [_req_row(r, request) for r in rows]
        return ok({"results": data, "unread": sum(1 for r in data if r["unread"])})
    photo = request.FILES.get("photo")
    text = (request.POST.get("text") or "").strip()
    try:
        wanted = json.loads(request.POST.get("wanted") or "{}")
    except ValueError:
        wanted = {}
    if not isinstance(wanted, dict):
        wanted = {}
    wanted = {k: wanted[k] for k in ("needs", "size", "max", "q") if k in wanted}
    if not photo and len(text) < 5 and not wanted:
        return fail("یک عکس از فرش بفرستید یا بنویسید چه فرشی می‌خواهید.")
    if photo:
        if photo.size > 12 * 1024 * 1024:
            return fail("حجم عکس زیاد است (حداکثر ۱۲ مگابایت).")
        try:
            from PIL import Image

            Image.open(photo).verify()
        except Exception:  # noqa: BLE001
            return fail("فایل فرستاده‌شده عکس نیست.")
    if FinderRequest.objects.filter(user=user, created_at__gte=timezone.now() - timezone.timedelta(hours=1)).count() >= 10:
        return fail("درخواست‌های زیادی فرستاده‌اید؛ کمی بعد دوباره امتحان کنید.", 429)
    from accounts.views import profile_of

    mobile = profile_of(user).mobile or user.username
    name = (request.POST.get("name") or user.get_full_name() or "").strip()
    r = services.create(user, mobile, name, text, wanted, photo)
    return ok(_req_row(r, request), status=201)


@endpoint(methods=("POST",), login=True)
def request_seen(request, pk):
    FinderRequest.objects.filter(pk=pk, user=request.api_user, seen_at__isnull=True, answered_at__isnull=False).update(
        seen_at=timezone.now())
    return ok({"ok": True})


PHOTO_SALT = "finder-photo"


def photo_token(r):
    """پیوند امضاشدهٔ عکس (اپ و وب بدون سرآیند ورود هم می‌توانند نشانش دهند)."""
    return signing.dumps(r.pk, salt=PHOTO_SALT, compress=True)


@endpoint()
def request_photo(request, pk):
    t = request.GET.get("t", "")
    if t:
        try:
            if signing.loads(t, salt=PHOTO_SALT, max_age=60 * 60 * 24 * 30) != pk:
                raise Http404
        except signing.BadSignature:
            raise Http404
        return _photo(FinderRequest.objects.filter(pk=pk).first())
    if request.api_user is None:
        return fail("ابتدا وارد شوید.", 401)
    return _photo(FinderRequest.objects.filter(pk=pk, user=request.api_user).first())


def _photo(r):
    if not r or not r.photo:
        raise Http404
    root = Path(settings.PRIVATE_ROOT).resolve()
    path = (root / r.photo).resolve()
    if root not in path.parents or not path.is_file():
        raise Http404
    resp = FileResponse(open(path, "rb"), content_type="image/jpeg")
    resp["Cache-Control"] = "private, max-age=3600"
    return resp


def panel_photo(request, pk):
    """عکس درخواست برای کارمندان پنل."""
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404
    return _photo(FinderRequest.objects.filter(pk=pk).first())
