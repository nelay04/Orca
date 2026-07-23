# Orca (orca2echo)

<p align="center">
  A real-time web-based chat application built with <strong>Django</strong>, <strong>Django Channels</strong>, <strong>PostgreSQL</strong>, and <strong>Redis</strong>.
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

## Quick start

The fastest path is Docker, which brings PostgreSQL and Redis with it. Nothing
else to install.

```bash
git clone <repository-url>
cd orca

cp .env.example .env
# Edit .env: set SECRET_KEY, FERNET_KEY, and your Gmail app password.
# Leave DATABASE_URL and REDIS_URL blank to use the bundled database containers.
# To use a hosted PostgreSQL instead, set DATABASE_URL and adjust COMPOSE_PROFILES.
# Add pgadmin to COMPOSE_PROFILES for a web UI on http://127.0.0.1:5050
# See docs/DEVELOPMENT.md#choosing-your-databases

docker compose up --build -d
```

Open `http://127.0.0.1:8004/`.

Prefer to run it directly? You will need Python 3.12+, PostgreSQL, and Redis.
The databases can still be the bundled containers:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill it in
docker compose up -d postgres redis   # or use your own servers
python manage.py migrate
python manage.py runasgi
```

Sign-in sends a one-time code by email, so working `EMAIL_HOST_USER` and
`EMAIL_HOST_PASSWORD` values are required to get past the login screen.

Full setup, every environment variable, and troubleshooting:
**[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**

---

## Documentation

| Document | Contents |
|----------|----------|
| **[Development guide](docs/DEVELOPMENT.md)** | Running locally or with Docker, environment variables, what `DATABASE_URL` should be, pgAdmin, email setup, commands, troubleshooting |
| **[Architecture](docs/ARCHITECTURE.md)** | Tech stack, data model, request flows, real-time messaging design, security model, project layout |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, Django, Django Channels (WebSockets) |
| Database | PostgreSQL (auth, OTPs, profiles, friendships, messages) |
| In-memory store | Redis (Channels layer and rate limiting) |
| Security | `cryptography.fernet` (authenticated symmetric encryption) |

See [Architecture](docs/ARCHITECTURE.md) for how these fit together.

---

## Testing

```bash
python manage.py test
flake8 .
```

The suite needs PostgreSQL (it creates and drops its own test database) but
not Redis. CI runs the same on Python 3.12 and 3.13.

---

## Known limitations and roadmap

This started as an early solo learning project, and some parts still show it.
Honest list of what is not done:

- **No message pagination.** A conversation loads its full history on every
  open, which will not scale past a few thousand messages.
- **Messages are stored in plaintext.** There is no end-to-end encryption; the
  link encryption covers URLs, not message bodies.
- **Chat sockets are only authorized per message.** A client is admitted to the
  Channels group named by the URL without a membership check, so a non-member
  who learned a conversation id could observe traffic, though not write to it.
- **No read receipts, typing indicators, presence, or media attachments.**
- **Push notification keys are configurable but unused.** No service worker
  subscription flow is wired up yet.
- **Test coverage is focused on auth and authorization.** The WebSocket
  consumer is not yet covered by automated tests.

---

## License

Released under the [MIT License](LICENSE).
