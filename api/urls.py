from django.urls import path

from . import views as v

urlpatterns = [
    path("config/", v.config),
    path("home/", v.home),
    path("categories/", v.categories),
    path("products/", v.products),
    path("products/filters/", v.filters),
    path("products/<int:pk>/", v.product),
    path("auth/otp/", v.auth_otp),
    path("auth/verify/", v.auth_verify),
    path("auth/password/", v.auth_password),
    path("auth/logout/", v.auth_logout),
    path("me/", v.me),
    path("cart/quote/", v.cart_quote),
    path("orders/", v.orders),
    path("orders/create/", v.order_create),
    path("orders/<int:number>/", v.order),
    path("track/", v.track),
    path("wishlist/", v.wishlist),
    path("notifications/", v.notifications),
    path("pay/<str:token>/", v.pay),
]
