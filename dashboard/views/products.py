from functools import partial

from django import forms
from django.contrib import messages
from django.db import transaction
from django.forms import inlineformset_factory, modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from blog.models import Faq
from catalog.models import Product, ProductImage, Variation
from core.models import Media

from ..ac import unique_slug
from ..auth import clear_site_cache, staff_required
from ..forms import formfield_for, style_form
from ..models import log

MAIN = ["title", "slug", "english_name", "short_description", "content"]
SIDE_PUBLISH = ["status", "published_at", "menu_order"]
SIDE_PRICE = ["album", "custom_base_price", "sale_status"]
SIDE_TAX = ["primary_category", "categories", "brand", "tags", "specs"]
SIDE_IMAGE = ["image", "video_url"]
SEO = ["seo_title", "seo_description", "focus_keyword", "robots", "canonical_url"]
VAR_FIELDS = ["size", "attributes", "sku", "is_available", "override_price", "manual_price", "sale_price", "pair_only", "menu_order"]

ProductForm = modelform_factory(Product, fields=MAIN + SIDE_PUBLISH + SIDE_PRICE + SIDE_TAX + SIDE_IMAGE + ["sku"] + SEO,
                                formfield_callback=partial(formfield_for, ac_urls={}))
class VariationBaseFS(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for f in self.forms:
            if not hasattr(f, "cleaned_data") or f.cleaned_data.get("DELETE") or not f.has_changed() and not f.instance.pk:
                continue
            if not f.cleaned_data.get("size") and not f.cleaned_data.get("manual_price"):
                f.add_error("size", "سایز را انتخاب کنید (یا برای محصول بدون سایز، قیمت دستی بنویسید).")


VariationFS = inlineformset_factory(Product, Variation, formset=VariationBaseFS, fields=VAR_FIELDS, extra=0, can_delete=True,
                                    formfield_callback=partial(formfield_for, ac_urls={}))
FaqFS = inlineformset_factory(Product, Faq, fields=["question", "answer", "order", "is_active"], extra=0, can_delete=True,
                              formfield_callback=partial(formfield_for, ac_urls={}),
                              widgets={"answer": forms.Textarea(attrs={"rows": 3})})


@staff_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        form = style_form(ProductForm(request.POST, instance=product))
        vfs = VariationFS(request.POST, instance=product or Product(), prefix="v")
        ffs = FaqFS(request.POST, instance=product or Product(), prefix="f")
        if form.is_valid() and vfs.is_valid() and ffs.is_valid():
            with transaction.atomic():
                p = form.save(commit=False)
                if not p.slug:
                    p.slug = unique_slug(Product, p.title)
                p.modified_at = timezone.now()
                created = p.pk is None
                p.save()
                form.save_m2m()
                vfs.instance = p
                vfs.save()
                ffs.instance = p
                ffs.save()
                # گالری به ترتیب انتخاب‌شده
                ids = [int(x) for x in request.POST.get("gallery", "").split(",") if x.strip().isdigit()]
                ProductImage.objects.filter(product=p).delete()
                valid = set(Media.objects.filter(pk__in=ids).values_list("pk", flat=True))
                ProductImage.objects.bulk_create([ProductImage(product=p, media_id=m, order=i) for i, m in enumerate(ids) if m in valid])
                if not p.image_id and ids:
                    Product.objects.filter(pk=p.pk).update(image_id=ids[0])
                if p.album_id:  # سایزهای محصول آلبومی = سایزهای آلبوم
                    from pricing.albums import sync_album_variations

                    sync_album_variations([Product.objects.select_related("album").get(pk=p.pk)])
                p.refresh_price_cache()
                save_fp_flags(request, p)
            log(request, "create" if created else "update", "محصولات", p)
            clear_site_cache()
            messages.success(request, f"«{p.title}» ذخیره شد.")
            if request.POST.get("_next") == "list":
                return redirect("/panel/products/")
            return redirect(f"/panel/products/{p.pk}/edit/")
        messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        form = style_form(ProductForm(instance=product, initial=None if product else {"status": "publish", "published_at": timezone.now()}))
        vfs = VariationFS(instance=product or Product(), prefix="v", queryset=Variation.objects.select_related("size").order_by("menu_order", "pk"))
        ffs = FaqFS(instance=product or Product(), prefix="f")
    for f in vfs.forms + [vfs.empty_form] + ffs.forms + [ffs.empty_form]:
        style_form(f)
    from farshplus.models import FarshPlusItem
    from farshplus.sync import inactive_reason

    own = None
    if product and product.album_id:
        vs = list(product.variations.all())
        own = {
            "custom": product.custom_base_price, "album_base": product.album.base_price,
            "override": sum(1 for v in vs if v.override_price is not None),
            "sale": sum(1 for v in vs if v.sale_price),
        }
        if own["custom"] is None and not own["override"] and not own["sale"]:
            own = None
    fp_item = FarshPlusItem.objects.filter(product=product).first() if product else None
    gallery = [pi.media for pi in ProductImage.objects.filter(product=product).select_related("media").order_by("order")] if product else []
    return render(request, "dashboard/product_form.html", {
        "obj": product, "form": form, "vfs": vfs, "ffs": ffs, "gallery": gallery, "own": own,
        "gallery_ids": ",".join(str(m.pk) for m in gallery), "fp": fp_item, "fp_off": inactive_reason(),
        "groups": {"main": MAIN, "publish": SIDE_PUBLISH, "price": SIDE_PRICE, "tax": SIDE_TAX, "image": SIDE_IMAGE, "seo": SEO},
    })


@staff_required
def product_follow_album(request, pk):
    """حذف قیمت‌های اختصاصی و حراج تا محصول دقیقاً از قیمت آلبوم پیروی کند."""
    from pricing.overrides import follow_album

    if request.method == "POST":
        product = get_object_or_404(Product, pk=pk)
        follow_album([product])
        log(request, "update", "محصولات", product, "پیروی کامل از قیمت آلبوم")
        clear_site_cache()
        messages.success(request, "قیمت‌های اختصاصی و حراج حذف شد؛ قیمت‌ها حالا دقیقاً از آلبوم می‌آیند.")
    return redirect(f"/panel/products/{pk}/edit/#sizes")


@staff_required
def product_duplicate(request, pk):
    if request.method != "POST":
        return redirect(f"/panel/products/{pk}/edit/")
    src = get_object_or_404(Product, pk=pk)
    with transaction.atomic():
        cats, tags, specs = list(src.categories.all()), list(src.tags.all()), list(src.specs.all())
        imgs = list(ProductImage.objects.filter(product=src))
        vars_ = list(src.variations.all())
        src.pk = None
        src.wp_id = None
        src.title = src.title + " (کپی)"
        src.slug = unique_slug(Product, src.title)
        src.sku = ""   # کد تازه خودکار ساخته می‌شود
        src.status = "draft"
        src.views = 0
        src.rating_avg, src.rating_count = 0, 0
        src.save()
        src.categories.set(cats)
        src.tags.set(tags)
        src.specs.set(specs)
        ProductImage.objects.bulk_create([ProductImage(product=src, media_id=i.media_id, order=i.order) for i in imgs])
        for v in vars_:
            attrs = list(v.attributes.all())
            v.pk, v.wp_id, v.product = None, None, src
            v.save()
            v.attributes.set(attrs)
        src.refresh_price_cache()
    log(request, "create", "محصولات", src, "کپی از محصول دیگر")
    messages.success(request, "کپی محصول به‌صورت پیش‌نویس ساخته شد.")
    return redirect(f"/panel/products/{src.pk}/edit/")


def _tri(v):
    return {"1": True, "0": False}.get(v)


def save_fp_flags(request, product):
    from farshplus.models import FarshPlusItem
    from farshplus.sync import get_item

    if "fp_enabled" not in request.POST:
        return
    en, feed = _tri(request.POST.get("fp_enabled")), _tri(request.POST.get("fp_in_feed"))
    item = FarshPlusItem.objects.filter(product=product).first()
    if item is None and en is None and feed is None:
        return
    item = item or get_item(product)
    item.enabled, item.in_feed = en, feed
    item.save()


@staff_required
def product_farshplus(request, pk):
    """ارسال فوری یک محصول به فرش پلاس"""
    from farshplus.client import ApiError
    from farshplus.sync import get_item, inactive_reason, process

    if request.method != "POST":
        return redirect(f"/panel/products/{pk}/edit/")
    product = get_object_or_404(Product, pk=pk)
    why = inactive_reason()
    if why:
        messages.error(request, why)
    else:
        item = get_item(product)
        item.mode = "manual"
        if not item.pk:
            item.save()
        try:
            messages.success(request, process(item, interactive=True))
        except ApiError as e:
            messages.error(request, f"فرش پلاس: {e}")
    log(request, "action", "فرش پلاس", product, "ارسال دستی")
    return redirect(f"/panel/products/{pk}/edit/#farshplus")
