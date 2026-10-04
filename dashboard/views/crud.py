import csv
from functools import partial

from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.core.paginator import Paginator
from django.db import models, router, transaction
from django.db.models import Q
from django.forms import inlineformset_factory, modelform_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import strip_tags
from django.utils.text import capfirst

from ..ac import unique_slug
from ..auth import clear_site_cache, staff_required
from ..forms import JalaliDateTimeField, formfield_for, style_form, to_en
from ..models import log
from ..registry import REGISTRY


def get_res(key):
    res = REGISTRY.get(key)
    if not res:
        raise Http404
    return res


def build_form_class(res, fields=None):
    return modelform_factory(res.model, fields=fields or res.form_fields,
                             formfield_callback=partial(formfield_for, ac_urls=res.ac))


def build_inline(res, inline):
    return inlineformset_factory(res.model, inline.model, fk_name=inline.fk, fields=inline.fields, extra=inline.extra,
                                 can_delete=True, formfield_callback=partial(formfield_for, ac_urls={}))


# ---------------------------------------------------------------- فهرست
def _field(model, name):
    try:
        return model._meta.get_field(name)
    except Exception:  # noqa: BLE001
        return None


def filter_specs(res, request):
    """ساخت فیلترهای کنار فهرست + اعمال روی queryset"""
    specs = []
    for name in res.filters:
        f = _field(res.model, name.split("__")[0])
        val = request.GET.get(name, "")
        spec = {"name": name, "label": capfirst(f.verbose_name) if f else name, "value": val, "kind": "select", "options": []}
        if f is None:
            continue
        if f.choices:
            spec["options"] = [(str(k), v) for k, v in f.choices]
        elif isinstance(f, models.BooleanField):
            spec["options"] = [("1", "بله"), ("0", "خیر")]
        elif f.is_relation:
            from ..ac import AC

            key = AC.key_for(f.related_model)
            if key:
                spec["kind"] = "ac"
                spec["ac"] = f"/panel/ac/{key}/"
                if val:
                    o = f.related_model.objects.filter(pk=val).first()
                    spec["selected"] = (val, (AC.get(key).label or str)(o)) if o else None
            else:
                spec["options"] = [(str(o.pk), str(o)) for o in f.related_model.objects.all()[:200]]
        specs.append(spec)
    for name, (label, options, _) in res.custom_filters.items():
        specs.append({"name": name, "label": label, "value": request.GET.get(name, ""), "kind": "select", "options": options})
    return specs


def apply_filters(res, qs, request):
    for name in res.filters:
        val = request.GET.get(name, "")
        if val == "":
            continue
        f = _field(res.model, name.split("__")[0])
        if isinstance(f, models.BooleanField):
            qs = qs.filter(**{name: val == "1"})
        else:
            qs = qs.filter(**{name: val})
    for name, (_, _, fn) in res.custom_filters.items():
        val = request.GET.get(name, "")
        if val:
            qs = fn(qs, val)
    if res.date_filter:
        jf = JalaliDateTimeField(with_time=False, required=False)
        for key, op in (("from", "gte"), ("to", "lte")):
            v = request.GET.get(f"d_{key}")
            if v:
                try:
                    from datetime import datetime, time, timedelta

                    from django.utils import timezone

                    d = jf.to_python(v)
                    if op == "lte":
                        d = d + timedelta(days=1)
                    edge = timezone.make_aware(datetime.combine(d, time.min))
                    qs = qs.filter(**{f"{res.date_filter}__{'gte' if op == 'gte' else 'lt'}": edge})
                except Exception:  # noqa: BLE001
                    pass
    q = (request.GET.get("q") or "").strip()
    if q and res.search:
        q_en = to_en(q)
        cond = Q()
        for f in res.search:
            if f.startswith("="):
                if q_en.isdigit():
                    cond |= Q(**{f[1:]: int(q_en)})
            else:
                cond |= Q(**{f"{f}__icontains": q})
                if q_en != q:
                    cond |= Q(**{f"{f}__icontains": q_en})
        qs = qs.filter(cond)
    return qs


def list_columns(res, request):
    """ستون‌های پیش‌فرض + ستون‌های اختیاری که کاربر انتخاب کرده (در نشست ذخیره می‌شود)."""
    if not res.extra_columns:
        return res.columns, []
    extra = res.extra_columns()
    skey = f"panel_cols_{res.key}"
    if request.GET.get("cols_set"):
        chosen = [c for c in request.GET.getlist("cols") if c]
        request.session[skey] = chosen
    else:
        chosen = request.session.get(skey, [])
    cols = list(res.columns)
    extra_on = [c for c in extra if c.name in chosen]
    cols[-1:-1] = extra_on   # پیش از آخرین ستون (تاریخ)
    return cols, [(c.name, c.label, c.name in chosen) for c in extra]


def action_specs(res):
    out = []
    for k, a in res.actions.items():
        out.append({"key": k, "label": a[0], "input": a[2] if len(a) > 2 else "",
                    "choices": a[3]() if len(a) > 3 and a[3] else None})
    return out


@staff_required
def list_view(request, key):
    res = get_res(key)
    qs = res.model.objects.all()
    if res.queryset:
        qs = res.queryset(qs)
    qs = apply_filters(res, qs, request)
    sortable = {c.sort for c in res.columns if c.sort}
    o = request.GET.get("o", "")
    qs = qs.order_by(o, "-pk") if o.lstrip("-") in sortable else qs.order_by(*res.ordering)

    if request.method == "POST":
        act = request.POST.get("action")
        ids = request.POST.getlist("ids")
        if request.POST.get("all") == "1":   # همهٔ نتایج فیلتر (همهٔ صفحه‌ها)
            ids = list(qs.values_list("pk", flat=True))
        if ids and act:
            sel = res.model.objects.filter(pk__in=ids)
            if act == "delete" and res.can_delete:
                n = sel.count()
                with transaction.atomic():
                    for obj in sel:
                        log(request, "delete", res.title, obj)
                    sel.delete()
                messages.success(request, f"{n} مورد حذف شد.")
            elif act in res.actions:
                spec = res.actions[act]
                if len(spec) > 2 and not request.POST.get("action_value", "").strip():
                    messages.error(request, f"برای «{spec[0]}» مقدار {spec[2]} را وارد کنید.")
                    return redirect(request.get_full_path())
                msg = spec[1](request, sel)
                log(request, "action", res.title, None, f"{res.actions[act][0]} ({len(ids)} مورد)")
                if msg:
                    messages.success(request, msg)
            clear_site_cache()
        return redirect(request.get_full_path())

    if request.GET.get("export") == "csv":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{res.key}.csv"'
        resp.write("﻿")
        w = csv.writer(resp)
        w.writerow([c.label for c in res.columns])
        for obj in qs[:20000]:
            w.writerow([strip_tags(str(c.fn(obj) if c.fn else getattr(obj, c.name, ""))) for c in res.columns if True])
        return resp

    columns, col_choices = list_columns(res, request)
    page = Paginator(qs, res.per_page).get_page(request.GET.get("page"))
    rows = []
    for obj in page.object_list:
        cells = [(c.fn(obj) if c.fn else getattr(obj, c.name, ""), c.cls) for c in columns]
        rows.append({"obj": obj, "url": res.obj_url(obj), "cells": cells,
                     "public": res.view_url(obj) if res.view_url else ""})
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("o", None)
    return render(request, res.list_template, {
        "res": res, "rows": rows, "page": page, "filters": filter_specs(res, request), "o": o,
        "columns": columns, "col_choices": col_choices, "actions": action_specs(res),
        "q": request.GET.get("q", ""), "base_qs": params.urlencode(), "d_from": request.GET.get("d_from", ""),
        "d_to": request.GET.get("d_to", ""), "filtered": any(request.GET.get(k) for k in ["q", "d_from", "d_to", *res.filters, *res.custom_filters]),
    })


# ---------------------------------------------------------------- ویرایش
def fill_slug(res, obj):
    if res.slug_from and hasattr(obj, "slug") and not obj.slug:
        obj.slug = unique_slug(res.model, getattr(obj, res.slug_from) or "item")


@staff_required
def edit_view(request, key, pk=None):
    res = get_res(key)
    if res.edit_url and pk:
        obj = get_object_or_404(res.model, pk=pk)
        return redirect(res.edit_url(obj))
    obj = get_object_or_404(res.model, pk=pk) if pk else None
    if obj is None and not res.can_add:
        raise Http404
    Form = build_form_class(res)
    inlines = [(i, build_inline(res, i)) for i in res.inlines]
    if request.method == "POST":
        form = style_form(Form(request.POST, request.FILES, instance=obj))
        formsets = [(i, FS(request.POST, request.FILES, instance=obj or res.model(), prefix=f"in{n}")) for n, (i, FS) in enumerate(inlines)]
        if form.is_valid() and all(fs.is_valid() for _, fs in formsets):
            with transaction.atomic():
                o = form.save(commit=False)
                fill_slug(res, o)
                created = o.pk is None
                o.save()
                form.save_m2m()
                for _, fs in formsets:
                    fs.instance = o
                    fs.save()
                if res.after_save:
                    res.after_save(request, o, created, form)
            log(request, "create" if created else "update", res.title, o)
            clear_site_cache()
            messages.success(request, f"«{o}» ذخیره شد.")
            nxt = request.POST.get("_next")
            if nxt == "list":
                return redirect(res.url())
            if nxt == "add":
                return redirect(res.url() + "add/")
            return redirect(res.obj_url(o))
        messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")
    else:
        initial = None
        if not obj:
            initial = res.initial() if res.initial else {}
            initial.update({k: v for k, v in request.GET.items() if k in res.form_fields})
        form = style_form(Form(instance=obj, initial=initial))
        formsets = [(i, FS(instance=obj or res.model(), prefix=f"in{n}")) for n, (i, FS) in enumerate(inlines)]
    for _, fs in formsets:
        for f in fs.forms + [fs.empty_form]:
            style_form(f)
    groups = []
    for title, names, place in res.fieldsets:
        groups.append({"title": title, "place": place, "fields": [form[n] for n in names if n in form.fields]})
    return render(request, "dashboard/form.html", {
        "res": res, "obj": obj, "form": form, "groups": groups, "formsets": formsets,
        "readonly": [(lbl, fn(obj)) for lbl, fn in res.readonly] if obj else [],
        "public": res.view_url(obj) if obj and res.view_url else "",
    })


@staff_required
def delete_view(request, key, pk):
    res = get_res(key)
    if not res.can_delete:
        raise Http404
    obj = get_object_or_404(res.model, pk=pk)
    collector = NestedObjects(using=router.db_for_write(res.model))
    collector.collect([obj])
    related = {}
    for m, objs in collector.model_objs.items():
        if m is not res.model:
            related[m._meta.verbose_name_plural] = len(objs)
    if request.method == "POST":
        log(request, "delete", res.title, obj)
        obj.delete()
        clear_site_cache()
        messages.success(request, f"«{obj}» حذف شد.")
        return redirect(res.url())
    return render(request, "dashboard/delete.html", {"res": res, "obj": obj, "related": related})
