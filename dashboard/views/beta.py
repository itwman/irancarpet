"""پنل ← اقساط بتا: خریدهای ثبت‌شده در سامانهٔ بتا بانک رفاه و وضعیت وصول اقساط."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from installments import beta, betaflow
from installments.beta import BetaError
from installments.models import BetaSale, BetaSettings
from shop.models import Order

from ..auth import staff_required
from ..models import log

TABS = [("open", "ثبت‌شده در بتا"), ("failed", "قسط وصول‌نشده"), ("waiting", "در انتظار تأیید مشتری"), ("all", "همه")]


@staff_required
def beta_list(request):
    s = BetaSettings.load()
    if request.method == "POST" and request.POST.get("do") == "sync":
        try:
            n = betaflow.sync_due(limit=300, force=True) if s.ready else 0
            messages.success(request, f"اقساط {n} خرید از بتا به‌روز شد.")
        except Exception as e:  # noqa: BLE001
            messages.error(request, f"به‌روزرسانی نشد: {e}")
        return redirect(request.get_full_path())
    tab = request.GET.get("t") if request.GET.get("t") in dict(TABS) else "open"
    qs = BetaSale.objects.select_related("order")
    counts = {
        "open": qs.filter(sale_id__isnull=False).count(),
        "failed": qs.filter(failed_count__gt=0).count(),
        "waiting": qs.filter(sale_id__isnull=True).exclude(order__status="cancelled").count(),
    }
    if tab == "open":
        qs = qs.filter(sale_id__isnull=False)
    elif tab == "failed":
        qs = qs.filter(failed_count__gt=0)
    elif tab == "waiting":
        qs = qs.filter(sale_id__isnull=True).exclude(order__status="cancelled")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(order__number__icontains=q) | Q(order__last_name__icontains=q) | Q(order__mobile__icontains=q)
                       | Q(sale_id__icontains=q))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    rows = []
    for sale in page.object_list:
        live = [r for r in sale.installments if not r.get("deleted")]
        nxt = next((r for r in live if not r.get("ok") and r.get("status") != 3), None)
        rows.append({"sale": sale, "order": sale.order, "count": len(live) or sale.order.installment.get("count"),
                     "next": nxt, "nc": beta.mask_nc(sale.national_code)})
    return render(request, "dashboard/beta_list.html", {
        "s": s, "tabs": [(k, label, counts.get(k)) for k, label in TABS], "tab": tab, "page": page, "rows": rows, "q": q,
    })


@staff_required
def order_beta(request, pk):
    """از صفحهٔ سفارش: به‌روزرسانی اقساط از بتا، یا ثبت دستی شمارهٔ فروش بتا (برای خریدهایی که در پنل بتا ثبت شده‌اند)."""
    order = get_object_or_404(Order, pk=pk, payment_mode="installment")
    if request.method != "POST":
        return redirect(f"/panel/orders/{pk}/view/")
    do = request.POST.get("do")
    sale = betaflow.sale_for(order)
    try:
        if do == "link":
            sid = "".join(ch for ch in request.POST.get("sale_id", "") if ch.isdigit())
            if not sid:
                messages.error(request, "شمارهٔ فروش بتا را وارد کنید.")
                return redirect(f"/panel/orders/{pk}/view/")
            sale.sale_id = int(sid)
            sale.save(update_fields=["sale_id"])
            betaflow.sync(sale)
            log(request, "action", "سفارش‌ها", order, f"اتصال به فروش بتا {sid}")
            messages.success(request, f"سفارش به فروش {sid} بتا وصل شد و اقساطش خوانده شد.")
        elif do == "sync" and sale.sale_id:
            betaflow.sync(sale)
            messages.success(request, "اقساط از بتا به‌روز شد.")
        elif do == "check" and sale.national_code:
            msg = betaflow.check(order)
            messages.info(request, msg)
    except betaflow.FlowError as e:
        messages.error(request, str(e))
    except BetaError as e:
        sale.last_error = e.admin_text[:300]
        sale.save(update_fields=["last_error"])
        messages.error(request, f"بتا: {e.admin_text}")
    return redirect(f"/panel/orders/{pk}/view/")


def order_context(order):
    """جعبهٔ بتا در صفحهٔ سفارش پنل."""
    plan = order.installment_plan
    if not (order.is_installment and plan and plan.kind == "beta"):
        return None
    sale = betaflow.sale_for(order, create=False)
    return {"sale": sale, "ready": BetaSettings.load().ready, "site": settings.SITE_URL,
            "rows": [r for r in (sale.installments if sale else []) if not r.get("deleted")],
            "start_label": betaflow.month_label(sale.start_ym) if sale and sale.start_ym else ""}
