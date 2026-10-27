from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import urlencode

from catalog.models import ProductTag
from catalog import tagclean

from ..auth import clear_site_cache, staff_required
from ..models import log


@staff_required
def tag_cleanup(request):
    """دقیق‌کردن فرش‌های یک برچسب: کدام نقشه‌ها بمانند، بقیه برداشته شوند."""
    src = request.POST if request.method == "POST" else request.GET
    pk = src.get("tag") or next((x for x in src.getlist("ids") if str(x).isdigit()), "")
    if not str(pk).isdigit():
        messages.warning(request, "یک برچسب را در فهرست برچسب‌ها تیک بزنید.")
        return redirect("/panel/tags/")
    tag = get_object_or_404(ProductTag, pk=int(pk))
    word = (src.get("word") or "").strip()[:80] or tagclean.default_word(tag.name)
    here = "/panel/tags/cleanup/?" + urlencode({"tag": tag.pk, "word": word})
    if request.method == "POST" and src.get("apply") == "1":
        res, edit = tagclean.apply(tag, word, request.POST.getlist("keep"), add_missing=src.get("add") == "1",
                                   drop_album_defaults=src.get("albums") == "1", user=request.user)
        log(request, "update", "برچسب‌های محصول", tag, res["summary"])
        clear_site_cache()
        msg = (f"{res['removed']} فرش از «{tag.name}» برداشته و {res['added']} فرش افزوده شد؛ "
               f"{len(res['rules'])} نقشه ماند و قانون خودکار گرفت.")
        if res["albums"]:
            msg += f" برچسب از پیش‌فرض {res['albums']} آلبوم برداشته شد."
        messages.success(request, msg + (" برای برگرداندن: ابزار محتوا ← سابقهٔ تغییرها." if edit else ""))
        return redirect(here)
    data = tagclean.analyze(tag, word)
    return render(request, "dashboard/tag_cleanup.html", {"tag": tag, "d": data, "word": word})
