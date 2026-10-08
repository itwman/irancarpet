from django.utils.html import escape, format_html, linebreaks

from core.templatetags.fa import fa_num


def text_to_html(text):
    """متن سادهٔ فروشنده ← HTML امن (پاراگراف و شکست خط، بدون تگ دلخواه)."""
    return linebreaks(escape((text or "").strip()))


def seller_block(p):
    s = p.seller
    rows = [("فروشنده", format_html('<a href="{}">{}</a>', s.get_absolute_url(), s.name)),
            ("ارسال از", escape(s.city)),
            ("هزینهٔ ارسال", s.shipping_label),
            ("زمان آماده‌سازی", fa_num(f"{s.prep_days} روز کاری"))]
    if s.return_policy:
        rows.append(("مرجوعی", escape(s.return_policy)))
    html = "<ul>" + "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in rows) + "</ul>"
    html += "<p>پرداخت امن از درگاه ایران کارپت انجام می‌شود و مبلغ تا تحویل سالم کالا نزد ایران کارپت می‌ماند.</p>"
    return {"title": "فروشنده و ارسال", "html": html, "open": True}
