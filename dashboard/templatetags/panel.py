from django import forms, template

from ..registry import GROUPS, REGISTRY

register = template.Library()

EXTRA_NAV = {
    "فروش": [("کارمندان", "/panel/customers/?is_staff=1", "shield")],
    "فروشگاه": [("ساخت گروهی فرش", "/panel/products/bulk/", "plus"), ("جایگزینی متن و لینک‌ها", "/panel/content-tools/", "search")],
    "تنظیمات": [("تنظیمات سایت، درگاه و پیامک", "/panel/settings/", "settings")],
    "اپلیکیشن": [("تنظیمات اپلیکیشن", "/panel/settings/?tab=app", "settings")],
    "همکاری در فروش": [("تنظیمات همکاری در فروش", "/panel/settings/?tab=affiliate", "settings")],
    "باشگاه مشتریان": [("تنظیمات پیامک سفارش و باشگاه", "/panel/settings/?tab=crm", "settings")],
    "مارکت‌پلیس": [("صف بررسی کالاها", "/panel/seller-products/?queue=1", "search"), ("تنظیمات مارکت‌پلیس", "/panel/settings/?tab=market", "settings")],
}
NAV_FIRST = {"باشگاه مشتریان": [("گزارش فروش و مشتریان", "/panel/crm/report/", "layers"),
                                 ("گزارش بازدید و ورودی‌ها", "/panel/stats/", "layers"),
                                 ("پروفایل و گروه‌های مشتریان", "/panel/crm/segments/", "users")]}
GROUP_ICONS = {"باشگاه مشتریان": "users", "فروش": "receipt", "فروشگاه": "carpet", "قیمت‌گذاری": "layers", "مجله و برگه‌ها": "pen", "رسانه": "image",
               "سئو": "arrow", "اپلیکیشن": "phone", "تنظیمات": "settings", "فرش‌یاب": "search", "همکاری در فروش": "users", "مارکت‌پلیس": "box"}


def _badge(r):
    if not r.badge:
        return 0
    try:
        return r.badge() or 0
    except Exception:  # noqa: BLE001
        return 0


@register.simple_tag(takes_context=True)
def panel_nav(context):
    path = context["request"].path
    full = context["request"].get_full_path()
    out = []
    for g in GROUPS:
        items = [{"title": t, "url": u, "icon": i, "active": path.startswith(u) or (u.endswith("/segments/") and path.startswith("/panel/crm/customer/"))}
                 for t, u, i in NAV_FIRST.get(g, [])]
        for r in REGISTRY.values():
            if r.group == g and r.nav:
                items.append({"title": r.title, "url": r.url(), "icon": r.icon, "active": path.startswith(r.url()),
                              "badge": _badge(r)})
        for title, url, icon in EXTRA_NAV.get(g, []):
            items.append({"title": title, "url": url, "icon": icon, "active": full == url or (url == "/panel/settings/" and path == url)})
        if g == "تنظیمات":
            items = [items[-1]] + items[:-1]
        if any(i["active"] for i in items if i["url"] == "/panel/customers/?is_staff=1"):
            for i in items:
                if i["url"] == "/panel/customers/":
                    i["active"] = False
        out.append({"title": g, "items": items, "icon": GROUP_ICONS.get(g, "box"), "badge": sum(i.get("badge") or 0 for i in items)})
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
