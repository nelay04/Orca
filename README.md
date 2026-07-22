# Orca (orca2echo)

<p align="center">
  A real-time web-based chat application built with <strong>Django</strong>, <strong>Django Channels</strong>, <strong>Redis</strong>, and <strong>MongoDB</strong>.
</p>

<p align="center">
  <img src="orca2echo/static/images/home-screen.png" alt="Home Screen" width="25%" />
</p>

---

## Features

| Feature | Description |
|---|---|
| **Real-time Messaging** | Instant messaging powered by WebSockets via Django Channels and Redis |
| **Friend System** | Send, accept, decline, and cancel friend requests effortlessly |
| **OTP Authentication** | Passwordless login using single-use codes sent by email, with expiry and attempt limits |
| **Profile Sharing** | Generate and share your profile using automatically generated QR codes and encrypted links |
| **Dark / Light Mode** | Toggle between responsive light and dark themes |
| **Secure Link Encryption** | Profile and conversation links are authenticated with `Fernet` (AES-CBC + HMAC) |
| **Non-blocking Architecture** | Asynchronous WebSocket consumer with synchronous database work offloaded |

---

## Screenshots

### Live Chat Room

<p align="center">
  <img src="orca2echo/static/images/chat-room.png" alt="Chat Room" width="25%" />
</p>

Real-time chat interface featuring instant message delivery, timestamps, and active status.

---

### Add Friends and Share Profile

<p align="center">
  <img src="orca2echo/static/images/share-profile.png" alt="Share Profile" width="25%" />
</p>

Easily connect with others using encrypted QR codes or direct profile links.

---

### Friend List and Requests

<p align="center">
  <img src="orca2echo/static/images/friend-list.png" alt="Friend List" width="25%" />
</p>

Manage your connections, view active friends, and handle incoming requests on the fly.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, Django, Django Channels (WebSockets) |
| Relational store | SQLite (Django auth and OTP records) |
| Document store | MongoDB (profiles, friendships, messages) |
| In-Memory Store | Redis (Channels layer and rate limiting) |
| Security | `cryptography.fernet` (authenticated symmetric encryption) |

---

## Folder Structure

```
.
├── orca/                    # Django core project folder
│   ├── settings.py          # Application settings (logging, channels, DB)
│   ├── asgi.py              # ASGI config for Channels
│   └── wsgi.py              # WSGI config for HTTP
├── orca2echo/               # Main application
│   ├── forms.py             # Django forms for validation (Signin, Signup)
│   ├── models.py            # MongoDB document models and the Django OTP model
│   ├── views.py             # HTTP route handlers
│   ├── consumers.py         # WebSocket chat consumer
│   ├── routing.py           # WebSocket routing configuration
│   ├── tests.py             # Auth, authorization, and token tests
│   ├── management/          # Custom Django management commands
│   │   └── commands/
│   │       ├── runasgi.py   # `python manage.py runasgi` starts Uvicorn
│   │       └── init_mongo.py# `python manage.py init_mongo` creates indexes
│   ├── services/            # Extracted business logic
│   │   ├── auth_service.py  # Encryption, QR generation, OTP
│   │   ├── model_service.py # OTP lifecycle against the Django ORM
│   │   └── mongo_service.py # PyMongo wrappers
│   ├── static/              # CSS, JS, and image assets
│   └── templates/           # Django HTML templates
├── scripts/
│   └── generate_vapid_keys.py
├── .github/workflows/       # CI: lint and tests
├── .env.example             # Template for your local .env
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.12 or newer
- MongoDB instance (local or Atlas)
- Redis server (local or Docker)

### Installation

1. Clone the repository and navigate into it:

   ```bash
   git clone <repository-url>
   cd orca
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Ensure Redis is running on your machine:

   ```bash
   sudo apt install redis-server
   sudo systemctl enable redis-server
   sudo systemctl start redis-server
   ```

4. Create your `.env` from the template and fill in real values:

   ```bash
   cp .env.example .env
   ```

   At minimum you need `SECRET_KEY`, `MONGO_URL`, `EMAIL_HOST_USER`, and
   `EMAIL_HOST_PASSWORD`. See [Environment Variables](#environment-variables).

5. Apply migrations and create the MongoDB indexes:

   ```bash
   python manage.py migrate
   python manage.py init_mongo
   ```

   `init_mongo` is a one-time bootstrap that creates the unique indexes the app
   relies on. MongoDB is connected to lazily, so the rest of the project,
   including the test suite, runs without a MongoDB server available.

6. Optionally create an admin account:

   ```bash
   python manage.py createsuperuser
   ```

### Running the Application

Because this app uses WebSockets, it must be run with an ASGI server. Use the
built-in management command, which reads `HOST`, `PORT`, and `DEBUG` from `.env`:

```bash
python manage.py runasgi
```

The application will be accessible at `http://127.0.0.1:8000/` (or whatever
`HOST` and `PORT` you configured).

You can also override `.env` values from the command line:

```bash
python manage.py runasgi --host 0.0.0.0 --port 9000
python manage.py runasgi --no-reload   # disable auto-reload (for staging)
```

### Running with Docker

`docker compose` brings up the app together with MongoDB and Redis:

```bash
cp .env.example .env   # fill in SECRET_KEY and email credentials
docker compose up --build -d
```

The app is served on `http://127.0.0.1:8004/`. The compose file overrides
`MONGO_URL` and `REDIS_URL` to point at the sibling containers.

---

## Available Scripts

| Command | Description |
|--------|-------------|
| `python manage.py runasgi` | Run ASGI server with WebSocket support (reads HOST/PORT from `.env`) |
| `python manage.py runasgi --host 0.0.0.0 --port 9000` | Override host/port at the command line |
| `python manage.py runasgi --no-reload` | Disable auto-reload (e.g. for staging) |
| `python manage.py init_mongo` | Create the MongoDB indexes. Safe to re-run |
| `python manage.py test` | Run the test suite. Needs no MongoDB or Redis |
| `flake8 .` | Lint the project |
| `python manage.py collectstatic` | Collect static files for production |
| `python manage.py runserver` | Basic Django HTTP server, no WebSocket support |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key, used for sessions and signing |
| `DEBUG` | Yes | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Yes in production | Comma-separated hostnames to serve. Defaults to `127.0.0.1,localhost` |
| `MONGO_URL` | Yes | MongoDB connection URI |
| `EMAIL_HOST_USER` | Yes | Email address used to send OTPs |
| `EMAIL_HOST_PASSWORD` | Yes | SMTP app password for email dispatch |
| `APP_URL` | No | Public base URL. Used for CSRF trusted origins and QR profile links |
| `APP_NAME` | No | App package name used to locate the QR output directory (default `orca2echo`) |
| `HOST` | No | Server bind address (default `127.0.0.1`) |
| `PORT` | No | Server bind port (default `8000`) |
| `REDIS_URL` | No | Redis URI (default `redis://127.0.0.1:6379`). Also enables the shared cache |
| `FERNET_KEY` | No | Dedicated key for profile and conversation tokens. Derived from `SECRET_KEY` when unset |
| `SECURE_SSL_REDIRECT` | No | Set `False` to disable the HTTPS redirect when `DEBUG=False` behind a proxy that already terminates TLS |
| `VAPID_PUBLIC_KEY` | No | Public key for push notifications (not yet wired up) |
| `VAPID_PRIVATE_KEY` | No | Private key for push notifications (not yet wired up) |

Rotating `SECRET_KEY` signs every user out. Rotating `FERNET_KEY`, or rotating
`SECRET_KEY` while `FERNET_KEY` is unset, additionally invalidates every
previously shared profile link and QR code.

---

## Security Notes

A few decisions worth knowing about if you deploy this:

- **OTP is the only authentication factor.** Codes are generated with `secrets`,
  expire after 10 minutes, allow 5 attempts, and cannot be re-requested for the
  same address more than once a minute. Requests are additionally capped per
  client address per hour.
- **Chat access is checked against the database**, not against the shape of the
  conversation token. A user who is not a participant is redirected away.
- **Message bodies are never inserted as HTML.** Server-rendered history relies
  on Django autoescaping and the WebSocket client builds nodes with
  `textContent`.
- **Never set `ALLOWED_HOSTS` to `*`.** With `DEBUG=False` it is what stops
  forged `Host` headers.
- **Do not commit `.env`.** It is gitignored. Use `.env.example` as the template.

---

## Known Limitations and Roadmap

This started as an early solo learning project, and some parts still show it.
Honest list of what is not done:

- **No message pagination.** A conversation loads its full history on every
  open, which will not scale past a few thousand messages.
- **Timestamps are client-supplied.** The browser sends `created_at`, so clock
  skew or a crafted WebSocket frame can misorder messages. These should be
  generated server-side.
- **Messages are stored in plaintext** in MongoDB. There is no end-to-end
  encryption; the link encryption covers URLs, not message bodies.
- **Split persistence.** Django auth and OTPs live in SQLite while everything
  else lives in MongoDB. A single store would be simpler.
- **The MongoDB layer is hand-rolled.** The model classes are thin insert
  wrappers with no schema validation or migration story.
- **No read receipts, typing indicators, presence, or media attachments.**
- **Push notification keys are configurable but unused.** No service worker
  subscription flow is wired up yet.
- **Test coverage is focused on auth and authorization.** The MongoDB service
  layer and the WebSocket consumer are not yet covered.
- **Mobile-only by design.** Desktop viewports are redirected to a notice page.

---

## License

Released under the [MIT License](LICENSE).
