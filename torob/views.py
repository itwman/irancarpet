from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import feed
from .models import TorobSettings


@csrf_exempt
def products(request):
    s = TorobSettings.load()
    if not s.enabled:
        return JsonResponse({"count": 0, "max_pages": 0, "products": []})
    params = request.POST if request.method == "POST" else request.GET
    pu, url, pg = params.get("page_unique", ""), params.get("page_url", ""), params.get("page", "1")
    if str(pu).strip().isdigit():
        data = feed.single(feed.product_by_unique(int(pu)), s)
    elif url:
        data = feed.single(feed.product_by_url(url), s)
    else:
        data = feed.page(max(1, int(pg) if str(pg).isdigit() else 1), s)
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
