from django.shortcuts import render, redirect, get_list_or_404

from .forms import ReservationForm
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
            {"form": form}
            )


def reservation_success(request, pk):
    reservation = get_list_or_404(Reservation, pk=pk)
    return render(
        request,
        "reservations/reservation_success.html",
        {"reservation": reservation},
    )
