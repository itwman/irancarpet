from django.urls import path

from . import seller as sv
from . import views

urlpatterns = [
    path("sell/", views.landing, name="sell"),
    path("seller/", sv.home),
    path("seller/stats/", sv.stats),
    path("seller/more/", sv.more),
    path("seller/look/", sv.look),
    path("seller/shelves/", sv.shelves),
    path("seller/albums/", sv.albums),
    path("seller/albums/add/", sv.album_edit),
    path("seller/albums/<int:pk>/", sv.album_edit),
    path("seller/quick/", sv.quick),
    path("seller/offers/", sv.offers),
    path("seller/coupons/", sv.coupons),
    path("seller/questions/", sv.questions),
    path("seller/products/bulk/", sv.bulk),
    path("seller/products/<int:pk>/stock/", sv.stock_toggle),
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
    path("vendor/<str:slug>/follow/", views.follow),
    path("my-account/orders/<int:number>/received/<int:pk>/", views.customer_received),
]
