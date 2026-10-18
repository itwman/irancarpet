"""شمارش بازدید فرش و مقاله بدون نوشتن در دیتابیس به ازای هر بازدید.

قبلاً هر بازدید (حتی ربات) یک UPDATE روی جدول فرش می‌زد که در binlog مای‌اسکیوال هم ثبت می‌شد.
حالا بازدیدها در کش جمع می‌شوند و هر ۱۰ دقیقه (run_jobs) یک‌جا نوشته می‌شوند؛ ربات‌ها شمرده نمی‌شوند.
"""
from django.core.cache import cache
from django.db.models import F

KINDS = {"p": ("catalog", "Product"), "b": ("blog", "Post")}


def hit(kind, pk, request=None):
    if request is not None:
        try:
            from affiliate.track import is_bot

            if is_bot(request):
                return
        except Exception:  # noqa: BLE001
            pass
    key = f"vc:{kind}:{pk}"
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, None)
        ids = cache.get(f"vc:{kind}:ids") or set()
        if pk not in ids:
            ids.add(pk)
            cache.set(f"vc:{kind}:ids", ids, None)


def flush():
    """شمارش‌های جمع‌شده ← دیتابیس. خروجی: تعداد ردیف‌های به‌روزشده."""
    from django.apps import apps

    n = 0
    for kind, (app, model) in KINDS.items():
        ids = cache.get(f"vc:{kind}:ids") or set()
        if not ids:
            continue
        cache.delete(f"vc:{kind}:ids")
        Model = apps.get_model(app, model)
        for pk in ids:
            key = f"vc:{kind}:{pk}"
            c = cache.get(key) or 0
            cache.delete(key)
            if c:
                n += Model.objects.filter(pk=pk).update(views=F("views") + c)
    return n
