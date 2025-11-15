from django.urls import path
from . import views

urlpatterns = [
    path("new/", views.create_reservation, name="create_reservation"),
    path(
        "success/<int:pk>/",
        views.reservation_success,
        name="reservation_success"
        ),
]