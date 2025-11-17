from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ReservationForm, MIN_LEAD_MINUTES
from .models import Reservation, RestaurantSettings


@staff_member_required
def staff_today(request):
    """
    Simple read only dashboard showing today's reservations.
    Only accessible to logged-in staff (admin users)
    """
    today = timezone.localdate()

    reservations = (
        Reservation.objects
        .filter(date=today)
        .order_by("time")
    )

    return render(
        request,
        "reservations/staff_today.html",
        {
            "today": today,
            "reservations": reservations,
        },
    )


def create_reservation(request):
    settings_obj = RestaurantSettings.objects.first()
    reservations_open = True
    closure_message = ""

    if settings_obj:
        reservations_open = settings_obj.reservations_open
        closure_message = settings_obj.closure_message or (
            "Online reservations are temporarily unavailable. "
            "Please contact the restaurant directly by phone."
        )

    if request.method == "POST":
        form = ReservationForm(request.POST)

        if not reservations_open:
            # Block creation, show a non-field error
            form.add_error(None, closure_message)
        elif form.is_valid():
            # status defaults to PENDING
            reservation = form.save(commit=False)

            # Automatically confirm all online reservations
            reservation.status = Reservation.Status.CONFIRMED

            reservation.source = "ONLINE"

            reservation.save()
            form.save_m2m()

            return redirect("reservation_success", pk=reservation.pk)
    else:
        form = ReservationForm()

    return render(
        request,
        "reservations/reservation_form.html",
        {
            "form": form,
            "MIN_LEAD_MINUTES": MIN_LEAD_MINUTES,
            "reservations_open": reservations_open,
            "closure_message": closure_message,
            }
        )


def reservation_success(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(
        request,
        "reservations/reservation_success.html",
        {"reservation": reservation},
    )
