from django.urls import path

from . import carts, club

urlpatterns = [
    path("my-account/club/", club.club, name="club"),
    path("cart/restore/<str:token>/", carts.restore_view),
]
