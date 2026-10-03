"""بررسی رمز عبور کاربران وردپرس (phpass قدیمی و bcrypt وردپرس ۶.۸+)."""
import base64
import hashlib
import hmac

from django.contrib.auth.hashers import BasePasswordHasher
from django.utils.crypto import constant_time_compare

ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _encode64(data, count):
    out, i = [], 0
    while i < count:
        value = data[i]
        i += 1
        out.append(ITOA64[value & 0x3F])
        if i < count:
            value |= data[i] << 8
        out.append(ITOA64[(value >> 6) & 0x3F])
        if i >= count:
            break
        i += 1
        if i < count:
            value |= data[i] << 16
        out.append(ITOA64[(value >> 12) & 0x3F])
        if i >= count:
            break
        i += 1
        out.append(ITOA64[(value >> 18) & 0x3F])
    return "".join(out)


def phpass_check(password, stored):
    if stored[:3] not in ("$P$", "$H$"):
        return False
    count = 1 << ITOA64.index(stored[3])
    salt = stored[4:12]
    pw = password.encode("utf-8")
    h = hashlib.md5(salt.encode() + pw).digest()
    for _ in range(count):
        h = hashlib.md5(h + pw).digest()
    return constant_time_compare(stored[:12] + _encode64(h, 16), stored)


def bcrypt_check(password_bytes, stored):
    try:
        import bcrypt
    except ImportError:  # pragma: no cover
        return False
    stored = stored.replace("$2y$", "$2b$", 1)
    try:
        return bcrypt.checkpw(password_bytes, stored.encode())
    except ValueError:
        return False


class PhpassHasher(BasePasswordHasher):
    """رمزهای منتقل‌شده از وردپرس با پیشوند `phpass$` ذخیره می‌شوند."""

    algorithm = "phpass"

    def verify(self, password, encoded):
        _, stored = encoded.split("$", 1)
        if stored.startswith(("$P$", "$H$")):
            return phpass_check(password, stored)
        if stored.startswith("$wp$"):  # وردپرس ۶.۸+
            pre = base64.b64encode(
                hmac.new(b"wp-sha384", password.strip().encode(), hashlib.sha384).digest()
            )
            return bcrypt_check(pre, stored[3:])
        if stored.startswith(("$2y$", "$2b$", "$2a$")):
            return bcrypt_check(password.encode(), stored)
        return False

    def encode(self, password, salt):  # pragma: no cover - فقط برای خواندن
        raise NotImplementedError("رمز جدید با هشر پیش‌فرض جنگو ذخیره می‌شود.")

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm}

    def must_update(self, encoded):
        return True
