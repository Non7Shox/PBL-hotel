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

### Environment variables

The defaults work for local development, so nothing needs to be set to run the project. For a production deployment, set:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `True` | Set to `False` in production |
| `DJANGO_SECRET_KEY` | local dev key | **Required** when `DJANGO_DEBUG=False` — the app refuses to start without it |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated list of host names the site is served on |
| `DJANGO_SITE_URL` | `http://127.0.0.1:8001` | Public address of the site, used in bot messages |
| `TELEGRAM_BOT_TOKEN` | empty (bot off) | Token from @BotFather, see [Telegram bot](#-telegram-bot) |
| `TELEGRAM_BOT_USERNAME` | empty | Bot username without `@`, used for the "notify me in Telegram" link |
| `TELEGRAM_STAFF_CHAT_ID` | empty | Reception chat that receives bookings and the morning summary |
| `TELEGRAM_DIGEST_HOUR` | `8` | Hour (Tashkent time) of the morning summary |

Instead of exporting variables you can put them in a `.env` file next to `manage.py` (one `KEY=VALUE` per line; see `.env.example`). The file is git-ignored; real environment variables take precedence.

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

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

Each Django app includes a `tests.py` module covering model logic, views and form validation:

- **rooms** — room pages, 3D tour embedding, seasonal pricing calculation
- **bookings** — booking codes, price totals, date/capacity validation, overlap detection, the availability API and the full online booking flow
- **accounts / staff** — guest and staff login, role-based access

Tests write uploaded files to a temporary folder, so running them never touches `media/`.

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

## 🤖 Telegram bot

One bot serves two audiences:

**Reception chat**
- Every new booking (site or desk) arrives as a card with **Confirm / Cancel** buttons, later **Check in / Check out**. Buttons follow the same status rules as the staff dashboard, notify the guest and update the card in place.
- Cancellations by guests and status changes made on the site are posted to the chat.
- A morning summary at `TELEGRAM_DIGEST_HOUR`: occupancy tonight, arrivals and departures, pending requests, month revenue. `/today` sends it on demand.
- Buttons only work inside the configured reception chat.

**Guests (private chat)**
- The booking page has a **Connect notifications** button. It opens the bot with a signed link, so knowing a booking code alone is not enough to subscribe.
- `/booking CODE email` links a booking manually, `/mybookings` lists linked bookings, `/stop` unsubscribes.
- `/rooms 12.11 15.11 2` lists free rooms for the dates with the total price.
- A reminder is sent the day before check-in.

### Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`.
3. Start the bot in a second terminal (it uses long polling, no public address needed):

   ```bash
   python manage.py runbot
   ```

4. Add the bot to the reception group, send `/chatid` there, put the number into `TELEGRAM_STAFF_CHAT_ID` and restart both `runserver` and `runbot`.

`runbot` sends the morning summary itself. To send it from a scheduler instead (or to test it), run `python manage.py bot_daily` (`--force` resends today's). Without a token the site works as before and simply skips Telegram.

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
