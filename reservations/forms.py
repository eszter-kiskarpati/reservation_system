import datetime
from datetime import time, datetime as dt, timedelta
from django import forms
from django.utils import timezone

from .models import Reservation, OpeningHours, RestaurantSettings


# total indoor seats
DEFAULT_indoor_capacity = 42

# total outdoor seats
DEFAULT_outdoor_capacity = 54

# biggest party size cap INDOOR - default
MAX_PARTY_SIZE = 12

# biggest party size cap OUTDOOR
OUTDOOR_MAX_PARTY_SIZE = 8

# booking behaviour constants
DWELL_MINUTES = 90

LARGE_PARTY_THRESHOLD = 7
MAX_LARGE_GROUPS_SIMULTANEOUS = 2

VERY_LARGE_PARTY_THRESHOLD = 9

MEDIUM_PARTY_MIN = 5
MEDIUM_PARTY_MAX = 6

MIN_LEAD_MINUTES = 15

# seating preference identifiers
PREF_NO_PREF = Reservation.SeatingPreference.NO_PREFERENCE
PREF_INDOOR = Reservation.SeatingPreference.INDOOR_ONLY
PREF_OUTDOOR = Reservation.SeatingPreference.OUTDOOR_IF_POSSIBLE

# which prefs count as which "zone"
INDOOR_PREFERENCES = [PREF_INDOOR, PREF_NO_PREF]
OUTDOOR_PREFERENCES = [PREF_OUTDOOR]


# Helper to pull capacities from DB (RestaurantSettings)
def get_capacity_limits():
    """
    Return (indoor_capacity, outdoor_capacity) from RestaurantSettings
    if configured, otherwise fall back to the default constants.
    """
    settings = RestaurantSettings.objects.first()
    if settings:
        return settings.indoor_capacity, settings.outdoor_capacity
    return DEFAULT_indoor_capacity, DEFAULT_outdoor_capacity


# opening hours
OPEN_TIME = time(12, 0)
CLOSE_TIME = time(17, 0)
LAST_RES_TIME = time(16, 30)


def generate_time_choices(
        start: time,
        end: time,
        step_minutes: int = 15
        ):
    """
    Return list of ('HH:MM', 'HH:MM') choices between start and end inclusive
    """
    choices = []
    current = dt.combine(dt.today(), start)
    end_dt = dt.combine(dt.today(), end)

    while current <= end_dt:
        label = current.strftime("%H:%M")
        choices.append((label, label))
        current += timedelta(minutes=step_minutes)

    return choices


TIME_CHOICES = generate_time_choices(OPEN_TIME, LAST_RES_TIME, 15)


class ReservationForm(forms.ModelForm):
    # Override the model field with a ChoiceField for the form
    time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "required": True,
                }
                ),
        label="Time",
    )

    class Meta:
        model = Reservation
        fields = [
            "name",
            "email",
            "phone",
            "date",
            "time",
            "party_size",
            "seating_preference",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "required": True
                    }
                ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "required": True
                    }
                ),
            "date": forms.DateInput(
                attrs={
                    "type": "text",
                    "class": "form-control",
                    "id": "id_date",
                    "autocomplete": "off"
                    },
                format="%Y-%m-%d",
            ),
            "party_size": forms.NumberInput(
                attrs={"class": "form-control", "min": 1},
            ),
            "seating_preference": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Type here..."
                    ),
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Calculate closed weekdays from OpeningHours
        closed = OpeningHours.objects.filter(is_open=False).values_list(
            "weekday", flat=True
        )
        # Store as comma-seperated string in the data input
        self.fields["date"].widget.attrs["data-closed-weekdays"] = ",".join(
            str(d) for d in closed
        )

    def clean_time(self):
        """Convert 'HH:MM' string from the select into a time object"""
        value = self.cleaned_data["time"]
        if not value:
            raise forms.ValidationError("Please choose a time.")
        hour, minute = map(int, value.split(":"))
        return time(hour, minute)

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        time_value = cleaned_data.get("time")
        party_size = cleaned_data.get("party_size")
        seating_pref = cleaned_data.get("seating_preference")

        # fetch current indoor/outdoor capacities from admin settings
        indoor_capacity, outdoor_capacity = get_capacity_limits()

        # party size limits
        if party_size:
            # indoor/default cap
            if party_size > MAX_PARTY_SIZE:
                self.add_error(
                    "party_size",
                    f"Online reservations are "
                    f"limited to {MAX_PARTY_SIZE} guests. "
                    "For larger groups, please contact the "
                    "restaurant directly."
                )
            # outdoor specific cap
            if (
                seating_pref in OUTDOOR_PREFERENCES
                and party_size > OUTDOOR_MAX_PARTY_SIZE
            ):
                self.add_error(
                    "party_size",
                    f"For outdoor seating we accomodate up to "
                    f"{OUTDOOR_MAX_PARTY_SIZE} guests per booking. "
                    "For larger groups, please choose indoor seating or "
                    "contact the restaurant directly by phone."
                )

        # extra safety; email and phone num must be present
        if not cleaned_data.get("email"):
            self.add_error(
                "email",
                "Email is required so we can send you the confirmation."
                )
        if not cleaned_data.get("phone"):
            self.add_error(
                "phone",
                "Phone number is required so that we can contact you"
                " if necessary."
                )

        # no past dates
        if date and date < datetime.date.today():
            self.add_error("date", "You can't book for a past date")

        opening = None
        weekday_label = None

        # check opening hrs for that day
        if date:
            weekday = date.weekday()
            opening = OpeningHours.objects.filter(weekday=weekday).first()
            weekday_label = date.strftime("%A")

            if not opening or not opening.is_open:
                self.add_error(
                    "date",
                    f"We are closed on {weekday_label}s."
                    f" Please choose another date.",
                )

        # time within allowed range for that day
        if time_value and opening and opening.is_open:
            last_res = opening.effective_last_res_time()

            # Time too early OR too late?
            if (
                (opening.open_time and time_value < opening.open_time)
                or (last_res and time_value > last_res)
            ):
                self.add_error(
                    "time",
                    f"On {weekday_label}s we accept reservations between "
                    f"{opening.open_time.strftime('%H:%M')} and "
                    f"{last_res.strftime('%H:%M')}"
                )

        # same-day minimum lead time (15 mins)
        if date and time_value:
            today = timezone.localdate()
            if date == today:
                now = timezone.localtime()
                cutoff_time = (
                    now + timedelta(minutes=MIN_LEAD_MINUTES)
                    ).time()
                if time_value <= cutoff_time:
                    self.add_error(
                        "time",
                        f"For same-day reservations, please choose a time at "
                        f"least {MIN_LEAD_MINUTES} minutes from now."
                    )

        # capacity check with dwell time & large/very-large/medium limits
        if date and time_value and party_size:
            # decide which zone we are checking
            if seating_pref in OUTDOOR_PREFERENCES:
                zone = "outdoor"
                max_capacity = outdoor_capacity
                zone_prefs = OUTDOOR_PREFERENCES
            else:
                # treat NO_PREFERENCE as indoor for safety
                zone = "indoor"
                max_capacity = indoor_capacity
                zone_prefs = INDOOR_PREFERENCES

            requested_start = dt.combine(date, time_value)
            requested_end = requested_start + timedelta(minutes=DWELL_MINUTES)

            existing_reservations = Reservation.objects.filter(
                date=date,
                seating_preference__in=zone_prefs,
            ).exclude(status=Reservation.Status.CANCELLED)

            concurrent_guests = 0
            concurrent_large_groups = 0
            concurrent_very_large_groups = 0
            concurrent_medium_groups = 0

            for r in existing_reservations:
                existing_start = dt.combine(date, r.time)
                existing_end = existing_start + timedelta(
                    minutes=DWELL_MINUTES
                )

                # time intervals overlap?
                if (
                    (existing_start < requested_end)
                    and (requested_start < existing_end)
                ):
                    concurrent_guests += r.party_size

                    size = r.party_size
                    if size >= VERY_LARGE_PARTY_THRESHOLD:
                        # 9–12 guests: uses the single 12-seat zone
                        concurrent_very_large_groups += 1
                        concurrent_large_groups += 1  # also counts as large
                    elif size >= LARGE_PARTY_THRESHOLD:
                        # 7–8 guests
                        concurrent_large_groups += 1
                    elif MEDIUM_PARTY_MIN <= size <= MEDIUM_PARTY_MAX:
                        # 5–6 guests
                        concurrent_medium_groups += 1

            # 0) overall seat capacity (zone specific)
            if concurrent_guests + party_size > max_capacity:
                # Special case: user chose " no preference" and inddor is full
                # but outdoor might still have space -> suggest outdoor
                if zone == "indoor" and seating_pref == PREF_NO_PREF:
                    outdoor_requested_start = requested_start
                    outdoor_requested_end = requested_end

                    outdoor_existing = Reservation.objects.filter(
                        date=date,
                        seating_preference__in=OUTDOOR_PREFERENCES,
                    ).exclude(status=Reservation.Status.CANCELLED)

                    outdoor_overlap_total = 0
                    for r in outdoor_existing:
                        o_start = dt.combine(date, r.time)
                        o_end = o_start + timedelta(minutes=DWELL_MINUTES)
                        if (
                            o_start < outdoor_requested_end
                            and outdoor_requested_start < o_end
                        ):
                            outdoor_overlap_total += r.party_size

                    if (
                        outdoor_overlap_total
                        + party_size
                        <= outdoor_capacity
                    ):
                        self.add_error(
                            "seating_preference",
                            "We are fully booked indoors at the time, but "
                            "outdoor tables may be available if the weather "
                            "allows. Please choose 'Outdoor seating' or "
                            "contact the restaurant directly by phone."
                        )
                        return cleaned_data

                self.add_error(
                    "time",
                    "Sorry, we are fully booked at that time based on "
                    "current reservations. Please pick another time slot."
                )
                return cleaned_data

            new_size = party_size
            new_is_very_large = new_size >= VERY_LARGE_PARTY_THRESHOLD
            new_is_large = new_size >= LARGE_PARTY_THRESHOLD
            new_is_medium = MEDIUM_PARTY_MIN <= new_size <= MEDIUM_PARTY_MAX

            if zone == "indoor":
                # 1) only ONE very-large (9–12) group at a time
                if new_is_very_large and concurrent_very_large_groups >= 1:
                    self.add_error(
                        "time",
                        "We can only host one very "
                        "large group (9–12 guests) at "
                        "the same time. Please choose another time or contact "
                        "the restaurant directly."
                    )

                # 2) at most TWO large (7+) groups in total
                if new_is_large and (
                    concurrent_large_groups + 1 > MAX_LARGE_GROUPS_SIMULTANEOUS
                ):
                    self.add_error(
                        "time",
                        "We can only accommodate a limited "
                        "number of large groups "
                        "at the same time. Please choose another "
                        "time or contact "
                        "the restaurant directly by phone for "
                        "large party bookings."
                    )

                # 3) if we already have TWO large groups, allow only ONE medium
                effective_large_count = concurrent_large_groups
                if new_is_large:
                    effective_large_count += 1

                if effective_large_count >= 2:
                    effective_medium_count = concurrent_medium_groups
                    if new_is_medium:
                        effective_medium_count += 1

                    if effective_medium_count > 1:
                        self.add_error(
                            "time",
                            "We are already hosting multiple "
                            "large groups at that "
                            "time, so we cannot take additional 5–6 person "
                            "bookings. Please choose another time or "
                            "contact the restaurant directly."
                        )
            elif zone == "outdoor":
                # Outdoor specific group rules

                # at most TWO large (7-8) outdoor groups at once
                if new_is_large and (concurrent_large_groups + 1 > 2):
                    self.add_error(
                        "time",
                        "We are already hosting multiple large "
                        "outdoor groups at "
                        "that time. Please choose another time or "
                        "select indoor seating."
                    )

        return cleaned_data
