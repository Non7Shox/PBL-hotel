# 🏨 Aurelio Hotel — Hotel Management System

A full-featured hotel management web application built with **Django 6** as a Project-Based Learning (PBL) exercise. The system covers the entire guest journey — from browsing rooms to booking and check-out — plus an internal staff dashboard for managing reservations, housekeeping and seasonal pricing.

---

## ✨ Features

### Guest-facing
| Feature | Description |
|---|---|
| **Room catalogue** | Browse rooms by floor, view photos, amenities, capacity and pricing |
| **3D room tours** | Interactive `.glb` 3D model viewer embedded on room detail pages |
| **Availability check** | Real-time date-based availability search |
| **Online booking** | Book a room with date picker, guest count and special requests |
| **Booking codes** | Every reservation gets a unique human-readable code (e.g. `AUR-X7K4P2`) |
| **My bookings** | Authenticated guests can view, track and cancel their bookings |
| **Guest reviews** | Leave a 1–5 star rating and comment after a stay (one review per room per guest) |
| **User accounts** | Register, log in, and view a personal profile with booking statistics |

### Staff dashboard (`/staff/`)
| Feature | Description |
|---|---|
| **Booking management** | Confirm, check-in, check-out, cancel or mark no-shows with enforced status transitions |
| **Desk booking** | Create walk-in bookings directly from the front-desk panel |
| **Housekeeping status** | Update room cleanliness state (Clean / Dirty / Inspected / Out of Service) |
| **Seasonal pricing** | Set per-room price overrides for date ranges; the system calculates the correct total automatically |
| **Staff roles** | Three roles with different permissions: **Manager**, **Receptionist**, **Housekeeping** |

### Admin (`/admin/`)
Full Django admin interface with inline seasonal rates, amenity management, and staff profile controls.

---

## 🗂 Project Structure

```
PBL-hotel/
├── pbl_hotel/          # Django project config (settings, root URLs)
├── accounts/           # Guest registration, login, staff login, profile
├── bookings/           # Booking model, forms, views, URL routing
├── rooms/              # Room, Floor, Amenity, SeasonalRate, Review models
├── staff/              # Staff profiles, roles, dashboard views
├── templates/          # Global HTML templates (Jinja-style Django templates)
│   ├── base.html
│   ├── accounts/
│   ├── bookings/
│   ├── rooms/
│   └── staff/
├── media/              # Uploaded images & 3D models (.glb)
├── manage.py
└── requirements.txt
```

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| Backend | [Django 6.1](https://docs.djangoproject.com/en/6.1/) |
| Database | SQLite (development) |
| Image handling | [Pillow 12](https://pillow.readthedocs.io/) |
| 3D models | `.glb` files served via `<model-viewer>` web component |
| Language | Russian (UI) / Python 3 |
| Timezone | `Asia/Tashkent` (UTC+5) |

Full dependency list: [`requirements.txt`](requirements.txt)

```
asgiref==3.12.1
Django==6.1.1
pillow==12.3.0
sqlparse==0.6.0
tzdata==2026.4
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- `pip` / `venv`

### 1. Clone the repository

```bash
git clone https://github.com/Non7Shox/PBL-hotel.git
cd PBL-hotel
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (admin + staff access)

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open your browser at **http://127.0.0.1:8000/**

---

## 🔑 URL Map

| URL | Description |
|---|---|
| `/` | Room listing (home page) |
| `/rooms/<id>/` | Room detail + 3D tour + reviews |
| `/bookings/` | Create a booking |
| `/bookings/my/` | Guest's booking list |
| `/bookings/<code>/` | Booking detail (public link) |
| `/accounts/login/` | Guest login |
| `/accounts/staff-login/` | Staff-only login |
| `/accounts/signup/` | Guest registration |
| `/accounts/profile/` | Guest profile page |
| `/staff/` | Staff dashboard |
| `/admin/` | Django admin panel |

---

## 👥 User Roles

| Role | Access |
|---|---|
| **Guest** | Browse rooms, book, cancel, review |
| **Receptionist** | Everything guests can do + manage bookings, desk booking |
| **Housekeeping** | Update housekeeping status on rooms |
| **Manager** | All of the above + seasonal rates, full staff dashboard |
| **Superuser** | Full admin access |

Staff accounts are created by assigning a `StaffProfile` to a user via the admin panel or `python manage.py shell`.

---

## 💡 Key Design Decisions

- **Booking codes** — Collision-safe random codes with format `AUR-XXXXXX` using a retry loop on `IntegrityError`.
- **Seasonal pricing** — `SeasonalRate` records override the base nightly price per date range; `Room.get_price_for_dates()` walks day-by-day to compute exact totals.
- **Status machine** — `Booking.STAFF_TRANSITIONS` maps allowed status changes, preventing illegal jumps (e.g. going from *Checked Out* back to *Pending*).
- **Role-based access** — `@staff_required` and `@role_required(*roles)` decorators protect staff views; the `staff_status` context processor injects role info into every template.
- **Overlap detection** — `Booking.overlapping()` class method uses half-open interval logic (`check_in < check_out_other AND check_out > check_in_other`) to reliably detect date conflicts.

---

## 🧪 Running Tests

```bash
python manage.py test
```

Each Django app includes a `tests.py` module covering model logic, views and form validation.

---

## 📁 Media Files

Uploaded images and 3D models are stored in the `media/` directory and served locally via Django's dev media handler when `DEBUG = True`.

> ⚠️ **Production note:** Do not serve media files through Django in production. Use a web server (nginx, Caddy) or a cloud storage bucket (S3, GCS) instead.

---

## 📧 Email Configuration

Email is currently printed to the **console** (development mode). To enable real delivery, update `pbl_hotel/settings.py`:

```python
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'HOST': 'smtp.example.com',
        'PORT': 587,
        'USERNAME': 'you@example.com',
        'PASSWORD': 'your-password',
        'USE_TLS': True,
    }
}
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to your fork: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

This project was created for educational purposes as part of a PBL (Project-Based Learning) course. Feel free to fork and adapt it for your own learning.
