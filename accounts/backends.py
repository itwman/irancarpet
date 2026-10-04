from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .utils import normalize_mobile


class IdentifierBackend(ModelBackend):
    """ورود با نام کاربری، ایمیل یا موبایل + رمز (رمز وردپرسی قدیمی هم پذیرفته می‌شود)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        ident = username.strip()
        mobile = normalize_mobile(ident)
        q = Q(username__iexact=ident) | Q(email__iexact=ident)
        if mobile:
            q |= Q(profile__mobile=mobile) | Q(username=mobile)
        for user in User.objects.filter(q).distinct()[:5]:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
