from django.urls import path

from . import views

urlpatterns = [
    path("sell/", views.landing, name="sell"),
    path("seller/", views.dashboard),
    path("seller/pause/", views.toggle_pause),
    path("seller/products/", views.product_list),
    path("seller/products/add/", views.product_edit),
    path("seller/products/<int:pk>/", views.product_edit),
    path("seller/products/<int:pk>/toggle/", views.product_hide),
    path("seller/orders/", views.order_list),
    path("seller/orders/<int:pk>/", views.order_detail),
    path("seller/finance/", views.finance),
    path("seller/settings/", views.shop_settings),
    path("vendor/<str:slug>/", views.store),
    path("my-account/orders/<int:number>/received/<int:pk>/", views.customer_received),
]
