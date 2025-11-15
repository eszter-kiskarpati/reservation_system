import datetime
from django import forms

from .models import Reservation


# total indoor seats
MAX_CAPACITY_PER_SLOT = 42


class ReservationForm(forms.ModelForm):
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
            "time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"},
                format="%H:%M",
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

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")
        party_size = cleaned_data.get("party_size")

        # extra safety; email and phone bih must be present
        if not cleaned_data.get("email"):
            self.add_error(
                "email",
                "Email is required so we can send you the confirmation."
                )
        if not cleaned_data.get("phone"):
            self.add_error(
                "phone",
                "Phone number is required so that we can contact you"
                "if necessary."
                )

        if date and date < datetime.date.today():
            self.add_error("date", "You can't book for a past date")

        if date and time and party_size:
            existing = Reservation.objects.filter(
                date=date,
                time=time,
            ).exclude(status=Reservation.Status.CANCELLED)

            total_guests = sum(r.party_size for r in existing) + party_size
            if total_guests > MAX_CAPACITY_PER_SLOT:
                raise forms.ValidationError(
                    "Sorry, we are fully booked at that time."
                    "Please pick another time slot."
                )

        return cleaned_data
