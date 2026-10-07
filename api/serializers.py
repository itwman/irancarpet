"""تبدیل مدل‌ها به JSON اپلیکیشن."""
import re
from html import unescape
from urllib.parse import quote

from django.conf import settings
from django.utils.html import strip_tags

from core.templatetags.fa import reeds_of

THUMB_SIZES = (240, 480, 960)


def media_url(m):
    return m.absolute_url if m and m.file else ""


def thumb_url(m, w=480):
    """نسخهٔ کوچک تصویر برای اپ (در اولین درخواست ساخته و نگه داشته می‌شود)."""
    if not m or not m.file:
        return ""
    w = min(THUMB_SIZES, key=lambda x: abs(x - w))
    return f"{settings.SITE_URL}/app-img/{w}/{quote(m.file.name)}"


def plain(html, limit=0):
    t = re.sub(r"\s+", " ", unescape(strip_tags(html or ""))).strip()
    return (t[:limit] + "…") if limit and len(t) > limit else t


def card(p):
    """کارت محصول در فهرست‌ها."""
    return {
        "id": p.pk,
        "title": p.title,
        "image": thumb_url(p.image, 480),
        "price": p.min_price or 0,
        "price_is_from": not p.album_id,
        "in_stock": p.stock_status != "outofstock" and p.sale_status not in ("unavailable",),
        "rating": float(p.rating_avg or 0),
        "rating_count": p.rating_count or 0,
        "reeds": reeds_of(p.title),
        "brand": p.brand.name if getattr(p, "brand_id", None) and p.brand else "",
    }


def size_row(v):
    s = v.size
    return {
        "variation_id": v.pk,
        "label": s.label if s else (v.sku or "—"),
        "dimensions": s.dimensions if s else "",
        "width": float(s.width or 0) if s else 0,
        "length": float(s.length or 0) if s else 0,
        "diameter": float(s.diameter or 0) if s else 0,
        "round": bool(s and s.type == "round"),
        "area": float(s.area or 0) if s else 0,
        "price": v.price or 0,
        "regular_price": v.final_price or 0,
        "on_sale": v.on_sale,
        "available": bool(v.is_available and v.price),
        "pair_only": v.is_pair_only,
        "attributes": [a.name for a in v.attributes.all()],
    }


def _video(p):
    from catalog.video import info

    v = info(p)
    if not v:
        return None
    url = v.get("page") or v.get("src") or ""
    return {"kind": v["kind"], "url": url if url.startswith("http") else settings.SITE_URL + url}


def offer_json(o, with_product=False):
    d = {"id": o.pk, "variation": o.variation.pk, "size": o.size.label, "price": o.price, "regular_price": o.regular_price,
         "percent": o.off_percent, "remaining": o.remaining, "ends_at": o.ends_at.isoformat() if o.ends_at else None,
         "allowed": o.allowed, "note": f"قیمت ویژهٔ هر تخته؛ برای خرید {o.allowed_label} تخته."}
    if with_product:
        d.update(product_id=o.product_id, title=o.product.title, image=thumb_url(o.product.image, 480) if o.product.image_id else "")
    return d


def product_detail(p, gallery, variations, specs, reviews, faqs, related):
    from content.render import build, color_siblings, full_text, to_text

    doc = build(p, list(variations))
    blocks_html = "".join(f"<h2>{b['title']}</h2>{b['html']}" for b in doc["blocks"])
    return {
        **card(p),
        "slug": p.slug,
        "url": settings.SITE_URL + p.get_absolute_url(),
        "sku": p.sku,
        "english_name": p.english_name,
        "purchasable": p.is_purchasable,
        "sale_status": p.sale_status,
        "album": p.album.name if p.album_id else "",
        "images": [{"full": media_url(m), "thumb": thumb_url(m, 960), "w": m.width or 0, "h": m.height or 0} for m in gallery],
        "short_description": to_text(doc["bullets"]),
        "content_html": (doc["html"] or "") + blocks_html,
        "content_text": full_text(doc)[:6000],
        "info_blocks": [{"title": b["title"], "text": to_text(b["html"]), "html": b["html"]} for b in doc["blocks"]],
        "special_offers": [offer_json(o) for o in __import__("shop.offers", fromlist=["for_product"]).for_product(p)],
        "colors": [{"id": x["product"].pk, "title": x["product"].title, "color": x["color"], "current": x["current"],
                    "image": thumb_url(x["product"].image, 240) if x["product"].image_id else ""} for x in color_siblings(p)],
        "sizes": [size_row(v) for v in variations],
        "specs": specs,
        "categories": [{"id": c.pk, "name": c.name} for c in p.categories.all()],
        "tags": [t.name for t in p.tags.all()],
        "reviews": [{"author": r.author_name, "rating": r.rating or 0, "text": plain(r.content, 600),
                     "date": r.created_at.date().isoformat(), "verified": r.verified,
                     "photos": [settings.SITE_URL + ph.url for ph in r.photos.all()]} for r in reviews],
        "video": _video(p),
        "faqs": [{"q": f.question, "a": plain(f.answer)} for f in faqs],
        "related": [card(x) for x in related],
    }


def order_row(o, items=False):
    d = {
        "number": o.number,
        "status": o.status,
        "status_label": o.status_label,
        "payment_label": o.get_payment_mode_display(),
        "grand_total": o.grand_total,
        "created_at": o.created_at.isoformat(),
        "items_total": o.items_total,
        "discount": o.discount, "coupon_code": o.coupon_code,
        "paid_amount": o.paid_amount,
        "remaining": o.remaining,
        "online_amount": o.online_amount,
        "payment_mode": o.payment_mode,
        "shipping_mode": o.shipping_mode,
        "can_pay": o.can_pay,
        "tracking_code": o.tracking_code,
        "items_count": sum(i.quantity for i in o.items.all()),
    }
    if o.is_installment and o.installment:
        plan = o.installment_plan
        state = o.installment_state or "review"
        note = ""
        if plan:
            note = {"review": plan.review_note, "approved": plan.approved_note, "done": plan.approved_note}.get(state, "")
        d["installment"] = {**o.installment, "state": state, "state_label": o.get_installment_state_display(),
                            "plan_title": plan.title if plan else o.installment.get("plan_title", ""), "note": note}
    if items:
        d.update({
            "items": [{"title": i.title, "size": i.size_label, "unit_price": i.unit_price, "quantity": i.quantity,
                       "product_id": i.product_id,
                       "image": thumb_url(i.product.image, 240) if i.product_id and i.product and i.product.image_id else ""}
                      for i in o.items.all()],
            "address": {"first_name": o.first_name, "last_name": o.last_name, "mobile": o.mobile, "province": o.province,
                        "city": o.city, "address": o.address, "postal_code": o.postal_code},
            "payments": [{"amount": pm.amount, "status": pm.status, "gateway": pm.gateway, "ref_id": pm.ref_id,
                          "date": pm.created_at.isoformat()} for pm in o.payments.all()],
        })
    return d
