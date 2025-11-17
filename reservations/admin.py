from datetime import date, timedelta
from django.contrib import admin
from .models import (Reservation,
                     Table,
                     OpeningHours,
                     RestaurantSettings,
                     SpecialOpeningDay
                     )


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "capacity")
    search_fields = ("number",)
    ordering = ("number",)


class ReservationDayFilter(admin.SimpleListFilter):
    title = "Day"
    parameter_name = "day"

    def lookups(self, request, model_admin):
        return [
            ("today", "Today"),
            ("tomorrow", "Tomorrow"),
            ("week", "Next 7 days"),
        ]

    def queryset(self, request, queryset):
        today = date.today()

        if self.value() == "today":
            return queryset.filter(date=today)

        if self.value() == "tomorrow":
            return queryset.filter(date=today + timedelta(days=1))

        if self.value() == "week":
            return queryset.filter(
                date__gte=today,
                date__lte=today + timedelta(days=7),
            )

        return queryset


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "time",
        "name",
        "party_size",
        "seating_preference_display",
        "tables_list",
        "status",
        "source"
    )
    list_filter = (
        "date",
        ReservationDayFilter,
        "seating_preference",
        "status",
        "source",
        )
    search_fields = ("name", "email", "phone", "notes",)
    filter_horizontal = ("tables",)

    ordering = ("date", "seating_preference", "time")

    date_hierarchy = "date"

    change_list_template = "admin/reservations/reservation/change_list.html"

    @admin.display(description="Seating")
    def seating_preference_display(self, obj: Reservation):
        """
        Show the human readable seating preference:
        'No preference', 'Indoor only', 'Outdoor if possible'
        """
        return obj.get_seating_preference_display()

    @admin.display(description="Tables")
    def tables_list(self, obj: Reservation):
        """
        Comma seperated list of assigned tables, e.g. "T 1, 4".
        Used as a quick floor map for staff
        """
        tables = obj.tables.all()
        if not tables:
            return "-"
        return ", ".join(t.number for t in tables)


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


@admin.register(SpecialOpeningDay)
class SpecialOpeningDayAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "is_open",
        "bookings_open_from",
        "public_message"
        )
    list_editable = (
        "is_open",
        "bookings_open_from",
        "public_message"
    )
    ordering = ("date",)


@admin.register(RestaurantSettings)
class RestaurantSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "indoor_capacity",
        "outdoor_capacity",
        "max_party_size_indoor",
        "max_party_size_outdoor",
        "medium_group_min_size",
        "medium_group_max_size",
        "large_group_min_size",
        "very_large_group_min_size",
        "max_large_groups_indoor",
        "max_very_large_groups_indoor",
        "max_large_groups_outdoor",
        "reservations_open",
        )

    fieldsets = (
        (None, {
            "fields": (
                "indoor_capacity",
                "outdoor_capacity",
                "max_party_size_indoor",
                "max_party_size_outdoor",
            )
        }),
        ("Group settings", {
            "fields": (
                "medium_group_min_size",
                "medium_group_max_size",
                "large_group_min_size",
                "very_large_group_min_size",
                "max_large_groups_indoor",
                "max_very_large_groups_indoor",
                "max_large_groups_outdoor",
            )
        }),
        ("Online reservation control", {  # NEW SECTION
            "fields": ("reservations_open", "closure_message"),
            "description": "Use this to temporarily "
            "close the reservation system.",
        }),
    )

    def has_add_permission(self, request):
        # Allow only one settings row
        if RestaurantSettings.objects.exists():
            return False
        return super().has_add_permission(request)
