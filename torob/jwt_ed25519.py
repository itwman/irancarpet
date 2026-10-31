"""بررسی توکن JWT ترب (EdDSA / ed25519) بدون کتابخانهٔ بیرونی.

پیاده‌سازی مرجع RFC 8032 (بخش ۵.۱)؛ فقط «بررسی امضا» لازم است، نه امضا کردن. کندتر از کتابخانه‌های C است
(چند ده میلی‌ثانیه) ولی ترب در هر دور فقط چند ده درخواست می‌دهد و توکن تأییدشده تا انقضا در کش می‌ماند.
"""
import base64
import hashlib
import json
import time

P = 2 ** 255 - 19
Q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x):
    return pow(x, P - 2, P)


D = -121665 * _inv(121666) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)


def _add(a, b):
    A = (a[1] - a[0]) * (b[1] - b[0]) % P
    B = (a[1] + a[0]) * (b[1] + b[0]) % P
    C = 2 * a[3] * b[3] * D % P
    Dd = 2 * a[2] * b[2] % P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F % P, G * H % P, F * G % P, E * H % P)


def _mul(s, pt):
    q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            q = _add(q, pt)
        pt = _add(pt, pt)
        s >>= 1
    return q


def _equal(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % P == 0 and (a[1] * b[2] - b[1] * a[2]) % P == 0


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * _inv(D * y * y + 1) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P:
        x = x * SQRT_M1 % P
    if (x * x - x2) % P:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_GY = 4 * _inv(5) % P
_GX = _recover_x(_GY, 0)
G = (_GX, _GY, 1, _GX * _GY % P)


def _decompress(b):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % P)


def verify(public, message, signature):
    """امضای ed25519؛ public: ۳۲ بایت، signature: ۶۴ بایت."""
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _decompress(public)
    R = _decompress(signature[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= Q:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public + message).digest(), "little") % Q
    return _equal(_mul(s, G), _add(R, _mul(h, A)))


def public_from_pem(pem):
    """کلید عمومی ed25519 از PEM (SubjectPublicKeyInfo): ۳۲ بایت آخر."""
    body = "".join(line for line in pem.strip().splitlines() if "-----" not in line)
    return base64.b64decode(body)[-32:]


def _b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class InvalidToken(Exception):
    pass


def decode(token, public, audience, leeway=60, now=None):
    """توکن را بررسی می‌کند و payload را برمی‌گرداند؛ خطا ← InvalidToken."""
    try:
        h64, p64, s64 = token.strip().split(".")
        header, payload = json.loads(_b64(h64)), json.loads(_b64(p64))
        sig = _b64(s64)
    except Exception as e:  # noqa: BLE001
        raise InvalidToken("bad token format") from e
    if header.get("alg") != "EdDSA":
        raise InvalidToken("bad alg")
    if not verify(public, f"{h64}.{p64}".encode(), sig):
        raise InvalidToken("bad signature")
    now = time.time() if now is None else now
    if "exp" not in payload or now > float(payload["exp"]) + leeway:
        raise InvalidToken("expired")
    if "nbf" in payload and now < float(payload["nbf"]) - leeway:
        raise InvalidToken("not yet valid")
    aud = payload.get("aud")
    auds = aud if isinstance(aud, list) else [aud]
    if audience not in auds:
        raise InvalidToken("bad audience")
    return payload
