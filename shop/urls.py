from django.urls import path, re_path

from accounts import views as acc
from . import views

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add),
    path("cart/update/", views.cart_update),
    path("checkout/", views.checkout, name="checkout"),
    re_path(r"^checkout-2/(?:.*)$", views.checkout_legacy),
    path("pay/<str:gateway>/callback/", views.callback),
    path("pay/fake/<int:pk>/", views.fake_gateway),
    path("track-order/", views.track_order, name="track"),
    path("my-account/", acc.dashboard, name="account"),
    path("my-account/login/", acc.login_view, name="login"),
    path("my-account/verify/", acc.verify_view),
    path("my-account/logout/", acc.logout_view),
    path("my-account/orders/<int:number>/", views.order_detail),
    path("my-account/orders/<int:number>/pay/", views.order_pay),
    # زیرصفحه‌های قدیمی ووکامرس (orders، edit-account، lost-password و...)
    re_path(r"^my-account/[^/]+/(?:[^/]+/)?$", views.account_legacy),
]
