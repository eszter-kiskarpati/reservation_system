import datetime
from datetime import time, datetime as dt, timedelta
from django import forms

from .models import Reservation


# total indoor seats
MAX_CAPACITY_PER_SLOT = 42

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
        widget=forms.Select(attrs={"class": "form-select"}),
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
                attrs={"class": "form-control", "required": True}
                ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "required": True}
                ),
            "date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"},
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

    def clean_time(self):
        """Convert 'HH:MM' string from the select into a time object"""
        value = self.cleaned_data["time"]
        hour, minute = map(int, value.split(":"))
        return time(hour, minute)

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        time_value = cleaned_data.get("time")
        party_size = cleaned_data.get("party_size")

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

        # block Thursdays (weekday() == 3 -> Mon=0...)
        if date and date.weekday() == 3:
            self.add_error(
                "date",
                "We are closed for food service on Thursdays."
                " Please choose another day."
            )

        # time must be within opening hrs
        if time_value:
            if time_value < OPEN_TIME or time_value > LAST_RES_TIME:
                self.add_error(
                    "time",
                    f"We accept online reservations between "
                    f"{OPEN_TIME.strftime('%H:%M')} and "
                    f"{LAST_RES_TIME.strftime('%H:%M')}"
                )

        # capacity check
        if date and time_value and party_size:
            existing = Reservation.objects.filter(
                date=date,
                time=time_value,
            ).exclude(status=Reservation.Status.CANCELLED)

            total_guests = sum(r.party_size for r in existing) + party_size
            if total_guests > MAX_CAPACITY_PER_SLOT:
                raise forms.ValidationError(
                    "Sorry, we are fully booked at that time."
                    " Please pick another time slot."
                )

        return cleaned_data
