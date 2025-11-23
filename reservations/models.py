from django.db import models


class Table(models.Model):
    class Area(models.TextChoices):
        INDOOR = "INDOOR", "Indoor"
        OUTDOOR = "OUTDOOR", "Outdoor"

    number = models.CharField(
        max_length=20,
        unique=True,
        help_text="Table label, e.g. R1-T1, 4, Outside-3, etc."
    )
    capacity = models.PositiveIntegerField()

    area = models.CharField(
        max_length=10,
        choices=Area.choices,
        default=Area.INDOOR,
        help_text="Used for indoor/outdoor stats and assignment",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to temporarily remove this table from use."
    )

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


class SpecialOpeningDay(models.Model):
    """
    One off special opening day/s (e.g. Christmas) with it's own booking window
    """
    date = models.DateField(unique=True)

    is_open = models.BooleanField(
        default=True,
        help_text="Uncheck to treat this date as closed."
    )

    bookings_open_from = models.DateField(
        help_text="Date from which online "
        "reservations are allowed for this day"
    )

    public_message = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional short message shown on the reservation page"
    )

    open_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Optional: opening time for this special day. "
        "Leave blank to use normal weekday hours."
    )
    close_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Optional: closing time for this special day."
    )
    last_res_time = models.TimeField(
        blank=True,
        null=True,
        help_text="Optional: last time a new reservation can start. "
        "If blank, close_time will be used."
    )

    class Meta:
        verbose_name = "Special opening day"
        verbose_name_plural = "Special opening days"
        ordering = ["date"]

    def __str__(self):
        status = "open" if self.is_open else "closed"
        return f"{self.date} ({status}, online from {self.bookings_open_from})"


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        SEATED = "SEATED", "Seated"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No show"
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
        ),
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


class RestaurantSettings(models.Model):
    """
    Simple sungleton-style settings model so staff can adjust capacities
    without changing code.
    """
    indoor_capacity = models.PositiveIntegerField(
        default=42,
        help_text="Total indoor seats used for capacity calculations. "
        "The default number is 42"
    )
    outdoor_capacity = models.PositiveIntegerField(
        default=54,
        help_text="Total outdoor seats used for capacity calculations. "
        "The default number is 54"
    )

    # dwell time in minutes (includes clean up time)
    dwell_minutes = models.PositiveIntegerField(
        default=90,
        help_text=(
            "Average duration of a reservation (including clean up time), "
            "in minutes. Used for reservation capacity and load calculations. "
            "The default time is 90 minutes."
        ),
    )

    # Max party sizes for online bookings
    max_party_size_indoor = models.PositiveIntegerField(
        default=12,
        help_text="Maximum party size allowed for 'Indoor' & "
        "'No preference' online bookings. "
        "The default number is 12"
    )
    max_party_size_outdoor = models.PositiveIntegerField(
        default=8,
        help_text="Maximum party size allowed for 'Outdoor' online bookings. "
        "The default number is 8"
    )

    # very large/large/medium party settings
    medium_group_min_size = models.PositiveBigIntegerField(
        default=5,
        help_text="Minimum party size considered to be a 'medium group'. "
        "The default number is 5"
    )
    medium_group_max_size = models.PositiveBigIntegerField(
        default=6,
        help_text="Maximum party size considered to be a 'medium group'. "
        "The default number is 6"
    )
    large_group_min_size = models.PositiveBigIntegerField(
        default=7,
        help_text="Minimum party size considered to be a 'large group'. "
        "The default number is 7"
    )
    very_large_group_min_size = models.PositiveBigIntegerField(
        default=9,
        help_text="Minimum party size considered to be a 'very large group'. "
        "The default number is 9"
    )
    max_large_groups_indoor = models.PositiveBigIntegerField(
        default=2,
        help_text="Maximum number of overlapping large indoor groups. "
        "The default number is 2"
    )
    max_very_large_groups_indoor = models.PositiveBigIntegerField(
        default=1,
        help_text="Maximum number of overlapping very large indoor groups. "
        "The default number is 1"
    )
    max_large_groups_outdoor = models.PositiveBigIntegerField(
        default=2,
        help_text="Maximum number of overlapping very large indoor groups. "
        "The default number is 2"
    )

    reservations_open = models.BooleanField(
        default=True,
        help_text=(
            "Uncheck this to temporarily close the online reservation form."
            )
    )
    closure_message = models.TextField(
        blank=True,
        help_text=(
            "Message shown on the public reservation page when reservations "
            "are closed. Leave blank to use a default message."
            )
    )

    class Meta:
        verbose_name = "Restaurant settings"
        verbose_name_plural = "Restaurant settings"

    def __str__(self):
        return "Restaurant capacity settings"
