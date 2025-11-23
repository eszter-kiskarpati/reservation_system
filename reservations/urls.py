from django.urls import path
from . import views

urlpatterns = [
    path("new/", views.create_reservation, name="create_reservation"),
    path(
        "success/<int:pk>/",
        views.reservation_success,
        name="reservation_success"
        ),
    path("staff/today/", views.staff_today, name="staff_today"),
    path(
        "staff/reservation/<int:pk>/status/",
        views.staff_update_status,
        name="staff_update_status",
    ),
    path(
        "staff/reservation/<int:pk>/tables/",
        views.staff_update_tables,
        name="staff_update_tables",
    ),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
]
