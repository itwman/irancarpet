from django.http import Http404, HttpResponse
from django.views.decorators.cache import cache_control

from . import llms
from .models import SeoSettings


@cache_control(public=True, max_age=600)
def llms_txt(request):
    return HttpResponse(llms.build(), content_type="text/markdown; charset=utf-8")


def indexnow_key(request, key):
    """فایل تأیید کلید IndexNow: /<key>.txt"""
    s = SeoSettings.load()
    if key != s.indexnow_key:
        raise Http404
    return HttpResponse(s.indexnow_key, content_type="text/plain; charset=utf-8")
