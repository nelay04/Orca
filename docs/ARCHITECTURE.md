# Architecture

How Orca is put together, and why.

- [Overview](#overview)
- [Tech stack](#tech-stack)
- [Why two databases](#why-two-databases)
- [Data model](#data-model)
- [Request flows](#request-flows)
- [Real-time messaging](#real-time-messaging)
- [Security model](#security-model)
- [Project layout](#project-layout)

---

## Overview

Orca is a mobile-first chat app. A user signs in with a one-time code sent to
their email, finds other people by scanning a QR code or opening a shared
profile link, sends a friend request, and once it is accepted the two can
exchange messages in real time.

There are two request paths through the application:

```
                    ┌────────────────────────────┐
   HTTP  ──────────▶│  Django views (views.py)   │──────▶  SQLite   (auth, OTP)
   page loads,      │  synchronous               │──────▶  MongoDB  (everything else)
   forms            └────────────────────────────┘

                    ┌────────────────────────────┐
   WebSocket ──────▶│  ChatConsumer              │──────▶  MongoDB  (message writes)
   live messages    │  async, Django Channels    │◀─────▶  Redis    (fan-out between clients)
                    └────────────────────────────┘
```

Both paths are served by a single ASGI process. Uvicorn routes HTTP to the
Django WSGI-style view stack and `/ws/...` to the Channels consumer, wired in
[`orca/asgi.py`](../orca/asgi.py) and [`orca2echo/routing.py`](../orca2echo/routing.py).

---

## Tech stack

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | HTML, CSS, vanilla JavaScript | No build step, no framework |
| Web framework | Django 5.2 LTS | Routing, templates, auth, forms |
| Real-time | Django Channels | WebSocket consumer for chat |
| ASGI server | Uvicorn | Serves HTTP and WebSocket together |
| Relational store | SQLite | Django auth tables and OTP records |
| Document store | MongoDB (PyMongo) | Profiles, friendships, messages |
| Cache / broker | Redis | Channels layer, signin rate limiting |
| Static files | WhiteNoise | Compressed, hashed static serving |
| Crypto | `cryptography.fernet` | Profile and conversation link tokens |

---

## Why two databases

This is the most unusual thing about the project, so it is worth stating
plainly: the split is historical, not principled.

Django's `contrib.auth` needs a relational database, and the project kept the
default SQLite. Everything the app itself models (profiles, friendships,
messages) was written against MongoDB. The result:

- **SQLite** holds `auth_user`, sessions, and the single Django model,
  `Otp` ([`orca2echo/models.py`](../orca2echo/models.py)).
- **MongoDB** holds five collections, accessed through thin hand-rolled classes
  in the same file, with query helpers in
  [`services/mongo_service.py`](../orca2echo/services/mongo_service.py).

The join key between the two is the **username**. A Django `User.username` is
the same string as `user_name` in the Mongo documents.

Consolidating onto one store is on the roadmap. See
[Known limitations](../README.md#known-limitations-and-roadmap).

### Username generation

Usernames are derived, not chosen. `generate_username()` takes the part of the
email before `@`, strips everything that is not a letter, and appends a
nanosecond-precision timestamp, giving something like `nelaykarmakar2026...`.
That keeps them unique without a uniqueness check, at the cost of being ugly.

---

## Data model

### SQLite

| Model | Fields | Notes |
|-------|--------|-------|
| `Otp` | `email`, `otp`, `created_at`, `attempts` | One row per pending sign-in. `created_at` drives expiry and the resend throttle; `attempts` caps guessing. Deleted on success or when burned. |
| `auth_user` | Django default | The password field holds the hashed current OTP, not a user-chosen password. |

### MongoDB collections

| Collection | Key fields | Purpose |
|------------|-----------|---------|
| `user_data` | `email`, `user_name`, `full_name`, `short_name`, `search_id`, `gender`, `dob`, `is_new_user` | Profile identity. Unique index on `email` and `user_name`. |
| `user_profile` | `user_name`, `profile_picture`, `about`, `qr_code` | Profile picture is a base64 string stored inline. |
| `friend_request_list` | `user_name_sender`, `user_name_receiver`, `is_active`, `is_accepted`, `is_declined`, `is_cancelled`, counters | One row per direction. Compound unique index on sender and receiver. |
| `friend_list` | `user_1`, `user_2`, `conversation_id` | Created once a request is accepted. |
| `conversations` | `conversation_id`, `sender`, `receiver`, `message`, `created_at` | One document per message. |

Indexes are created by `python manage.py init_mongo`, not at import time. See
[`db_connection.py`](../db_connection.py).

### How users find each other

A profile is addressed by the pair `(short_name, search_id)`:

- `short_name` is the user's initials, for example `NK`.
- `search_id` is a 20-digit number built from a timestamp plus random padding.

Neither is secret on its own, but both are encrypted into URL tokens before
being put in a link or QR code, so profile URLs are not enumerable by
incrementing an id.

### Conversation identity

When a friend request is accepted, a `friend_list` document is created with
`conversation_id = "<accepter>_<sender>"`. Message documents carry that same
string. Note the ordering depends on who accepted, so code must never assume
`"<a>_<b>"` over `"<b>_<a>"` — always resolve it through
`get_conversation_id_for_friendship()`.

---

## Request flows

### Sign-in

```
POST /signin  (email)
  │
  ├─ resend throttle: one OTP per email per minute
  ├─ IP throttle: 10 OTP requests per address per hour
  │
  ├─ superuser?  ──▶ render the OTP page, send nothing, create no OTP row
  │                  (identical response, so admins are not identifiable)
  │
  ├─ existing user?  ──▶ set their password to the new OTP
  └─ new user?       ──▶ create auth_user + user_data + user_profile
        │
        └─▶ email the OTP, store it in the Otp table, render otp.html

POST /verify-otp  (code)
  │
  ├─ no Otp row     ──▶ reject
  ├─ expired (10m)  ──▶ delete row, reject
  ├─ wrong code     ──▶ attempts += 1, burn the row at 5, reject
  └─ correct        ──▶ delete row, then
        ├─ is_new_user  ──▶ render signup.html to collect name/dob/gender
        └─ otherwise    ──▶ authenticate() + login(), redirect home
```

The OTP doubles as the Django password: `signin` calls `set_password(otp)` so
that `authenticate()` works normally at the end. This is why an OTP must be
single-use and short-lived.

### Friend request lifecycle

```
        add-friend                accept                    
  none ───────────▶ active ───────────────▶ accepted ──▶ friend_list row created
                      │                                    (enables chat)
                      ├── cancel  (by sender)   ──▶ inactive
                      └── decline (by receiver) ──▶ inactive
```

Re-sending after a cancel or decline reactivates the same row and increments
its counter rather than inserting a new one, which is what the compound unique
index enforces.

---

## Real-time messaging

The client opens `ws://<host>/ws/chat/<encrypted_conversation_id>/`.
[`ChatConsumer`](../orca2echo/consumers.py):

1. Rejects the connection if the session is not authenticated.
2. Derives a Channels group name from the token, and joins it.
3. On each inbound frame, resolves the real `conversation_id` from the
   database, writes the message to MongoDB, then broadcasts to the group.
4. Redis carries the broadcast, so both participants receive it even when they
   are served by different worker processes.

Blocking database work is wrapped in `sync_to_async` so the event loop is not
stalled.

The sender's own message is rendered optimistically in the browser before the
round trip, and the echoed copy is ignored client-side to avoid duplicates.

### Known weak point

`created_at` is generated by the browser and trusted by the server. Clock skew
or a crafted frame can misorder history. Message timestamps should be produced
server-side; this is listed in the roadmap.

---

## Security model

| Concern | Approach |
|---------|----------|
| Authentication | Email OTP only. Generated with `secrets`, 10 minute expiry, 5 attempt cap, throttled per email and per IP. |
| Session | Standard Django sessions. `HttpOnly` always; `Secure` when `DEBUG=False`. |
| Chat authorization | Membership is resolved from `friend_list` in the database. The URL token is not treated as proof of access. |
| Link tampering | Profile and conversation ids travel as Fernet tokens (AES-CBC + HMAC), so they cannot be forged or enumerated. |
| XSS | Django autoescaping for server-rendered history; the WebSocket client builds nodes with `textContent`, never `innerHTML`. |
| CSRF | Django middleware. `CSRF_TRUSTED_ORIGINS` comes from `APP_URL`. |
| Host header | `ALLOWED_HOSTS` from the environment, never `*`. |
| Admin | Superusers cannot sign in via OTP at all; they use `/admin/`. |

### Token keys

`encrypt_token` / `decrypt_token` in
[`services/auth_service.py`](../orca2echo/services/auth_service.py) use
`FERNET_KEY` when set, otherwise a key derived from `SECRET_KEY`. Setting
`FERNET_KEY` explicitly is recommended so that rotating `SECRET_KEY` does not
invalidate every profile link that has ever been shared.

Fernet output is deliberately non-deterministic. Nothing may cache on it; the
QR filename cache is keyed on `user_name` for exactly this reason.

---

## Project layout

```
orca/                       Django project package
├── settings.py             Env-driven config, channels, cache, security headers
├── asgi.py                 ASGI entry point, HTTP + WebSocket routing
└── wsgi.py                 WSGI entry point (HTTP only, no chat)

orca2echo/                  The application
├── views.py                HTTP handlers, IP rate limiting
├── consumers.py            WebSocket chat consumer
├── routing.py              WebSocket URL patterns
├── models.py               Otp (Django ORM) + MongoDB document classes
├── forms.py                Signin and signup validation
├── tests.py                Auth, authorization, token and form tests
├── admin.py                Django admin registration
├── management/commands/
│   ├── runasgi.py          Starts Uvicorn, reads HOST/PORT/DEBUG
│   └── init_mongo.py       Creates MongoDB indexes
├── services/
│   ├── auth_service.py     OTP generation, email, tokens, QR codes
│   ├── model_service.py    OTP lifecycle against the Django ORM
│   └── mongo_service.py    PyMongo query helpers
├── static/                 CSS, JS, images, icons, PWA manifest
├── templates/              Django templates
└── media/                  Base64 placeholder avatars

db_connection.py            MongoClient + ensure_indexes()
scripts/                    One-off developer scripts
docs/                       This documentation
```

### Where to start reading

- Sign-in and OTP: `views.py::signin`, `views.py::verify_otp`,
  `services/model_service.py`
- Chat: `templates/chat.html` (client), `consumers.py` (server)
- Profile links and QR: `services/auth_service.py::get_profile_share_context`
- Friend requests: `views.py::add_friend`, `views.py::response`
