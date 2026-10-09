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
