"""جستجوی آژاکسی موجودیت‌ها برای فیلدهای انتخابی پنل (Tom Select)، با ایجاد خودکار برای موارد سبک."""
import json
from dataclasses import dataclass, field
from typing import Callable

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from blog.models import BlogCategory, BlogTag, Page, Post
from catalog.models import AttributeTerm, Brand, Category, Product, ProductTag
from core.models import Media
from pricing.models import Album, Size

from .auth import staff_required


def unique_slug(model, text, field_name="slug"):
    base = slugify(text, allow_unicode=True)[:200] or "item"
    slug, i = base, 2
    while model.objects.filter(**{field_name: slug}).exists():
        slug, i = f"{base}-{i}", i + 1
    return slug


def _create_named(model, name_field="name"):
    def create(text):
        obj = model.objects.filter(**{f"{name_field}__iexact": text}).first()
        if obj:
            return obj
        return model.objects.create(**{name_field: text, "slug": unique_slug(model, text)})
    return create


@dataclass
class Spec:
    model: object
    search: list
    label: Callable = None
    create: Callable = None
    order: str = None
    extra: Callable = None  # فیلتر اضافه روی queryset
    thumb: bool = False


def _term_label(t):
    return f"{t.attribute.label}: {t.name}"


def _user_label(u):
    name = u.get_full_name()
    mobile = getattr(getattr(u, "profile", None), "mobile", "") or ""
    return " · ".join(x for x in (name, mobile or u.username) if x)


class Registry:
    def __init__(self):
        self.specs = {}

    def register(self, key, spec):
        self.specs[key] = spec

    def get(self, key):
        return self.specs.get(key)

    def key_for(self, model):
        for k, s in self.specs.items():
            if s.model is model:
                return k
        return None


AC = Registry()
AC.register("category", Spec(Category, ["name", "slug"], create=_create_named(Category), order="name"))
AC.register("product_tag", Spec(ProductTag, ["name"], create=_create_named(ProductTag), order="name"))
AC.register("brand", Spec(Brand, ["name"], create=_create_named(Brand), order="name"))
AC.register("term", Spec(AttributeTerm, ["name", "attribute__label"], label=_term_label, order="attribute__order",
                         extra=lambda qs: qs.select_related("attribute")))
AC.register("album", Spec(Album, ["name", "code", "company"], order="name"))
AC.register("size", Spec(Size, ["label", "slug"], order="sort_order"))
AC.register("product", Spec(Product, ["title", "sku", "slug"], order="-published_at"))
AC.register("media", Spec(Media, ["title", "file", "alt"], order="-created_at", thumb=True))
AC.register("blog_category", Spec(BlogCategory, ["name"], create=_create_named(BlogCategory), order="name"))
AC.register("blog_tag", Spec(BlogTag, ["name"], create=_create_named(BlogTag), order="name"))
AC.register("post", Spec(Post, ["title", "slug"], order="-published_at"))
AC.register("page", Spec(Page, ["title", "slug"], order="title"))
AC.register("user", Spec(get_user_model(), ["username", "first_name", "last_name", "email", "profile__mobile"], label=_user_label,
                         order="-date_joined", extra=lambda qs: qs.select_related("profile")))


@staff_required
@require_http_methods(["GET", "POST"])
def autocomplete(request, key):
    spec = AC.get(key)
    if not spec:
        return JsonResponse({"results": []}, status=404)
    label = spec.label or str
    if request.method == "POST":
        if not spec.create:
            return HttpResponseForbidden()
        try:
            text = (json.loads(request.body or "{}").get("text") or "").strip()
        except ValueError:
            return HttpResponseBadRequest()
        if not text:
            return HttpResponseBadRequest()
        obj = spec.create(text[:200])
        return JsonResponse({"value": str(obj.pk), "text": label(obj)})
    q = (request.GET.get("q") or "").strip()
    qs = spec.model.objects.all()
    if spec.extra:
        qs = spec.extra(qs)
    if q:
        en = q.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
        fa = en.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        cond = Q()
        for f in spec.search:
            for v in {q, en, fa}:
                cond |= Q(**{f"{f}__icontains": v})
        if en.isdigit():
            cond |= Q(pk=int(en))
        qs = qs.filter(cond)
    if spec.order:
        qs = qs.order_by(spec.order)
    out = []
    for o in qs.distinct()[:20]:
        row = {"value": str(o.pk), "text": label(o)}
        if spec.thumb:
            row["thumb"] = o.url
        out.append(row)
    return JsonResponse({"results": out})
