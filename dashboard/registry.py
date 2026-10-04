"""تعریف بخش‌های پنل: هر بخش = یک مدل با ستون‌ها، جستجو، فیلتر، فرم و عملیات گروهی."""
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.utils.html import format_html


@dataclass
class Col:
    name: str
    label: str
    fn: Optional[Callable] = None     # obj -> متن/HTML
    sort: Optional[str] = None        # فیلد مرتب‌سازی
    cls: str = ""                     # کلاس CSS ستون


@dataclass
class Inline:
    model: object
    fk: str
    fields: list
    title: str
    extra: int = 1
    ordering: Optional[str] = None


@dataclass
class Resource:
    key: str
    model: object
    title: str
    single: str
    group: str
    icon: str = "box"
    columns: list = field(default_factory=list)
    search: list = field(default_factory=list)
    filters: list = field(default_factory=list)
    custom_filters: dict = field(default_factory=dict)  # نام -> (برچسب، [(مقدار، برچسب)]، تابع(qs, مقدار))
    date_filter: Optional[str] = None
    ordering: tuple = ("-pk",)
    fieldsets: list = field(default_factory=list)   # [(عنوان، [فیلدها]، "main"|"side")]
    readonly: list = field(default_factory=list)    # [(برچسب، تابع obj)]
    inlines: list = field(default_factory=list)
    actions: dict = field(default_factory=dict)     # key -> (برچسب، تابع(request, qs) -> پیام)
    can_add: bool = True
    can_delete: bool = True
    slug_from: Optional[str] = None
    view_url: Optional[Callable] = None
    queryset: Optional[Callable] = None
    after_save: Optional[Callable] = None
    ac: dict = field(default_factory=dict)          # نام فیلد -> کلید جستجوی آژاکسی (اگر با پیش‌فرض فرق دارد)
    edit_url: Optional[Callable] = None             # اگر صفحهٔ ویرایش اختصاصی دارد
    list_template: str = "dashboard/list.html"
    nav: bool = True
    per_page: int = 40
    help: str = ""
    initial: Optional[Callable] = None            # مقدارهای پیش‌فرض فرم «افزودن»

    @property
    def form_fields(self):
        out = []
        for _, fs, _ in self.fieldsets:
            out += fs
        return out

    def url(self):
        return f"/panel/{self.key}/"

    def obj_url(self, obj):
        if self.edit_url:
            return self.edit_url(obj)
        return f"/panel/{self.key}/{obj.pk}/"


REGISTRY = {}
GROUPS = []  # ترتیب گروه‌های منو


def register(res):
    REGISTRY[res.key] = res
    if res.group not in GROUPS:
        GROUPS.append(res.group)
    return res


# ------------------------------------------------------------ کمک‌های ستون
def thumb(attr="image"):
    def fn(o):
        m = getattr(o, attr, None)
        url = getattr(m, "url", "") if m else ""
        return format_html('<img class="thumb" src="{}" alt="" loading="lazy">', url) if url else format_html('<span class="thumb thumb--empty"></span>')
    return fn


def yesno(attr):
    def fn(o):
        v = getattr(o, attr)
        return format_html('<span class="dot {}"></span>{}', "on" if v else "off", "بله" if v else "خیر")
    return fn


def badge(attr, colors=None):
    def fn(o):
        val = getattr(o, attr)
        disp = getattr(o, f"get_{attr}_display")()
        return format_html('<span class="badge-ic b-{}">{}</span>', val, disp)
    return fn
