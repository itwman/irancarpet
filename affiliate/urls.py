from django.urls import path

from . import views

urlpatterns = [
    path("affiliate/", views.landing, name="affiliate"),
    path("my-account/affiliate/", views.dashboard),
    path("my-account/affiliate/products/", views.products),
    path("my-account/affiliate/link/", views.make_link),
]
