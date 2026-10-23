from django.urls import path

from . import views

urlpatterns = [
    path("affiliate/", views.landing, name="affiliate"),
    path("my-account/affiliate/", views.dashboard),
    path("my-account/affiliate/carpets/", views.carpets),
    path("my-account/affiliate/links/", views.links),
    path("my-account/affiliate/earnings/", views.earnings),
    path("my-account/affiliate/payouts/", views.payouts),
    path("my-account/affiliate/guide/", views.guide),
    path("my-account/affiliate/story/<int:pk>/", views.story),
    path("my-account/affiliate/products/", views.products),
    path("my-account/affiliate/link/", views.make_link),
]
