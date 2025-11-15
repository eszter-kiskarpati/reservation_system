from django.db import models


class Table(models.Model):
    number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Table label, e.g. R1-T1, 4, Outside-3, etc."
    )
    capacity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.number} (seats {self.capacity})"


class OpeningHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    weekday = models.IntegerField(choices=Weekday.choices, unique=True)
    is_open = models.BooleanField(default=True)

    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    last_res_time = models.TimeField(
        null=True,
        blank=True,
        help_text=(
            "Last time a new reservation can start. "
            "If empty, close_time will be used.",
        )
    )

    class Meta:
        verbose_name = "Opening hour"
        verbose_name_plural = "Opening hours"
        ordering = ["weekday"]

    def __str__(self):
        label = self.get_weekday_display()
        if not self.is_open:
            return f"{label} - closed"
        return f"{label}: {self.open_time}-{self.close_time}"

    def effective_last_res_time(self):
        return self.last_res_time or self.close_time


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    class SeatingPreference(models.TextChoices):
        NO_PREFERENCE = "NO_PREF", "No preference"
        INDOOR_ONLY = "INDOOR", "Indoor only"
        OUTDOOR_IF_POSSIBLE = "OUTDOOR_IF_POSSIBLE", "Outdoor if possible"

    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    date = models.DateField()
    time = models.TimeField()
    party_size = models.PositiveIntegerField()

    seating_preference = models.CharField(
        max_length=25,
        choices=SeatingPreference.choices,
        default=SeatingPreference.NO_PREFERENCE,
    )

    notes = models.TextField(
        blank=True,
        help_text=(
            "Special requests: highchairs, low table, allergies, buggy, etc."
        )
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # staff can assign one or more specific tables from a fixed list
    tables = models.ManyToManyField(
        Table,
        blank=True,
        related_name="reservations",
        help_text=(
            "Internal use: assign one or more tables to this reservation."
        )
    )

    source = models.CharField(
        max_length=20,
        default="ONLINE",  # or PHONE, WALK_IN
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "time"]

    def __str__(self):
        return f"{self.name} - {self.date} {self.time} ({self.party_size})"
