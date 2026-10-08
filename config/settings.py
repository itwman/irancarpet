"""
تنظیمات پروژهٔ ایران کارپت (جنگو).

همهٔ مقادیر حساس و وابسته به سرور از متغیرهای محیطی (فایل .env) خوانده می‌شوند.
نمونه در .env.example
"""
from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,irancarpet.net,www.irancarpet.net")
# دامنهٔ پیوند کوتاه همکاران فروش (فقط ریدایرکت به سایت اصلی)
SHORT_HOSTS = env_list("SHORT_HOSTS", "crpt.it,www.crpt.it")
ALLOWED_HOSTS += [h for h in SHORT_HOSTS if h not in ALLOWED_HOSTS]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "https://irancarpet.net,https://www.irancarpet.net")

SITE_URL = os.environ.get("SITE_URL", "https://irancarpet.net").rstrip("/")
SITE_NAME = os.environ.get("SITE_NAME", "ایران کارپت")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
    "pricing",
    "catalog",
    "blog",
    "seo",
    "accounts",
    "shop",
    "dashboard",
    "farshplus",
    "torob",
    "api",
    "installments",
    "finder",
    "rajyar",
    "landing",
    "growth",
    "content",
    "affiliate",
]

MIDDLEWARE = [
    "affiliate.track.ShortHostMiddleware",  # دامنهٔ پیوند کوتاه همکاران (crpt.it)
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "seo.middleware.LegacyQueryMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "affiliate.track.RefMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "seo.middleware.RedirectFallbackMiddleware",
    "seo.middleware.StagingNoIndexMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
                "shop.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- دیتابیس -------------------------------------------------------------
# DATABASE_URL: دیتابیس اصلی سایت جنگو
# WP_DATABASE_URL: دیتابیس وردپرس (فقط برای ایمپورت؛ فقط خواندنی)
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=60,
    ),
}
if os.environ.get("WP_DATABASE_URL"):
    DATABASES["wp"] = dj_database_url.parse(os.environ["WP_DATABASE_URL"])

for _alias, _db in DATABASES.items():
    if _db["ENGINE"] == "django.db.backends.mysql":
        # دیتابیس وردپرس تاریخ‌های 0000-00-00 دارد، پس برای آن حالت سخت‌گیر خاموش است
        mode = "''" if _alias == "wp" else "'STRICT_TRANS_TABLES'"
        _db.setdefault("OPTIONS", {}).update({"charset": "utf8mb4", "init_command": f"SET sql_mode={mode}"})

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- رمز عبور ------------------------------------------------------------
# PhpassHasher اجازه می‌دهد مشتریان قدیمی با همان رمز وردپرس وارد شوند؛
# بعد از اولین ورود، رمز با الگوریتم پیش‌فرض جنگو دوباره هش می‌شود.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "core.hashers.PhpassHasher",
]

# کش مشترک بین همهٔ پردازه‌های gunicorn (تا تغییرات پنل فوراً همه‌جا دیده شود)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000
FILE_UPLOAD_PERMISSIONS = 0o664
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o2775

AUTHENTICATION_BACKENDS = ["accounts.backends.IdentifierBackend"]
LOGIN_URL = "/my-account/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

# --- زبان و زمان ---------------------------------------------------------
LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

# --- فایل‌ها ---------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = [BASE_DIR / "static"]

# تصاویر دقیقاً در همان مسیر وردپرس سرو می‌شوند تا آدرس تصاویر (و ایندکس Google Images) حفظ شود.
MEDIA_URL = "/wp-content/uploads/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
# فایل‌های خصوصی (تصویر چک و مدارک مشتری): خارج از media، فقط از راه پنل مدیریت قابل دیدن
PRIVATE_ROOT = Path(os.environ.get("PRIVATE_ROOT", BASE_DIR / "private"))

# --- امنیت در حالت production --------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

APPEND_SLASH = True

# در حالت استیجینگ، هدر X-Robots-Tag: noindex اضافه می‌شود تا گوگل نسخهٔ آزمایشی را ایندکس نکند
STAGING = env_bool("STAGING", False)
TESTING = len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "test"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}

UNFOLD = {
    "SITE_TITLE": "پنل ایران کارپت",
    "SITE_HEADER": "ایران کارپت",
    "SITE_URL": "/",
}

PRODUCTS_PER_PAGE = 24
POSTS_PER_PAGE = 12

# --- پرداخت و پیامک (مقادیر واقعی فقط در .env سرور) -----------------------
SEP_TERMINAL_ID = os.environ.get("SEP_TERMINAL_ID", "")
ZARINPAL_MERCHANT_ID = os.environ.get("ZARINPAL_MERCHANT_ID", "")
ZARINPAL_SANDBOX = env_bool("ZARINPAL_SANDBOX", False)
# درگاه آزمایشی: فقط در نسخهٔ آزمایشی؛ روی سایت اصلی خاموش
PAYMENT_FAKE = env_bool("PAYMENT_FAKE", DEBUG or STAGING)
SMSIR_API_KEY = os.environ.get("SMSIR_API_KEY", "")
SMSIR_OTP_TEMPLATE_ID = os.environ.get("SMSIR_OTP_TEMPLATE_ID", "")
SMSIR_ORDER_TEMPLATE_ID = os.environ.get("SMSIR_ORDER_TEMPLATE_ID", "")
SMSIR_ADMIN_TEMPLATE_ID = os.environ.get("SMSIR_ADMIN_TEMPLATE_ID", "")
