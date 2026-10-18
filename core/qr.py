"""QR کد SVG برای پیوندها (یک بار ساخته و برای همیشه کش می‌شود)."""
import hashlib

from django.core.cache import cache


def svg(url, color="#22265A"):
    if not url:
        return ""
    key = "qr:" + hashlib.sha1(f"{url}|{color}".encode()).hexdigest()
    v = cache.get(key)
    if v is None:
        try:
            import segno

            v = segno.make(url, error="m").svg_data_uri(scale=4, border=1, dark=color)
        except Exception:  # noqa: BLE001  — نبودِ کتابخانه نباید صفحه را از کار بیندازد
            v = ""
        cache.set(key, v, None)
    return v
