from django.contrib import admin
from .models import Reservation, Table, OpeningHours


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


@admin.register(OpeningHours)
class OpeningHoursAdmin(admin.ModelAdmin):
    list_display = (
        "weekday",
        "get_weekday_display",
        "is_open",
        "open_time",
        "close_time",
        "last_res_time"
        )
    list_editable = (
        "is_open",
        "open_time",
        "close_time",
        "last_res_time"
        )
