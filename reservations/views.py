from django.shortcuts import render, redirect, get_object_or_404

from .forms import ReservationForm, MIN_LEAD_MINUTES
from .models import Reservation


def create_reservation(request):
    if request.method == "POST":
        form = ReservationForm(request.POST)
        if form.is_valid():
            # status defaults to PENDING
            reservation = form.save()
            return redirect("reservation_success", pk=reservation.pk)
    else:
        form = ReservationForm()
    return render(
        request,
        "reservations/reservation_form.html",
        {
            "form": form,
            "MIN_LEAD_MINUTES": MIN_LEAD_MINUTES,
            }
        )


def reservation_success(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(
        request,
        "reservations/reservation_success.html",
        {"reservation": reservation},
    )
