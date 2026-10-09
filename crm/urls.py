from django.urls import path

from . import carts, club, contact

urlpatterns = [
    path("my-account/club/", club.club, name="club"),
    path("cart/restore/<str:token>/", carts.restore_view),
    path("contact/send/", contact.send),
]
