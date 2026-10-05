"""ویدیوی فرش: آپارات یا فایل mp4."""
import re

from django.conf import settings

APARAT = re.compile(r"aparat\.com/(?:v/|video/video/embed/videohash/)([A-Za-z0-9]+)")


def info(product):
    url = (product.video_url or "").strip()
    if not url:
        return None
    m = APARAT.search(url)
    poster = product.image.absolute_url if product.image_id and product.image else ""
    if m:
        h = m.group(1)
        return {"kind": "aparat", "embed": f"https://www.aparat.com/video/video/embed/videohash/{h}/vt/frame",
                "page": f"https://www.aparat.com/v/{h}", "poster": poster}
    if url.lower().split("?")[0].endswith((".mp4", ".webm", ".mov")):
        return {"kind": "file", "src": url, "poster": poster}
    return {"kind": "link", "page": url, "poster": poster}


def schema(product, v):
    """VideoObject برای نتایج ویدیویی گوگل."""
    if not v:
        return None
    from core import seo

    data = {
        "@context": "https://schema.org", "@type": "VideoObject",
        "name": f"ویدیوی {product.title}",
        "description": seo.plain(_desc(product), 200) or product.title,
        "thumbnailUrl": [v["poster"]] if v["poster"] else [],
        "uploadDate": (product.published_at or product.modified_at).isoformat() if (product.published_at or product.modified_at) else None,
    }
    if v["kind"] == "aparat":
        data["embedUrl"] = v["embed"]
        data["url"] = v["page"]
    elif v["kind"] == "file":
        data["contentUrl"] = v["src"] if v["src"].startswith("http") else settings.SITE_URL + v["src"]
    else:
        data["url"] = v["page"]
    return {k: x for k, x in data.items() if x}


def _desc(product):
    if product.use_template:
        from content.render import build

        d = build(product)
        return d["bullets"] or d["html"]
    return product.short_description or product.content
