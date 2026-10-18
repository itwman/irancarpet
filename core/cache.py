"""کش فایلی مشترک بین پردازه‌ها (gunicorn، تایمرها و فرمان‌هایی که مدیر با root می‌زند).

چرا فایل و نه دیتابیس: کش دیتابیسی هر نوشتن را DELETE+INSERT و هر چند بار یک COUNT(*) می‌کرد و همه‌اش
در binlog مای‌اسکیوال هم ثبت می‌شد (بیشترین نوشتن سایت). کش فایلی هیچ کوئری‌ای نمی‌زند.

دو تفاوت با FileBasedCache خود جنگو:
  - فایل‌ها با دسترسی گروه (۰۶۶۰) نوشته می‌شوند؛ وگرنه فایلی که root بسازد (مثلاً هنگام migrate) برای
    www-data خواندنی نیست و صفحه خطا می‌دهد.
  - اگر باز هم فایلی خواندنی نبود، مثل «نبودن در کش» رفتار می‌شود، نه خطا.
"""
import os

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.filebased import FileBasedCache


class SharedFileCache(FileBasedCache):
    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        super().set(key, value, timeout, version)
        try:
            os.chmod(self._key_to_file(key, version), 0o660)
        except OSError:
            pass

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except (PermissionError, EOFError, ValueError):
            return default

    def touch(self, key, timeout=DEFAULT_TIMEOUT, version=None):
        try:
            return super().touch(key, timeout, version)
        except PermissionError:
            return False

    def _createdir(self):
        old = os.umask(0o007)
        try:
            super()._createdir()
        finally:
            os.umask(old)
