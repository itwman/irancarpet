from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Profile
from accounts.utils import normalize_mobile
from shop.models import Order
from shop.views import PROVINCES

from ..auth import staff_required
from ..forms import style_form
from ..models import log

User = get_user_model()


class UserForm(forms.Form):
    first_name = forms.CharField(label="نام", required=False, max_length=150)
    last_name = forms.CharField(label="نام خانوادگی", required=False, max_length=150)
    mobile = forms.CharField(label="موبایل", required=False, max_length=20)
    email = forms.EmailField(label="ایمیل", required=False)
    province = forms.ChoiceField(label="استان", required=False, choices=[("", "—")] + [(p, p) for p in PROVINCES])
    city = forms.CharField(label="شهر", required=False, max_length=80)
    address = forms.CharField(label="آدرس", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    postal_code = forms.CharField(label="کد پستی", required=False, max_length=10)
    password = forms.CharField(label="رمز عبور تازه", required=False, widget=forms.PasswordInput(render_value=False),
                               help_text="خالی بگذارید تا رمز فعلی بماند.")
    is_active = forms.BooleanField(label="حساب فعال است", required=False, initial=True)
    is_staff = forms.BooleanField(label="دسترسی به پنل مدیریت", required=False)
    is_superuser = forms.BooleanField(label="مدیر کل (مدیریت کارمندان)", required=False)

    def __init__(self, *args, user=None, editor=None, **kw):
        super().__init__(*args, **kw)
        self.user, self.editor = user, editor
        if not editor.is_superuser:
            for f in ("is_staff", "is_superuser"):
                self.fields[f].disabled = True
                self.fields[f].help_text = "فقط مدیر کل می‌تواند تغییر دهد."

    def clean_mobile(self):
        raw = self.cleaned_data["mobile"]
        if not raw:
            return ""
        m = normalize_mobile(raw)
        if not m:
            raise forms.ValidationError("شمارهٔ موبایل درست نیست.")
        qs = Profile.objects.filter(mobile=m)
        if self.user:
            qs = qs.exclude(user=self.user)
        if qs.exists():
            raise forms.ValidationError("این موبایل برای کاربر دیگری ثبت شده است.")
        return m

    def clean_email(self):
        e = self.cleaned_data["email"]
        if e and User.objects.filter(email__iexact=e).exclude(pk=getattr(self.user, "pk", None)).exists():
            raise forms.ValidationError("این ایمیل برای کاربر دیگری ثبت شده است.")
        return e

    def clean(self):
        d = super().clean()
        if not self.user and not d.get("mobile") and not d.get("email"):
            raise forms.ValidationError("برای کاربر تازه موبایل یا ایمیل لازم است.")
        if d.get("password") and len(d["password"]) < 8:
            self.add_error("password", "رمز باید دست‌کم ۸ حرف باشد.")
        return d


@staff_required
def customer_edit(request, pk=None):
    user = get_object_or_404(User.objects.select_related("profile"), pk=pk) if pk else None
    profile = Profile.objects.filter(user=user).first() if user else None
    initial = {}
    if user:
        initial = {"first_name": user.first_name, "last_name": user.last_name, "email": user.email, "is_active": user.is_active,
                   "is_staff": user.is_staff, "is_superuser": user.is_superuser}
        if profile:
            initial.update(mobile=profile.mobile or "", province=profile.province, city=profile.city, address=profile.address,
                           postal_code=profile.postal_code)
    form = UserForm(request.POST or None, initial=initial, user=user, editor=request.user)
    style_form(form)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            u = user or User(username=d["mobile"] or d["email"])
            if not user:
                u.set_unusable_password()
            u.first_name, u.last_name, u.email = d["first_name"], d["last_name"], d["email"]
            if u.pk != request.user.pk:
                u.is_active = d["is_active"]
            if request.user.is_superuser and u.pk != request.user.pk:
                u.is_staff, u.is_superuser = d["is_staff"], d["is_superuser"]
            if d["password"]:
                u.set_password(d["password"])
            u.save()
            p, _ = Profile.objects.get_or_create(user=u)
            p.mobile = d["mobile"] or None
            p.province, p.city, p.address, p.postal_code = d["province"], d["city"], d["address"], d["postal_code"]
            p.save()
        log(request, "update" if user else "create", "مشتریان", u)
        messages.success(request, "اطلاعات کاربر ذخیره شد.")
        return redirect(f"/panel/customers/{u.pk}/edit/")
    orders = Order.objects.filter(user=user).order_by("-created_at") if user else []
    return render(request, "dashboard/customer_form.html", {"obj": user, "form": form, "orders": orders})
