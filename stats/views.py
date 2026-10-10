"""صفحه‌های پنل: «گزارش بازدید و ورودی‌ها» و «گزارش کمپین پیامکی»."""
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.templatetags.fa import fa_num, jdate
from dashboard.auth import staff_required

from . import reports

PERIODS = [("today", "امروز"), ("yesterday", "دیروز"), ("7", "۷ روز"), ("30", "۳۰ روز"), ("90", "۳ ماه"), ("365", "یک سال")]


def _range(key):
    today = timezone.localdate()
    if key == "today":
        return today, today
    if key == "yesterday":
        d = today - timezone.timedelta(days=1)
        return d, d
    n = int(key) if key in ("7", "30", "90", "365") else 30
    return today - timezone.timedelta(days=n - 1), today


def _bucket(series):
    """بیش از ۶۲ روز: هفتگی، تا نمودار خوانا بماند."""
    if len(series) <= 62:
        for s in series:
            s["label"] = jdate(s["day"], "%m/%d")
            s["tip"] = f'{jdate(s["day"], "%A %d %B")}: {fa_num(s["visits"])} ورود، {fa_num(s["views"])} بازدید صفحه'
        return series, False
    out = []
    for i in range(0, len(series), 7):
        chunk = series[i:i + 7]
        v = sum(c["visits"] for c in chunk)
        out.append({"day": chunk[0]["day"], "visits": v, "views": sum(c["views"] for c in chunk),
                    "label": jdate(chunk[0]["day"], "%m/%d"),
                    "tip": f'هفتهٔ {jdate(chunk[0]["day"], "%d %B")}: {fa_num(v)} ورود'})
    peak = max([c["visits"] for c in out] or [0]) or 1
    for c in out:
        c["h"] = round(c["visits"] * 100 / peak)
    return out, True


@staff_required
def traffic_view(request):
    key = request.GET.get("p") or "30"
    if key not in dict(PERIODS):
        key = "30"
    start, end = _range(key)
    r = reports.traffic(start, end)
    series, weekly = _bucket([dict(s) for s in r["series"]])
    step = max(1, len(series) // 10)
    return render(request, "stats/traffic.html", {
        "r": r, "series": series, "weekly": weekly, "label_step": step, "periods": PERIODS, "p": key,
        "start": start, "end": end,
    })


@staff_required
def campaign_view(request, pk):
    from crm.models import Campaign

    c = get_object_or_404(Campaign, pk=pk)
    return render(request, "stats/campaign.html", {"c": c, "r": reports.campaign(c)})
