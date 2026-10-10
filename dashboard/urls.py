from django.urls import path

from . import resources  # noqa: F401  ثبت بخش‌ها
from .ac import autocomplete
from content import views as content_views
from blog import panel as blog_panel
from crm import customer as crm_customer
from crm import views as crm_views
from growth import panel as growth_panel
from stats import views as stats_views

from .views import crud, home, media, orders, people, products, settings

urlpatterns = [
    path("", home.home, name="panel"),
    path("search/", home.search),
    path("settings/", settings.settings_view),
    path("settings/rajyar-pricelist.png", settings.rajyar_pricelist_png),
    path("ac/<str:key>/", autocomplete),
    path("media/upload/", media.upload),
    path("products/add/", products.product_edit),
    path("products/bulk/", content_views.bulk),
    path("content-tools/", content_views.tools),
    path("content-templates/<int:pk>/preview/", content_views.preview),
    path("products/<int:pk>/edit/", products.product_edit),
    path("products/<int:pk>/duplicate/", products.product_duplicate),
    path("products/<int:pk>/follow-album/", products.product_follow_album),
    path("products/<int:pk>/farshplus/", products.product_farshplus),
    path("orders/<int:pk>/view/", orders.order_view),
    path("orders/<int:pk>/print/", orders.order_print),
    path("orders/<int:pk>/installment/", orders.order_installment),
    path("customers/add/", people.customer_edit),
    path("customers/<int:pk>/edit/", people.customer_edit),
    path("rewrites/<int:pk>/preview/", blog_panel.preview),
    path("special-offers/preview/", growth_panel.offer_preview),
    path("crm/report/", crm_views.report_view),
    path("stats/", stats_views.traffic_view),
    path("crm/campaigns/<int:pk>/report/", stats_views.campaign_view),
    path("crm/segments/", crm_views.segments_view),
    path("crm/segments/<str:key>/", crm_views.segments_view),
    path("crm/customer/<str:mobile>/", crm_customer.customer_view),
    path("<str:key>/", crud.list_view),
    path("<str:key>/add/", crud.edit_view),
    path("<str:key>/<int:pk>/", crud.edit_view),
    path("<str:key>/<int:pk>/delete/", crud.delete_view),
]
