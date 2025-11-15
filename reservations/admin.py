from django.contrib import admin
from .models import Reservation, Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "capacity")
    search_fields = ("number",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "time",
        "name",
        "party_size",
        "status",
        "source"
    )
    list_filter = ("date", "status", "source")
    search_fields = ("name", "email", "phone")
    filter_horizontal = ("tables",)
