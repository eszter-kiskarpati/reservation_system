import json
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404

from django.views.decorators.http import require_POST
from django.contrib import messages

from .forms import ReservationForm, MIN_LEAD_MINUTES
from .models import (
    Reservation,
    RestaurantSettings,
    SpecialOpeningDay,
    OpeningHours
    )


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


@staff_member_required
@require_POST
def staff_update_status(request, pk):
    """
    staff only endpoint to quickly update a reservation's status
    from the 'today' dashboard
    """
    reservation = get_object_or_404(Reservation, pk=pk)

    new_status = request.POST.get("status")

    allowed_statuses = {
        Reservation.Status.CONFIRMED,
        Reservation.Status.SEATED,
        Reservation.Status.COMPLETED,
        Reservation.Status.NO_SHOW,
        Reservation.Status.CANCELLED,
    }

    if new_status not in allowed_statuses:
        messages.error(request, "Invalid status selected.")
        return redirect("staff_today")

    reservation.status = new_status
    reservation.save(update_fields=["status"])

    messages.success(
        request,
        f"Updated status for {reservation.name} at {reservation.time} to "
        f"{reservation.get_status_display()}"
    )
    return redirect("staff_today")


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

    # Check if there are any special days that are bookable right now
    today = timezone.localdate()

    special_qs = SpecialOpeningDay.objects.filter(
        date__gte=today,
        bookings_open_from__lte=today,
        is_open=True,
    )

    has_bookable_special_days = special_qs.exists()
    form_enabled = reservations_open or has_bookable_special_days

    # list of special open dates as YYYY, MM, DD...
    special_open_dates_str = ",".join(
        d.isoformat() for d in special_qs.values_list("date", flat=True)
    )

    # collect a public message for currently bookable special days
    special_message = ""
    if has_bookable_special_days:
        for msg in special_qs.values_list("public_message", flat=True):
            if msg:
                special_message = msg
                break

    if request.method == "POST":
        form = ReservationForm(request.POST)

        if not form_enabled:
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

    # weekday hours from OpeningHours (only open days)
    weekday_hours = {}
    for oh in OpeningHours.objects.filter(is_open=True):
        # last_res_time may be null - fall back to close_time
        last = oh.last_res_time or oh.close_time
        if oh.open_time and last:
            weekday_hours[oh.weekday] = {
                "open": oh.open_time.strftime("%H:%M"),
                "last": last.strftime("%H:%M")
            }

    # special day hrs for currently bookable spec days
    special_day_hours = {}
    for sd in special_qs:
        if sd.open_time and (sd.last_res_time or sd.close_time):
            special_day_hours[sd.date.isoformat()] = {
                "open": sd.open_time.strftime("%H:%M"),
                "last": (sd.last_res_time or sd.close_time).strftime("%H:%M"),
            }

    return render(
        request,
        "reservations/reservation_form.html",
        {
            "form": form,
            "MIN_LEAD_MINUTES": MIN_LEAD_MINUTES,
            "reservations_open": reservations_open,
            "form_enabled": form_enabled,
            "special_open_dates": special_open_dates_str,
            "closure_message": closure_message,
            "special_message": special_message,
            # JSON for JS
            "weekday_hours_json": json.dumps(weekday_hours),
            "special_day_hours_json": json.dumps(special_day_hours),
            }
        )


def reservation_success(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    return render(
        request,
        "reservations/reservation_success.html",
        {"reservation": reservation},
    )


def privacy_policy(request):
    return render(request, "privacy_policy.html")
