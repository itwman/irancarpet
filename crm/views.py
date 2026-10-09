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
    counts = segments.counts()
    rows, page = [], None
    if key:
        if key not in segments.SEGMENTS:
            raise Http404
        rows = segments.audience(key)
        page = Paginator(rows, 50).get_page(request.GET.get("page"))
    return render(request, "crm/segments.html", {
        "cards": [(k, v, counts.get(k, 0), segments.HINTS.get(k, "")) for k, v in segments.SEGMENTS.items()], "key": key,
        "title": segments.SEGMENTS.get(key, ""), "page": page, "total": len(rows)})
