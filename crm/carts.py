"""سبد خرید مشتری واردشده: ذخیره در پایگاه داده، بازگرداندن پس از ورود یا از پیوند پیامک، و یادآوری سبد رهاشده."""
import logging

from django.core import signing
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone

log = logging.getLogger(__name__)
SALT = "cart-restore"


def track(request, data):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_staff:
        return
    from .models import CartSnapshot

    if not data:
        CartSnapshot.objects.filter(user=user).delete()
        return
    CartSnapshot.objects.update_or_create(user=user, defaults={"data": dict(data), "updated_at": timezone.now(), "reminded_at": None})


def merge_into_session(session, data):
    from shop.cart import KEY

    cur = {str(k): int(v) for k, v in (session.get(KEY) or {}).items()}
    for k, v in (data or {}).items():
        cur.setdefault(str(k), int(v))
    session[KEY] = cur
    session.modified = True


def on_login(sender, request, user, **kwargs):
    """ورود در دستگاه دیگر: اگر سبد این دستگاه خالی است، سبد ذخیره‌شده برمی‌گردد؛ وگرنه سبد این دستگاه ذخیره می‌شود."""
    from shop.cart import KEY

    from .models import CartSnapshot

    try:
        snap = CartSnapshot.objects.filter(user=user).first()
        if request.session.get(KEY):
            track(request, request.session[KEY])
        elif snap and snap.data:
            merge_into_session(request.session, snap.data)
    except Exception:  # noqa: BLE001
        log.exception("cart restore on login")


def restore_url(user):
    from .links import shorten

    return shorten(f"/cart/restore/{signing.dumps(user.pk, salt=SALT, compress=True)}/", "c", days=14)


def restore_view(request, token):
    from .models import CartSnapshot

    try:
        pk = signing.loads(token, salt=SALT, max_age=14 * 86400)
    except signing.BadSignature:
        raise Http404
    snap = CartSnapshot.objects.filter(user_id=pk).first()
    if snap:
        merge_into_session(request.session, snap.data)
    return redirect("/cart/")
