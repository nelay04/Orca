# Architecture

How Orca is put together, and why.

- [Overview](#overview)
- [Tech stack](#tech-stack)
- [One database](#one-database)
- [Data model](#data-model)
- [Request flows](#request-flows)
- [Real-time messaging](#real-time-messaging)
- [Security model](#security-model)
- [Project layout](#project-layout)

---

## Overview

Orca is a mobile-first chat app that also lays out for tablet and desktop. A
user signs in with a one-time code sent to their email, finds other people by
scanning a QR code or opening a shared profile link, sends a friend request,
and once it is accepted the two can exchange messages in real time.

There are two request paths through the application:

```
                    ┌────────────────────────────┐
   HTTP  ──────────▶│  Django views (views.py)   │──────▶  PostgreSQL  (everything)
   page loads,      │  synchronous               │
   forms            └────────────────────────────┘

                    ┌────────────────────────────┐
   WebSocket ──────▶│  ChatConsumer              │──────▶  PostgreSQL  (message writes)
   live messages    │  async, Django Channels    │◀─────▶  Redis       (fan-out between clients)
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
| Database | PostgreSQL (psycopg 3) | Auth, sessions, OTPs, profiles, friendships, messages |
| Cache / broker | Redis | Channels layer, signin rate limiting |
| Static files | WhiteNoise | Compressed, hashed static serving |
| Crypto | `cryptography.fernet` | Profile and conversation link tokens |

---

## One database

Everything lives in PostgreSQL, through the Django ORM. There is no second
store and no SQLite fallback: [`orca/settings.py`](../orca/settings.py) raises
`ImproperlyConfigured` when `DATABASE_URL` is missing rather than quietly
starting against an empty local file.

This was not always so. Django auth and the `Otp` model used to live in SQLite
while profiles, friendships and messages lived in MongoDB, joined only by the
username string. That split was historical rather than principled, and it cost
real things: the admin could see only one model, nothing enforced that a Mongo
document referred to a user that existed, and every list page did two point
lookups per friend.

Query helpers live in
[`services/data_service.py`](../orca2echo/services/data_service.py). Views and
the consumer go through it rather than building querysets inline, so the access
patterns that matter for authorization stay in one place.

### Username generation

Usernames are derived, not chosen. `generate_username()` takes the part of the
email before `@`, strips everything that is not a letter, and appends a
nanosecond-precision timestamp, giving something like `nelaykarmakar2026...`.
That keeps them unique without a uniqueness check, at the cost of being ugly.

---

## Data model

All models are in [`orca2echo/models.py`](../orca2echo/models.py) and every one
of them is registered in the admin.

| Model | Key fields | Purpose |
|-------|-----------|---------|
| `auth_user` | Django default | The password field holds the hashed current OTP, not a user-chosen password. |
| `Otp` | `email`, `otp`, `created_at`, `attempts` | One row per pending sign-in. `created_at` drives expiry and the resend throttle; `attempts` caps guessing. Deleted on success or when burned. |
| `Profile` | `user` (one-to-one), `full_name`, `short_name`, `search_id`, `gender`, `dob`, `about`, `profile_picture`, `qr_code`, `is_new_user` | Everything about a user beyond their auth row. `search_id` is unique; `(short_name, search_id)` is indexed for the share-link lookup. The picture is a base64 string stored inline. |
| `FriendRequest` | `sender`, `receiver`, `is_active`, `is_accepted`, `is_declined`, `is_cancelled`, counters | One row per direction, unique on the pair. |
| `Friendship` | `public_id`, `user_1`, `user_2` | Created once a request is accepted. Also the conversation. |
| `Message` | `friendship`, `sender`, `receiver`, `message`, `created_at` | One row per message, indexed on `(friendship, created_at)` and ordered by `created_at`. `message` is stored Fernet-encrypted (at rest) and decrypted on read. |

There is no separate email or username column on `Profile`: `user.email` and
`user.username` are the only copy of each.

### How users find each other

A profile is addressed by the pair `(short_name, search_id)`:

- `short_name` is the user's initials, for example `NK`.
- `search_id` is a 20-digit number built from a timestamp plus random padding.

Neither is secret on its own, but both are encrypted into URL tokens before
being put in a link or QR code, so profile URLs are not enumerable by
incrementing an id.

### Conversation identity

A conversation is a `Friendship` row. Messages point at it by foreign key, and
chat URLs carry its `public_id`, a random UUID, inside a Fernet token.

It used to be the string `"<accepter>_<sender>"`, whose ordering depended on
who accepted the request, so every caller had to resolve it rather than build
it. A UUID has no ordering to get wrong and reveals no usernames.

The `public_id` is not a secret. It names the Channels group, and it is in the
page source of the chat screen. Access is decided by
`resolve_friendship()`, which returns the other participant only when the
caller is one of the two members.

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

The auth_user and Profile rows for a new user are written in one transaction.
A user without a profile could never finish signup, and would hold the email
address against a second attempt.

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
its counter rather than inserting a new one, which is what the unique
constraint on `(sender, receiver)` enforces.

---

## Real-time messaging

The client opens `ws://<host>/ws/chat/<friendship public_id>/`.
[`ChatConsumer`](../orca2echo/consumers.py):

1. Rejects the connection if the session is not authenticated.
2. Uses the `public_id` as the Channels group name, and joins it.
3. On each inbound frame, looks up the friendship between the sender and the
   named recipient. No friendship means no write and no broadcast, so a client
   sitting in a group it does not belong to cannot inject messages.
4. Writes the message, then broadcasts it with the timestamp the database
   assigned.
5. Redis carries the broadcast, so both participants receive it even when they
   are served by different worker processes.

Blocking database work is wrapped in `sync_to_async` so the event loop is not
stalled.

The sender's own message is rendered optimistically in the browser with a
provisional local time. When the echo of that message arrives, the client
replaces the timestamp with the server's, so both participants and the reloaded
history all show the same one.

### Known weak point

`connect()` admits any authenticated user to the group named by the URL. Per
message authorization still holds, so a non-member can neither write nor cause
a broadcast, but they would see traffic in a group whose `public_id` they had
somehow learned. Checking membership at connect time is the fix.

---

## Security model

| Concern | Approach |
|---------|----------|
| Authentication | Email OTP only. Generated with `secrets`, 10 minute expiry, 5 attempt cap, throttled per email and per IP. |
| Session | Standard Django sessions. `HttpOnly` always; `Secure` when `DEBUG=False`. |
| Chat authorization | Membership is resolved from `Friendship` in the database. The URL token is not treated as proof of access. |
| Link tampering | Profile and conversation ids travel as Fernet tokens (AES-CBC + HMAC), so they cannot be forged or enumerated. |
| Message storage | Bodies are encrypted at rest with the same Fernet before being written, so a stolen database holds only ciphertext. This is encryption at rest, not end to end: the server holds the key and decrypts on read for display. |
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

Message bodies are encrypted with the same key via `encrypt_message` /
`decrypt_message`. Unlike the ephemeral URL tokens, this ciphertext is stored,
so rotating the key makes existing history unreadable. If you must rotate,
re-encrypt the `Message` rows under the new key, or move to `MultiFernet` with
the old key retained for decryption.

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
├── models.py               Otp, Profile, FriendRequest, Friendship, Message
├── forms.py                Signin and signup validation
├── tests.py                Auth, authorization, friendship and form tests
├── admin.py                Django admin registration for every model
├── management/commands/
│   └── runasgi.py          Starts Uvicorn, reads HOST/PORT/DEBUG
├── services/
│   ├── auth_service.py     OTP generation, email, tokens, QR codes
│   ├── model_service.py    OTP lifecycle
│   └── data_service.py     Query helpers for the app's own tables
├── static/                 CSS, JS, images, icons, PWA manifest
├── templates/              Django templates
└── media/                  Base64 placeholder avatars

scripts/                    One-off developer scripts
docs/                       This documentation
```

### Where to start reading

- Sign-in and OTP: `views.py::signin`, `views.py::verify_otp`,
  `services/model_service.py`
- Chat: `templates/chat.html` (client), `consumers.py` (server)
- Profile links and QR: `services/auth_service.py::get_profile_share_context`
- Friend requests: `views.py::add_friend`, `views.py::response`
- Queries: `services/data_service.py`, `models.py`
