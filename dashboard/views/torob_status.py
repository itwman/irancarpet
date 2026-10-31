"""پنل ← وضعیت در ترب: فروشگاه و محصولات همان‌طور که ترب می‌بیند (Shop API) و ناهمسانی با سایت."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_datetime

from torob import shopapi
from torob.models import TorobProduct, TorobSettings

from ..auth import staff_required
from ..models import log

TABS = [("price", "قیمت ناهمسان"), ("stock", "موجودی ناهمسان"), ("404", "صفحه در دسترس نیست"), ("missing", "در سایت پیدا نشد"),
        ("all", "همهٔ محصولات")]


def _aware(v):
    from datetime import timezone as dtz

    from django.utils import timezone

    d = parse_datetime(v or "") if v else None
    return timezone.make_aware(d, dtz.utc) if d and timezone.is_naive(d) else d


@staff_required
def torob_status(request):
    s = TorobSettings.load()
    if request.method == "POST":
        do = request.POST.get("do")
        try:
            if do in ("sync", "full"):
                st = shopapi.sync(full=do == "full")
                c = st.get("counts") or {}
                messages.success(request, f"از ترب خوانده شد: {st.get('synced_rows', 0)} محصول تغییرکرده. "
                                          f"قیمت ناهمسان {c.get('price', 0)}، موجودی ناهمسان {c.get('stock', 0)}، "
                                          f"خارج از دسترس {c.get('404', 0)}.")
                log(request, "update", "ترب", None, "همگام‌سازی وضعیت ترب")
            elif do in ("activate", "deactivate"):
                ids = request.POST.getlist("ids")
                n = shopapi.set_active(ids, do == "activate")
                messages.success(request, f"{n} محصول در ترب {'فعال' if do == 'activate' else 'غیرفعال'} شد.")
                log(request, "update", "ترب", None, f"{do} {n} محصول در ترب")
        except shopapi.TorobError as e:
            messages.error(request, str(e))
        return redirect(request.get_full_path())
    tab = request.GET.get("t") or "price"
    if tab not in dict(TABS):
        tab = "price"
    qs = TorobProduct.objects.select_related("product").order_by("-torob_updated_at", "pk")
    if tab != "all":
        qs = qs.filter(problem=tab)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(page_url__icontains=q) | qs.filter(product__title__icontains=q)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    for r in page.object_list:
        r.status_labels = [shopapi.STATUS_LABELS.get(x, x) for x in r.statuses]
    st = s.shop_state or {}
    summary = st.get("summary") or {}
    counts = st.get("counts") or {}
    return render(request, "dashboard/torob_status.html", {
        "s": s, "has_token": bool((s.shop_api_token or "").strip()), "st": st, "summary": summary,
        "shop_status": shopapi.SHOP_STATUS.get(st.get("status", ""), st.get("status", "")),
        "errors": summary.get("not_accessible_errors") or [], "counts": counts,
        "calc_at": _aware(summary.get("calculated_at")),
        "tabs": [(k, v, counts.get(k) if k != "all" else counts.get("total")) for k, v in TABS], "tab": tab, "q": q,
        "page": page, "base_qs": f"t={tab}" + (f"&q={q}" if q else ""), "labels": shopapi.STATUS_LABELS,
    })
