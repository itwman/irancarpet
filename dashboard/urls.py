from django.urls import path

from . import resources  # noqa: F401  ثبت بخش‌ها
from .ac import autocomplete
from .views import crud, home, media, orders, people, products, settings

urlpatterns = [
    path("", home.home, name="panel"),
    path("search/", home.search),
    path("settings/", settings.settings_view),
    path("ac/<str:key>/", autocomplete),
    path("media/upload/", media.upload),
    path("products/add/", products.product_edit),
    path("products/<int:pk>/edit/", products.product_edit),
    path("products/<int:pk>/duplicate/", products.product_duplicate),
    path("products/<int:pk>/farshplus/", products.product_farshplus),
    path("orders/<int:pk>/view/", orders.order_view),
    path("orders/<int:pk>/print/", orders.order_print),
    path("customers/add/", people.customer_edit),
    path("customers/<int:pk>/edit/", people.customer_edit),
    path("<str:key>/", crud.list_view),
    path("<str:key>/add/", crud.edit_view),
    path("<str:key>/<int:pk>/", crud.edit_view),
    path("<str:key>/<int:pk>/delete/", crud.delete_view),
]
