"""فرشستان (و هر سایت دیگر روی همین کد): پاک کردن ردّ ایران کارپت از دیتابیس.

    python manage.py brand_clean            # فقط گزارش: private/brand-clean.csv
    python manage.py brand_clean --apply    # اعمال

چه می‌کند:
  ۱. بازنویسی مقاله‌ها: متن‌های ایران کارپت که روی مقاله‌های این سایت منتشر شده‌اند به نسخهٔ قبلی برمی‌گردند،
     ادغام‌ها (۳۰۱) برگردانده می‌شوند و صف خاموش می‌شود.
  ۲. هویت ایران کارپت در تنظیمات سایت (اینماد، مجوزها، اتحادیه، سال شروع، نام‌های دیگر، شبکه‌های اجتماعی) پاک می‌شود؛
     عوض نمی‌شود، چون مجوز و نماد هر فروشگاه مال خودش است. مال این سایت را در پنل وارد کنید.
  ۳. برگه‌ها و مقاله‌هایی که خودشان دربارهٔ ایران کارپت‌اند (تاریخچه، معرفی شرکت) پیش‌نویس می‌شوند و ۳۰۱ به صفحهٔ اول می‌روند؛
     عوض کردن نامشان ادعای نادرست دربارهٔ این فروشگاه می‌سازد.
  ۴. باقی متن‌ها (مقاله، برگه، دسته، صفحهٔ فرود، قالب متن، تنظیمات، پیامک‌ها…): «ایران کارپت» ← نام همین فروشگاه
     و irancarpet.net ← دامنهٔ همین سایت.
روی خود ایران کارپت اجرا نمی‌شود. اجرای دوباره بی‌خطر است.
"""
import csv
import json
import os
import re

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from core import brand

PATTERN = re.compile(r"ایران[ ‌]?کارپت|irancarpet|iran\.carpet|iran_carpet|Iran ?Carpet|137774", re.I)
# مدل‌هایی که متنشان به بازدیدکننده یا مشتری می‌رسد (سفارش‌ها، نظرها، گزارش‌ها و تاریخچه دست نمی‌خورند)
MODELS = [
    "blog.Post", "blog.Page", "blog.BlogCategory", "blog.BlogTag", "blog.Faq",
    "catalog.Category", "catalog.ProductTag", "catalog.Product",
    "content.ContentTemplate", "content.InfoBlock", "content.ContentSettings",
    "landing.LandingPage", "core.SiteSettings", "core.Media", "seo.SeoSettings",
    "crm.CrmSettings", "crm.AutoCampaign", "installments.InstallmentPlan", "installments.BetaSettings",
    "shop.ShopSettings", "shop.SpecialOffer", "api.AppSettings", "pricing.PricingSettings", "pricing.Album",
    "rajyar.RajyarSettings", "farshplus.FarshPlusSettings", "affiliate.AffiliateSettings", "finder.Need",
]
SKIP_FIELDS = {"rewrite_repo", "rewrite_branch", "rewrite_last_status", "source_url", "features_off", "brand_name"}
# هویت ایران کارپت در تنظیمات سایت: پاک می‌شود، عوض نمی‌شود
IDENTITY = {"enamad_url", "trust_html", "alt_names", "trust_since", "founding_date"}
IRANCARPET_IDS = ("137774", "1470154", "ecunion.ir/landing/8389", "@iran.carpet", "iran.carpet", "irancarpet")
SEEDED = {"trust_since": "فعال در فضای آنلاین از ۱۳۸۹ و فروش اینترنتی از ۱۳۹۱", "founding_date": "2010"}  # مهاجرت‌های core
# برگه‌ها و مقاله‌هایی که خودشان دربارهٔ ایران کارپت‌اند (معرفی شرکت، تاریخچه)
SELF_TITLE = re.compile(r"^\s*(درباره|تاریخچه)\S*\s+ایران[ \u200c]?کارپت")
SELF_SIGNS = ("پورتال فرش ماشینی ایران", "نخستین فروشگاه اینترنتی فرش ماشینی")
SELF_SLUG = re.compile(r"ایران-?کارپت|irancarpet", re.I)
NEEDLES = ("ایران کارپت", "ایران\u200cکارپت", "ایرانکارپت", "irancarpet", "iran.carpet", "iran_carpet", "iran carpet", "137774")


def _text_fields(model):
    for f in model._meta.get_fields():
        if not getattr(f, "concrete", False) or f.name in SKIP_FIELDS or getattr(f, "choices", None):
            continue
        if isinstance(f, (models.SlugField, models.EmailField)):
            continue
        if isinstance(f, (models.CharField, models.TextField, models.JSONField)):
            yield f


def _has(v):
    return bool(v) and bool(PATTERN.search(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))


def _fixed(f, v):
    """مقدار تازهٔ یک فیلد: پیوند شبکهٔ اجتماعی ایران کارپت پاک، باقی با نام و دامنهٔ همین سایت."""
    if isinstance(f, models.URLField) or (isinstance(v, str) and re.fullmatch(r"https?://\S+", v.strip())):
        if "irancarpet.net" in v and not re.search(r"iran\.carpet|@irancarpet|/irancarpet", v):
            return brand.fix(v)
        return ""
    if isinstance(f, models.JSONField):
        return json.loads(brand.fix(json.dumps(v, ensure_ascii=False)))
    return brand.fix(v)


class Command(BaseCommand):
    help = "پاک کردن ردّ ایران کارپت از دیتابیس سایت‌های دیگر روی همین کد (اول گزارش، بعد --apply)"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="اعمال (بدون این فقط گزارش)")

    def handle(self, *args, apply=False, **opts):
        if brand.is_main():
            raise CommandError("این‌جا خود ایران کارپت است؛ این دستور برای فرشستان و سایت‌های دیگر است.")
        if brand.name() == brand.DEFAULT_BRAND:
            raise CommandError("نام برند این سایت در پنل ← تنظیمات ← سایت ثبت نشده است.")
        rows = []
        with transaction.atomic():
            rows += self.rewrites(apply)
            rows += self.identity(apply)
            rows += self.self_pages(apply)
            rows += self.texts(apply)
            if not apply:
                transaction.set_rollback(True)
        if apply:
            from dashboard.auth import clear_site_cache

            brand.clear()
            clear_site_cache()
        path = os.path.join(str(getattr(settings, "PRIVATE_ROOT", settings.BASE_DIR)), "brand-clean.csv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["کار", "بخش", "شناسه", "نشانی", "فیلد", "پیش از", "پس از"])
            w.writerows(rows)
        by = {}
        for r in rows:
            by[r[0]] = by.get(r[0], 0) + 1
        self.stdout.write(" · ".join(f"{k}: {v}" for k, v in by.items()) or "هیچ ردّی از ایران کارپت پیدا نشد.")
        for r in [r for r in rows if r[0] in ("برگشت بازنویسی", "پیش‌نویس + ۳۰۱", "پاک (هویت)", "پاک (پیوند ایران کارپت)", "بررسی دستی")][:30]:
            self.stdout.write(f"  {r[0]}: {r[1]} {r[3] or r[2]} {r[4]}")
        self.stdout.write(f"فهرست کامل: {path}")
        self.stdout.write("اعمال شد." if apply else "هنوز چیزی تغییر نکرده است. برای اعمال: manage.py brand_clean --apply")

    # ------------------------------------------------------------ ۱. بازنویسی‌های ایران کارپت
    def rewrites(self, apply):
        from blog import rewrite
        from blog.models import PostRewrite
        from seo.models import SeoSettings

        out = []
        S = PostRewrite.Status
        # در گزارش: مقاله‌هایی که به متن قبلی برمی‌گردند جدا شمرده نمی‌شوند (در اعمال، بعد از برگشت بررسی می‌شوند)
        self.restored = {} if apply else {"Post": set(PostRewrite.objects.filter(status=S.PUBLISHED).values_list("post_id", flat=True))}
        for rw in PostRewrite.objects.filter(status__in=[S.PUBLISHED, S.MERGED]).select_related("post"):
            out.append(["برگشت بازنویسی", "مقاله", rw.post_id, rw.post.get_absolute_url(), "متن",
                        rw.title or rw.post.title, (rw.old or {}).get("title", "")])
            if apply:
                rewrite.rollback(rw)
        pending = PostRewrite.objects.exclude(status__in=[S.PUBLISHED, S.MERGED, S.REJECTED, S.SKIPPED])
        if pending.exists():
            out.append(["صف بازنویسی کنار رفت", "مقاله", pending.count(), "", "", "", ""])
            if apply:
                pending.update(status=S.SKIPPED)
        s = SeoSettings.load()
        if s.rewrite_enabled or s.rewrite_repo:
            out.append(["صف بازنویسی خاموش", "تنظیمات سئو", s.pk, "", "rewrite_enabled", "روشن", "خاموش"])
            if apply:
                SeoSettings.objects.filter(pk=s.pk).update(rewrite_enabled=False, rewrite_repo="")
        return out

    # ------------------------------------------------------------ ۲. هویت ایران کارپت در تنظیمات سایت
    def identity(self, apply):
        from core.models import SiteSettings

        s = SiteSettings.load()
        out, upd = [], {}
        for name in IDENTITY:
            v = getattr(s, name, "") or ""
            if v and (any(x in str(v) for x in IRANCARPET_IDS) or PATTERN.search(str(v)) or SEEDED.get(name) == str(v).strip()):
                out.append(["پاک (هویت)", "تنظیمات سایت", s.pk, "", name, str(v)[:200], ""])
                upd[name] = ""
        lic = getattr(s, "licenses", "") or ""
        keep = [ln for ln in lic.splitlines() if not any(x in ln for x in IRANCARPET_IDS) and not PATTERN.search(ln)]
        if "\n".join(keep).strip() != lic.strip():
            out.append(["پاک (هویت)", "تنظیمات سایت", s.pk, "", "licenses", lic[:200], "\n".join(keep)])
            upd["licenses"] = "\n".join(keep).strip()
        if apply and upd:
            SiteSettings.objects.filter(pk=s.pk).update(**upd)
        return out

    # ------------------------------------------------------------ ۳. برگه‌ها و مقاله‌های دربارهٔ خود ایران کارپت
    def self_pages(self, apply):
        from blog.models import Page, Post
        from seo.models import Redirect

        out = []
        for M in (Page, Post):
            for o in M.objects.filter(status="publish"):
                if o.pk in self.restored.get(M.__name__, ()):
                    continue   # بازنویسی ایران کارپت روی مقالهٔ خود این سایت؛ به متن قبلی برمی‌گردد
                if not (SELF_SLUG.search(o.slug or "") or SELF_TITLE.search(o.title or "")
                        or any(x in (o.content or "") for x in SELF_SIGNS)):
                    continue
                url = o.get_absolute_url()
                out.append(["پیش‌نویس + ۳۰۱", M._meta.verbose_name, o.pk, url, "", o.title, "/"])
                if apply:
                    M.objects.filter(pk=o.pk).update(status="draft")
                    Redirect.objects.update_or_create(source=Redirect.normalize(url), defaults={
                        "target": "/", "status_code": 301, "is_active": True})
        return out

    # ------------------------------------------------------------ ۴. باقی متن‌ها
    def texts(self, apply):
        out = []
        for label in MODELS:
            try:
                M = apps.get_model(label)
            except LookupError:
                continue
            fields = list(_text_fields(M))
            if not fields:
                continue
            q = models.Q()
            for f in fields:
                if not isinstance(f, models.JSONField):
                    for n in NEEDLES:
                        q |= models.Q(**{f"{f.name}__icontains": n})
            qs = M.objects.all() if any(isinstance(f, models.JSONField) for f in fields) else M.objects.filter(q)
            for o in qs.iterator():
                if o.pk in self.restored.get(M.__name__, ()):
                    continue
                changed = {}
                for f in fields:
                    if label == "core.SiteSettings" and f.name in IDENTITY | {"licenses"}:
                        continue
                    v = getattr(o, f.name)
                    if not _has(v):
                        continue
                    new = _fixed(f, v)
                    url = o.get_absolute_url() if hasattr(o, "get_absolute_url") else ""
                    if _has(new):   # نام کاربری شبکهٔ اجتماعی، نام انگلیسی و…: خودکار عوض نمی‌شود
                        out.append(["بررسی دستی", M._meta.verbose_name, o.pk, url, f.name, PATTERN.search(
                            new if isinstance(new, str) else json.dumps(new, ensure_ascii=False)).group(0), ""])
                    if new != v:
                        changed[f.name] = new
                        out.append(["نام و دامنهٔ این سایت" if new else "پاک (پیوند ایران کارپت)", M._meta.verbose_name, o.pk, url, f.name,
                                    (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))[:200],
                                    (new if isinstance(new, str) else json.dumps(new, ensure_ascii=False))[:200]])
                if apply and changed:
                    M.objects.filter(pk=o.pk).update(**changed)
        return out
