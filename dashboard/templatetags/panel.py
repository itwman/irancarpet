from django import forms, template

from ..registry import REGISTRY

register = template.Library()


def _badge(r):
    if not r.badge:
        return 0
    try:
        return r.badge() or 0
    except Exception:  # noqa: BLE001
        return 0


@register.simple_tag(takes_context=True)
def panel_nav(context):
    """منوی کناری پنل از روی dashboard/nav.py؛ بخش‌هایی که آن‌جا نیامده‌اند در «سایر»."""
    from ..nav import LAYOUT, OTHER

    path = context["request"].path
    full = context["request"].get_full_path()
    used, out = set(), []

    def item(row):
        if isinstance(row, str):
            r = REGISTRY.get(row)
            if r is None or not r.nav:
                return None
            used.add(row)
            return {"title": r.title, "url": r.url(), "badge": _badge(r)}
        title, url = row
        if title == "#":
            return {"head": url}
        if not url.startswith("/"):  # («عنوان دلخواه», "کلید بخش»)
            r = REGISTRY.get(url)
            if r is None or not r.nav:
                return None
            used.add(url)
            return {"title": title, "url": r.url(), "badge": _badge(r)}
        return {"title": title, "url": url, "badge": 0}

    for title, icon, rows in LAYOUT:
        items = [i for i in (item(r) for r in rows) if i]
        out.append({"title": title, "icon": icon, "items": items})
    rest = [{"title": r.title, "url": r.url(), "badge": _badge(r)} for k, r in REGISTRY.items() if r.nav and k not in used]
    if rest:
        out.append({"title": OTHER[0], "icon": OTHER[1], "items": rest})

    # فعال: نشانی‌های دارای ?… فقط با تطابق کامل؛ نشانی ساده وقتی هم‌خانواده‌ٔ دقیق‌ترش فعال نباشد.
    links = [i for g in out for i in g["items"] if "url" in i]
    exact = {i["url"] for i in links if "?" in i["url"] and full.startswith(i["url"])}
    for i in links:
        u = i["url"]
        if "?" in u:
            i["active"] = u in exact
        else:
            i["active"] = (path.startswith(u) and not any(e.split("?")[0] == u for e in exact)) or (
                u == "/panel/crm/segments/" and path.startswith("/panel/crm/customer/"))
    # اگر دو نشانی ساده هر دو فعال‌اند (مثل /panel/products/ و /panel/products/quick/) فقط بلندتر بماند
    act = [i for i in links if i["active"] and "?" not in i["url"]]
    if len(act) > 1:
        best = max(act, key=lambda i: len(i["url"]))
        for i in act:
            i["active"] = i is best
    for g in out:
        g["badge"] = sum(i.get("badge") or 0 for i in g["items"])
        g["active"] = any(i.get("active") for i in g["items"])
    return out


@register.filter
def wtype(bound):
    w = bound.field.widget
    if isinstance(w, forms.CheckboxInput):
        return "check"
    if "rich" in (w.attrs.get("class") or ""):
        return "rich"
    if isinstance(w, forms.HiddenInput):
        return "hidden"
    return "input"


@register.filter
def getattr_(obj, name):
    return getattr(obj, name, "")


@register.filter
def get_field(form, name):
    return form[name]
