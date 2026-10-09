"""پنل «برنامهٔ بازنویسی مقاله‌ها»."""
import copy

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import format_html, linebreaks

from core.templatetags.fa import fa_num, jdate
from dashboard.auth import staff_required
from dashboard.registry import Col, Resource, register

from . import rewrite
from .models import PostRewrite
from .rewrite_rules import words

S = PostRewrite.Status
BADGE = {"merged": "completed", "queued": "draft", "ready": "pending", "approved": "processing", "published": "completed", "rejected": "cancelled",
         "skipped": "draft"}
KINDS = {"merge": "ادغام", "city": "شهر", "price": "قیمت", "installment": "اقساط", "guide": "آموزشی"}


def _status(o):
    return format_html('<span class="badge-ic b-{}">{}</span>{}', BADGE.get(o.status, "draft"), o.get_status_display(),
                       format_html(' <span title="{}">⚠️</span>', o.warnings[:300]) if o.warnings else "")


_SCHED = {"at": None, "data": {}}


def _schedule():
    now = timezone.now()
    if _SCHED["at"] is None or (now - _SCHED["at"]).total_seconds() > 30:
        _SCHED["data"], _SCHED["at"] = rewrite.schedule(now), now
    return _SCHED["data"]


def _when(o):
    if o.status == S.PUBLISHED and o.published_at:
        return "منتشر شد " + jdate(o.published_at, "%Y/%m/%d")
    if o.status == S.MERGED and o.published_at:
        return "ریدایرکت شد " + jdate(o.published_at, "%Y/%m/%d")
    if o.merge_into and o.status in (S.READY, S.APPROVED):
        return "همراه مقالهٔ مقصد"
    if o.status in (S.READY, S.APPROVED):
        at = _schedule().get(o.pk)
        if at is None:
            return "انتشار خودکار خاموش است" if not rewrite._settings().rewrite_enabled else "—"
        return format_html('<span title="{}">حدود {}</span>', "زمان تقریبی؛ کار زمان‌بندی هر ۱۰ دقیقه اجرا می‌شود",
                           jdate(at, "%m/%d ساعت %H:%M"))
    if o.status == S.QUEUED:
        return "منتظر متن تازه"
    return "—"


def _gsc(o):
    if not o.gsc_impressions:
        return "—"
    s = f"{fa_num(o.gsc_impressions)} نمایش · رتبهٔ {fa_num(round(o.gsc_position, 1))}"
    if o.gsc_after:
        a = o.gsc_after
        s += f" ← {fa_num(a.get('impressions', 0))} · {fa_num(a.get('position', 0))}"
    return s


def _set(qs, status, **kw):
    return qs.update(status=status, **kw)


def _publish_now(request, qs):
    n = sum(rewrite.merge(r) if r.merge_into else rewrite.publish(r) for r in qs.filter(status__in=[S.READY, S.APPROVED]))
    return f"{fa_num(n)} مقاله منتشر شد."


def _approve(request, qs):
    n = qs.filter(status=S.READY).update(status=S.APPROVED)
    return f"{fa_num(n)} مقاله تأیید شد و در نوبت‌های بعدی (به ترتیب اولویت) منتشر می‌شود."


def _reject(request, qs):
    n = qs.filter(status__in=[S.READY, S.APPROVED, S.QUEUED]).update(status=S.REJECTED)
    return f"{fa_num(n)} متن رد شد و منتشر نمی‌شود."


def _hold(request, qs):
    n = 0
    for r in qs.filter(status__in=[S.READY, S.APPROVED]):
        r.status = S.READY
        r.publish_after = max(r.publish_after or timezone.now(), timezone.now()) + timezone.timedelta(days=3)
        r.save(update_fields=["status", "publish_after"])
        n += 1
    return f"انتشار {fa_num(n)} مقاله سه روز عقب افتاد."


def _rollback(request, qs):
    n = sum(rewrite.rollback(r) for r in qs.filter(status=S.PUBLISHED))
    return f"نسخهٔ قبلی {fa_num(n)} مقاله برگشت."


def _preview_links(o):
    if not o.pk:
        return "—"
    parts = []
    if o.content:
        parts.append(format_html('<a href="/panel/rewrites/{}/preview/" target="_blank" rel="noopener">پیش‌نمایش متن تازه</a>', o.pk))
    parts.append(format_html('<a href="{}" target="_blank" rel="noopener">صفحهٔ فعلی در سایت</a>', o.post.get_absolute_url()))
    if o.old:
        parts.append(format_html('<a href="/panel/rewrites/{}/preview/?old=1" target="_blank" rel="noopener">نسخهٔ قبل از بازنویسی</a>', o.pk))
    return format_html(" · ".join(["{}"] * len(parts)), *parts)


def _words(o):
    before = words((o.old or {}).get("content") if o.status == S.PUBLISHED else o.post.content)
    return f"{fa_num(before)} ← {fa_num(words(o.content))} کلمه" if o.content else f"{fa_num(before)} کلمه"


register(Resource(
    key="rewrites", model=PostRewrite, title="برنامهٔ بازنویسی مقاله‌ها", single="بازنویسی", group="مجله و برگه‌ها", icon="calendar",
    columns=[Col("rank", "اولویت", lambda o: fa_num(o.rank), "rank"),
             Col("post", "مقاله", lambda o: format_html('{}<br><small class="muted">{}</small>', fa_num(o.post.title)[:70], o.reason)),
             Col("kind", "نوع", lambda o: KINDS.get(o.kind, o.kind or "—")),
             Col("gsc", "گوگل (پیش ← بعد)", _gsc, "gsc_impressions"),
             Col("status", "وضعیت", _status, "status"),
             Col("when", "انتشار", _when, "publish_after")],
    search=["post__title", "keyword"], filters=["status", "kind"], ordering=("rank",), can_add=False, per_page=50,
    queryset=lambda qs: qs.select_related("post"),
    fieldsets=[("متن تازه", ["title", "seo_title", "seo_description", "focus_keyword", "excerpt", "content"], "main"),
               ("انتشار", ["status", "rank", "publish_after"], "side"), ("یادداشت نویسنده", ["notes"], "side")],
    readonly=[("پیش‌نمایش", _preview_links), ("کلمهٔ هدف", lambda o: o.keyword or "—"), ("ادغام در", lambda o: o.merge_into or "—"), ("چرا این مقاله", lambda o: o.reason or "—"),
              ("حجم متن", _words), ("گوگل", _gsc),
              ("هشدارها", lambda o: format_html("{}", linebreaks(o.warnings)) if o.warnings else "ندارد")],
    actions={"publish_now": ("انتشار همین حالا", _publish_now), "approve": ("تأیید (انتشار در نوبت بعدی)", _approve),
             "hold": ("سه روز عقب بینداز", _hold), "reject": ("رد کن (منتشر نشود)", _reject),
             "rollback": ("برگرداندن نسخهٔ قبلی", _rollback)},
    help="تا وقتی وضعیت «آماده» است، سایت هنوز متن قبلی را نشان می‌دهد. متن تازه پس از «مهلت بررسی» خودکار منتشر می‌شود؛ "
         "روزانه به «تعداد انتشار در روز» و از «ساعت انتشار روزانه» (هر دو در تنظیمات ← سئو)، به ترتیب اولویت و روی همان نشانی قبلی. "
         "ستون انتشار زمان تقریبی را نشان می‌دهد. لازم نیست کاری بکنید؛ اگر خواستید متن تازه را ببینید، «ویرایش» ← «پیش‌نمایش متن تازه». "
         "نسخهٔ قبلی نگه داشته می‌شود و با «برگرداندن نسخهٔ قبلی» برمی‌گردد. ستون گوگل: آمار سرچ کنسول پیش و بعد از بازنویسی.",
))


@staff_required
def preview(request, pk):
    from .views import post_detail

    rw = get_object_or_404(PostRewrite.objects.select_related("post"), pk=pk)
    src = rw.old if request.GET.get("old") else {f: getattr(rw, f) for f in rewrite.FIELDS}
    if not src.get("content"):
        raise Http404
    p = copy.copy(rw.post)
    for f in rewrite.FIELDS:
        if src.get(f):
            setattr(p, f, src[f])
    p.modified_at = timezone.now()
    return post_detail(request, p, preview=True)
