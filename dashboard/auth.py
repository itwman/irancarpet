from functools import wraps

from django.core.cache import cache
from django.shortcuts import redirect, render


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/my-account/login/?tab=password&next={request.get_full_path()}")
        if not (request.user.is_active and request.user.is_staff):
            return render(request, "dashboard/forbidden.html", status=403)
        return view(request, *args, **kwargs)
    return wrapper


def superuser_required(view):
    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            return render(request, "dashboard/forbidden.html", {"superuser": True}, status=403)
        return view(request, *args, **kwargs)
    return wrapper


def clear_site_cache():
    """بعد از هر ذخیره در پنل، کش منو، تنظیمات و صفحهٔ اصلی پاک شود تا تغییر بلافاصله دیده شود."""
    cache.delete_many(["menu_categories", "site_settings", "home_data", "bing_verification"])
