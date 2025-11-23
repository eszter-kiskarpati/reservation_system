import json
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from datetime import datetime as dt, timedelta

from django.views.decorators.http import require_POST
from django.contrib import messages
from .forms import (
    ReservationForm,
    MIN_LEAD_MINUTES,
    get_capacity_limits,
    get_dwell_minutes
    )
from .models import (
    Reservation,
    RestaurantSettings,
    SpecialOpeningDay,
    OpeningHours,
    Table
    )


SLOT_MINUTES = 15


def classify_area(reservation):
    """
    Decide whether a reservation counts as indoor, outdoor, or unassigned
    for capacity stats.

    Priority:
      1/ assigned_area if present
      2/ seating_preference as fall-back
    """
    # If reservation has explicit assigned_area (string or field),-
    # # trust that first
    area = getattr(reservation, "assigned_area", None)
    if area:
        area_str = str(area).upper()
        if area_str.startswith("INDOOR"):
            return "indoor"
        if area_str.startswith("OUTDOOR"):
            return "outdoor"

    # Fall back to seating preference
    pref = reservation.seating_preference

    if pref == Reservation.SeatingPreference.INDOOR_ONLY:
        return "indoor"

    # NO_PREFERENCE + OUTDOOR_IF_POSSIBLE count as unassigned
    return "unassigned"


def compute_level(guests, capacity):
    """
    Convert guests/capacity into semantic levels for CSS.
    """
    if not capacity:
        return "unknown"

    pct = (guests / capacity) * 100
    if pct < 50:
        return "calm"
    elif pct < 80:
        return "busy"
    else:
        return "very_busy"


def build_capacity_timeblocks(today, reservations, dwell_minutes,
                              indoor_capacity, outdoor_capacity):
    """
    Build raw 15 min time slots covering all active reservations.
    """
    active_statuses = {
        Reservation.Status.PENDING,
        Reservation.Status.CONFIRMED,
        Reservation.Status.SEATED,
        Reservation.Status.COMPLETED,
    }

    active = [r for r in reservations if r.status in active_statuses]
    if not active:
        return []

    dwell = timedelta(minutes=dwell_minutes)

    # Build (reservation, start_datetime, end_datetime)
    intervals = []
    for r in active:
        start = dt.combine(today, r.time)
        end = start + dwell
        intervals.append((r, start, end))

    earliest_start = min(start for _, start, _ in intervals)
    latest_end = max(end for _, _, end in intervals)

    # Floor to nearest 15-min slot
    start_minutes = earliest_start.hour * 60 + earliest_start.minute
    floored_minutes = (start_minutes // SLOT_MINUTES) * SLOT_MINUTES
    slot_start_dt = earliest_start.replace(
        hour=floored_minutes // 60,
        minute=floored_minutes % 60,
        second=0,
        microsecond=0,
    )

    blocks = []
    current = slot_start_dt
    total_capacity = indoor_capacity + outdoor_capacity

    while current < latest_end:
        slot_start = current
        slot_end = current + timedelta(minutes=SLOT_MINUTES)

        indoor = outdoor = unassigned = 0

        # accumulate overlapping reservations
        for r, res_start, res_end in intervals:
            if res_start < slot_end and slot_start < res_end:
                area = classify_area(r)
                if area == "indoor":
                    indoor += r.party_size
                elif area == "outdoor":
                    outdoor += r.party_size
                else:
                    unassigned += r.party_size

        total = indoor + outdoor + unassigned

        blocks.append({
            "start": slot_start,
            "end": slot_end,
            "indoor": indoor,
            "outdoor": outdoor,
            "unassigned": unassigned,
            "total": total,
            "indoor_level": compute_level(indoor, indoor_capacity),
            "outdoor_level": compute_level(outdoor, outdoor_capacity),
            "total_level": compute_level(total, total_capacity),
        })

        current = slot_end

    return blocks


def aggregate_hourly(timeblocks, indoor_capacity, outdoor_capacity, now=None):
    """
    Convert 15 min blocks into 1 hr summary blocks.
    We take the MAX load of each metric inside the hr.
    """
    if not timeblocks:
        return []

    hourly = {}
    total_capacity = indoor_capacity + outdoor_capacity

    for block in timeblocks:
        hour = block["start"].replace(minute=0, second=0, microsecond=0)

        if hour not in hourly:
            aware_start = timezone.make_aware(hour)
            aware_end = timezone.make_aware(hour + timedelta(hours=1))

            hourly[hour] = {
                "start": aware_start,
                "end": aware_end,
                "indoor": 0,
                "outdoor": 0,
                "unassigned": 0,
                "total": 0,
            }

        # Use max load inside the hr
        entry = hourly[hour]
        entry["indoor"] = max(entry["indoor"], block["indoor"])
        entry["outdoor"] = max(entry["outdoor"], block["outdoor"])
        entry["unassigned"] = max(entry["unassigned"], block["unassigned"])
        entry["total"] = max(entry["total"], block["total"])

    # Convert dict - sorted list
    hour_list = []
    for h, entry in sorted(hourly.items()):
        # Skip hrs with no load at all
        if entry["total"] == 0:
            continue

        entry["indoor_level"] = compute_level(entry["indoor"], indoor_capacity)
        entry["outdoor_level"] = compute_level(
            entry["outdoor"], outdoor_capacity
            )
        entry["total_level"] = compute_level(entry["total"], total_capacity)

        if now is not None:
            # mark past hrs to dim them in the UI
            entry["is_past"] = entry["end"] <= now
        else:
            entry["is_past"] = False

        hour_list.append(entry)

    return hour_list


def get_blocked_table_ids(reservation, dwell_minutes):
    """
    Return a set of table IDs that are not available for the
    given reservation's time window based on other reservations
    on the same date.

    We exclude this reservation itself and ignore CANCELLED / NO SHOW.
    """
    if not reservation.date or not reservation.time:
        return set()

    start = dt.combine(reservation.date, reservation.time)
    end = start + timedelta(minutes=dwell_minutes)

    other_reservations = (
        Reservation.objects
        .filter(date=reservation.date)
        .exclude(pk=reservation.pk)
        .exclude(
            status__in=[
                Reservation.Status.CANCELLED,
                Reservation.Status.NO_SHOW
            ]
        )
        .prefetch_related("tables")
    )

    blocked = set()

    for other in other_reservations:
        other_start = dt.combine(other.date, other.time)
        other_end = other_start + timedelta(minutes=dwell_minutes)

        # overlap?
        if other_start < end and start < other_end:
            blocked.update(other.tables.values_list("id", flat=True))

    return blocked


@staff_member_required
def staff_today(request):
    """
    Simple read only dashboard showing today's reservations.
    Only accessible to logged-in staff (admin users)
    """
    today = timezone.localdate()
    now = timezone.localtime()

    reservations_qs = (
        Reservation.objects
        .filter(date=today)
        .order_by("time")
        .prefetch_related("tables")
    )
    reservations = list(reservations_qs)

    indoor_capacity, outdoor_capacity = get_capacity_limits()
    dwell_minutes = get_dwell_minutes()

    # raw 15 min blocks
    quarter_blocks = build_capacity_timeblocks(
        today,
        list(reservations),
        dwell_minutes,
        indoor_capacity,
        outdoor_capacity,
    )

    # hourly aggregation
    hour_blocks = aggregate_hourly(
        quarter_blocks,
        indoor_capacity,
        outdoor_capacity,
        now=now,
    )

    active_tables = Table.objects.filter(is_active=True).order_by("number")

    # for each reservation, compute which tables are free for its timeslot
    for r in reservations:
        blocked_ids = get_blocked_table_ids(r, dwell_minutes)

        # Always keep already assigned tables visible even if blockd
        assigned_ids = set(r.tables.values_list("id", flat=True))

        r.available_tables = [
            t for t in active_tables
            if (t.id not in blocked_ids) or (t.id in assigned_ids)
        ]

    return render(
        request,
        "reservations/staff_today.html",
        {
            "today": today,
            "reservations": reservations,
            "hour_blocks": hour_blocks,
            "indoor_capacity": indoor_capacity,
            "outdoor_capacity": outdoor_capacity,
            "total_capacity": indoor_capacity + outdoor_capacity,
            "active_tables": active_tables,
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


@staff_member_required
@require_POST
def staff_update_tables(request, pk):
    """
    Staff only endpoint to update a reservation's table assignments
    from the 'today' dashboard.
    """
    reservation = get_object_or_404(Reservation, pk=pk)

    dwell_minutes = get_dwell_minutes()
    blocked_ids = get_blocked_table_ids(reservation, dwell_minutes)

    table_id = request.POST.get("table")

    # If nothing selected or empty string - clear assignment
    if not table_id:
        reservation.tables.clear()
        messages.success(
            request,
            f"Cleared table assignment for {reservation.name} at "
            f"{reservation.time}.",
        )
        return redirect("staff_today")

    try:
        table_id_int = int(table_id)
    except (TypeError, ValueError):
        messages.error(request, "Invalid table selection.")
        return redirect("staff_today")

    # Ensure table is actve
    table = get_object_or_404(Table, pk=table_id_int, is_active=True)

    # Conflict check
    if table.id in blocked_ids:
        messages.error(
            request,
            f"Can not assign table {table.number}: already in use "
            "at this time.",
        )
        return redirect("staff_today")

    # Assign single table
    reservation.tables.set([table])
    messages.success(
        request,
        f"Updated table for {reservation.name} at {reservation.time} to "
        f"{table.number}.",
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
