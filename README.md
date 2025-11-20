# Restaurant Reservation System

A full-stack, reusable reservation and capacity-management system built for real restaurant operations.
This project serves as a standard base implementation that can be deployed and adapted for multiple restaurant clients with minimal rework.


The system provides an online reservation interface for customers and an operations dashboard for staff, handling scheduling, capacity logic, table assignments, and special service rules.


## Purpose of the System


The goal of this project is to create a reliable, reusable foundation for restaurant reservation workflows. It is designed to:

- Support real-world restaurant scheduling, seating, and capacity constraints.

- Allow staff to manage bookings, tables, and special service days.

- Provide configurable business logic without editing code.

- Serve as a standard base for future restaurant websites.

- This system can be adapted per client while keeping core logic stable and reusable.


## Features


### Customer Facing Features


Online Reservation Form

- Name, contact details, date, time, party size, seating preference
- Times filtered dynamically based on opening hours, last reservation time, minimum lead time, special opening days, and global reservation settings


- Capacity & Group Size Enforcement
- Indoor and outdoor capacity handled separately
- Maximum party sizes enforced per area
- Dwell time used to check overlapping reservations
- Medium, large, and very large groups detected automatically
- Limits on overlapping large or very large groups


Special Opening Days


- Override weekday rules for holidays or special events
- Custom open times, close times, and last reservation times
- “Bookings open from” field allowing future special events to be bookable
- Optional public message shown to customers


Reservation Status


- Automatically confirmed when booked online
- Full lifecycle: Pending, Confirmed, Seated, Completed, Cancelled, No-show



### Staff-Facing Features

Restaurant Settings (Admin)


- Set indoor and outdoor capacity
- Configure maximum party sizes
- Define group size thresholds (medium/large/very large)
- Limits for overlapping large and very large groups
- Global reservation open/close toggle with custom public message
- Editable dwell time (duration of reservation including cleanup)


Table Assignment


- Assign tables to reservations
- Only shows available tables based on dwell time overlap
- Cancelled/no show reservations do not block tables


Special Opening Day Management


- Create/edit special opening days in admin
- Control booking window, opening hours, and public messaging


Staff “Today’s Reservations” Dashboard


- Clear overview of today’s bookings sorted by time
- Status update buttons for quick actions
- Notes, table assignments, and party details
- Colour coded styling based on reservation status


Hourly Service Load Overview


- Internal 15-minute dwell aware timeblocks
- Aggregated into hourly peak loads
- Tracks indoor, outdoor, unassigned, and total guests
- Capacity based status: calm, busy, very busy
- Colour coded load levels
- Past hours automatically dimmed


## Technology Stack

Backend


- Python 3
- Django 4
- Django ORM (SQLite or PostgreSQL)
- Django Admin customisation
- Timezone aware scheduling and validation


Frontend

- Django Templates
- Bootstrap
- Vanilla JavaScript
- Flatpickr
- Custom JS for filtering, lead-time checks, and special day logic
- Custom CSS for staff dashboard and load overview


## Project Structure (High-Level)

reservations/
- admin.py - Admin customisations
- models.py - Reservation, Settings, OpeningHours, SpecialOpeningDay, Table
- forms.py - Reservation form and server-side validation
- views.py - Customer/staff views and capacity/load logic
- templates/reservations/

    - reservation_form.html
    - staff_today.html
      - static/css/staff_today.css
      - static/js/main.js


Key architectural notes:


- All configuration stored in a single RestaurantSettings row
- Special days override weekday rules
- Core validation is server side
- Dwell time is central to overlap detection
- Fully timezone aware


## Installation (Basic)

git clone <repo url>
cd <project>

python -m venv venv
activate the virtual environment

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

Admin panel: /admin/
Reservation form: your public reservation URL