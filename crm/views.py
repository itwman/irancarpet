from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from dashboard.auth import staff_required

from . import report, segments


@staff_required
def report_view(request):
    try:
        days = int(request.GET.get("days", 90))
    except ValueError:
        days = 90
    days = days if days in (7, 30, 90, 180, 365, 0) else 90
    return render(request, "crm/report.html", {"r": report.build(days), "days": days,
                                               "periods": [(7, "۷ روز"), (30, "۳۰ روز"), (90, "۳ ماه"), (180, "۶ ماه"),
                                                           (365, "یک سال"), (0, "همه")]})


@staff_required
def segments_view(request, key=None):
    from django.shortcuts import redirect

    from accounts.utils import normalize_mobile

    q = (request.GET.get("q") or "").strip()
    if q and normalize_mobile(q):
        return redirect(f"/panel/crm/customer/{normalize_mobile(q)}/")
    counts = segments.counts()
    rows, page = [], None
    if q:
        ql = q.replace("ي", "ی").replace("ك", "ک")
        rows = [c for c in segments.customers().values() if ql in (c.get("full_name") or "") or q in c["mobile"]]
        rows.sort(key=lambda c: -(c["total"] or 0))
        page = Paginator(rows, 50).get_page(request.GET.get("page"))
    elif key:
        if key not in segments.SEGMENTS:
            raise Http404
        rows = segments.audience(key)
        page = Paginator(rows, 50).get_page(request.GET.get("page"))
    return render(request, "crm/segments.html", {
        "cards": [(k, v, counts.get(k, 0), segments.HINTS.get(k, "")) for k, v in segments.SEGMENTS.items()], "key": key,
        "title": segments.SEGMENTS.get(key, "") or (f"جستجو: {q}" if q else ""), "page": page, "total": len(rows), "q": q,
        "base_qs": f"q={q}" if q else ""})


@staff_required
def sms_preview(request):
    """پیش‌نمایش پیامک کمپین در فرم پنل: متن نهایی برای یک گیرندهٔ نمونه، تعداد حرف و تعداد پیامک."""
    from django.core.cache import cache
    from django.http import JsonResponse

    from shop.models import SpecialOffer

    from .campaigns import message, offer_vars
    from .models import CrmSettings
    from .notify import sample_context
    from .smart import sms_parts

    g = request.GET
    text = (g.get("text") or "")[:2000]
    s = CrmSettings.load()
    ctx = sample_context()
    offer = None
    try:
        oid = int(g.get("offer") or 0)
    except ValueError:
        oid = 0
    offer = SpecialOffer.objects.select_related("product", "size").filter(pk=oid).first() if oid else None
    if offer is None and g.get("kind") == "offer":
        from shop.offers import live_offers

        offer = next(iter(sorted(live_offers(), key=lambda o: -len(o.product.title))), None)
    extra = {"album": "فرش ۱۲۰۰ شانه نمونه", "date": "شنبه ۲۶ مهر"}
    if offer:
        extra.update(offer_vars(offer))
    extra["link"] = "https://crpt.ir/l/ab3k9xq"

    from types import SimpleNamespace

    from django.utils import timezone

    def num(k, default):
        try:
            return int("".join(ch for ch in (g.get(k) or "") if ch.isdigit()) or 0) or default
        except ValueError:
            return default

    coupon = SimpleNamespace(code="C12-AB2CD", value=num("discount", 2_000_000), min_order=num("min_order", 40_000_000),
                             ends_at=timezone.now() + timezone.timedelta(days=num("valid_days", 30)))
    if g.get("discount") in ("0", "۰"):
        coupon = None
    footer = s.marketing_footer if g.get("footer", "1") == "1" else ""
    body = message(text, {"name": ctx.get("name") or "محمدعلی"}, coupon, footer, **extra)
    out = {"text": body, "chars": len(body), "parts": sms_parts(body), "offer": offer.product.title if offer else ""}
    seg = g.get("segment")
    if seg:
        key = f"crm:prev:count:{seg}:{g.get('inactive_days')}:{g.get('album')}:{hash(g.get('custom') or '')}"
        n = cache.get(key)
        if n is None:
            from .segments import audience

            try:
                n = len(audience(seg, int(g.get("inactive_days") or 180), g.get("custom") or "", album=g.get("album") or None))
            except Exception:  # noqa: BLE001
                n = 0
            cache.set(key, n, 600)
        out["recipients"] = n
        out["total_sms"] = n * out["parts"]
        if offer and s.smart_offer and g.get("smart", "1") in ("1", "on", "true"):
            first = min(n, s.wave1_per_piece * max(offer.remaining, 1)) if s.wave1_per_piece else n
            out["wave1"] = first
            out["wave1_sms"] = first * out["parts"]
    return JsonResponse(out)


@staff_required
def campaign_plan(request, pk):
    """برنامهٔ ارسال هوشمند: گیرنده‌ها به ترتیب امتیاز، دلیل امتیاز و اندازهٔ مرحله‌ها."""
    from django.shortcuts import get_object_or_404

    from .models import Campaign
    from .smart import plan

    c = get_object_or_404(Campaign.objects.select_related("offer__product", "offer__size"), pk=pk)
    if not c.offer_id:
        raise Http404
    p = plan(c)
    scored = sum(1 for _, sc, _, _ in p["ranked"] if sc > 0)
    bounds, acc = [], 0
    for i, n in enumerate(p["waves"], 1):
        bounds.append((i, acc + 1, acc + n, n))
        acc += n
    rows = []
    for idx, (m, sc, why, is_set) in enumerate(p["ranked"][:200], 1):
        w = next((b[0] for b in bounds if b[1] <= idx <= b[2]), None)
        rows.append({"i": idx, "mobile": m, "score": sc, "why": "، ".join(why), "set": is_set, "wave": w})
    return render(request, "crm/plan.html", {"c": c, "p": p, "rows": rows, "bounds": bounds, "scored": scored,
                                             "sets": sum(1 for r in p["ranked"] if r[3])})
