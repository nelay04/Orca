# Development guide

Everything needed to get Orca running, either directly on your machine or with
Docker.

- [Choosing how to run it](#choosing-how-to-run-it)
- [Option A: run locally](#option-a-run-locally)
- [Option B: run with Docker](#option-b-run-with-docker)
- [What MONGO_URL should be](#what-mongo_url-should-be)
- [Environment variables](#environment-variables)
- [Getting the email OTP working](#getting-the-email-otp-working)
- [Common commands](#common-commands)
- [Testing and linting](#testing-and-linting)
- [Rotating keys](#rotating-keys)
- [Troubleshooting](#troubleshooting)

---

## Choosing how to run it

Orca needs three things: the Python app, a MongoDB server, and a Redis server.

| | Local | Docker |
|---|---|---|
| You install | Python, MongoDB, Redis | Docker only |
| MongoDB and Redis | you run them, or use hosted | started for you as containers |
| Code changes | picked up on reload | restart the container |
| Best for | day-to-day development | trying it out, or a deployment-like run |

Docker is the fastest way to a working app because it brings MongoDB and Redis
with it. There is nothing to install and nothing to point at.

---

## Option A: run locally

### 1. Prerequisites

- **Python 3.12 or newer**
- **MongoDB** running locally, or a free [MongoDB Atlas](https://www.mongodb.com/atlas) cluster
- **Redis** running locally

On Debian or Ubuntu:

```bash
sudo apt install redis-server mongodb
sudo systemctl enable --now redis-server
```

Check Redis is reachable:

```bash
redis-cli ping     # expects: PONG
```

### 2. Install

```bash
git clone <repository-url>
cd orca

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Open `.env` and set, at minimum:

```env
SECRET_KEY=<generate one, see below>
MONGO_URL=mongodb://127.0.0.1:27017/
REDIS_URL=redis://127.0.0.1:6379
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<gmail app password>
```

Generate the two keys:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first is `SECRET_KEY`, the second is `FERNET_KEY`.

### 4. Initialise the databases

```bash
python manage.py migrate       # SQLite: auth, sessions, OTP table
python manage.py init_mongo    # MongoDB: unique indexes
```

`init_mongo` is the only command that needs a live MongoDB. `migrate`, `check`,
and the test suite all run without one, because the Mongo connection is lazy.

Optionally create an admin account:

```bash
python manage.py createsuperuser
```

### 5. Run

```bash
python manage.py runasgi
```

Open the URL it prints, by default `http://127.0.0.1:8000/`.

Use `runasgi`, not `runserver`. `runserver` is HTTP-only, so pages will load
but chat will silently fail to connect.

Override host and port without touching `.env`:

```bash
python manage.py runasgi --host 0.0.0.0 --port 9000
python manage.py runasgi --no-reload
```

---

## Option B: run with Docker

`docker-compose.yml` defines three services:

| Service | Image | Published to host | Purpose |
|---------|-------|-------------------|---------|
| `django` | built from `Dockerfile` | yes, `${PORT}` | the app |
| `mongo` | `mongo:7` | no | database, data kept in the `mongo_data` volume |
| `redis` | `redis:7-alpine` | no | Channels layer and cache |

**Yes, MongoDB runs as a container.** You do not need MongoDB installed, and
you do not need an Atlas account. The same is true for Redis.

Neither database publishes a host port. They are reachable only from the app
container over the compose network, which is why the app addresses them as
`mongo:27017` and `redis:6379`.

### 1. Configure

```bash
cp .env.example .env
```

Set `SECRET_KEY`, `FERNET_KEY`, and your email credentials as described above.

**Leave `MONGO_URL` and `REDIS_URL` alone.** Compose overrides both, see
[What MONGO_URL should be](#what-mongo_url-should-be).

The `.env` file must exist before you start, because compose loads it with
`env_file`. Compose also reads it to resolve `${PORT}`.

### 2. Start

```bash
docker compose up --build -d
```

The app is published on the port from `.env`, default `8004`, so
`http://127.0.0.1:8004/`.

The port is bound to `127.0.0.1`, so it is reachable from this machine only.
That is deliberate: a plain `8004:8004` mapping publishes on all interfaces and
bypasses the host firewall. On a server, put a reverse proxy in front rather
than widening this. To expose it anyway, set `DOCKER_BIND=0.0.0.0` in `.env`.

Compose also forces three settings regardless of `.env`, because a container is
not the same environment as your laptop:

| Setting | Value | Why |
|---------|-------|-----|
| `DEBUG` | `False` | Error pages would otherwise dump configuration to anyone who can reach the port. Set `DOCKER_DEBUG=True` to override. |
| `SECURE_SSL_REDIRECT` | `False` | The container speaks HTTP; the proxy in front terminates TLS and does the redirect. Set `DOCKER_SSL_REDIRECT=True` to override. |
| `MONGO_URL`, `REDIS_URL` | service names | `127.0.0.1` inside a container means the container itself. |

Because `DEBUG` is off, the session cookie is marked `Secure`. Browsers treat
`127.0.0.1` as a secure origin so sign-in still works locally, but if you reach
the container over plain HTTP from another machine, sign-in will fail until
TLS is in place. Set `DOCKER_DEBUG=True` for that kind of testing.

Migrations, MongoDB indexes, and `collectstatic` all run automatically on
container start via `entrypoint.sh`.

### 3. Everyday use

```bash
docker compose logs -f django                                  # follow logs
docker compose exec django python manage.py createsuperuser    # admin account
docker compose exec django python manage.py test               # run tests
docker compose restart django                                  # after code edits
docker compose down                                            # stop
docker compose down -v                                         # stop and wipe the database
```

The project directory is bind-mounted into the container, so code edits need
only a `restart`, not a rebuild. Rebuild when `requirements.txt` changes:

```bash
docker compose up --build -d
```

Collected static files go to a named volume rather than the bind mount, so
`collectstatic` inside the container does not leave root-owned files in your
working tree. You will see an empty `staticfiles/` directory appear locally;
that is just the mount point, and it is gitignored.

### Changing the port

Set `PORT` in `.env`. It flows to the published host port, the container's
listening port, and the `EXPOSE` directive together:

```env
PORT=9000
```

```bash
docker compose up --build -d     # now on http://127.0.0.1:9000/
```

Also update `APP_URL` to match, since QR codes embed it.

---

## What MONGO_URL should be

This trips people up, so here it is explicitly. The correct value depends
entirely on where the app is running relative to the database.

| How you run the app | Where MongoDB is | `MONGO_URL` |
|---|---|---|
| Locally | MongoDB installed locally | `mongodb://127.0.0.1:27017/` |
| Locally | MongoDB Atlas | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| Docker compose | the `mongo` container | `mongodb://mongo:27017/` **set for you, ignore `.env`** |
| Docker compose | MongoDB Atlas | see below |

### Why compose ignores your `.env` value

Inside a container, `127.0.0.1` means *that container*, not your laptop. A
`.env` pointing at `127.0.0.1:27017` would make the app try to reach a MongoDB
running inside its own container, and fail.

So `docker-compose.yml` sets the correct values explicitly:

```yaml
environment:
  MONGO_URL: mongodb://mongo:27017/
  REDIS_URL: redis://redis:6379
```

Values in an `environment:` block win over values from `env_file`, so whatever
`MONGO_URL` your `.env` holds is deliberately overridden while running under
compose. This is intentional: it means the same `.env` works for both local and
Docker runs without editing.

### Using Atlas from Docker instead

If you would rather use a hosted database, edit `docker-compose.yml`:

1. Delete the `MONGO_URL:` line from the `django` service's `environment:` block.
2. Delete the whole `mongo:` service and the `mongo` entry under `depends_on:`.
3. Optionally delete the `mongo_data` volume.

Your `.env` `MONGO_URL` is then used unchanged. Remember to allow your IP in the
Atlas network access list.

The same pattern applies to `REDIS_URL` and the `redis` service.

---

## Environment variables

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored; never
commit it.

### Required

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret, used for sessions and signing. Generate a fresh one, never reuse an example value. |
| `MONGO_URL` | MongoDB connection URI. See the table above. |
| `EMAIL_HOST_USER` | Gmail address that sends sign-in codes. |
| `EMAIL_HOST_PASSWORD` | Gmail **app password**, not your account password. |

### Recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | `True` for development. Never `True` in a deployment. |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated hostnames to serve. Set to your domain in production. Never `*`. |
| `FERNET_KEY` | derived from `SECRET_KEY` | Dedicated key for profile links. Setting it lets you rotate `SECRET_KEY` without breaking every shared link. |
| `APP_URL` | none | Public base URL. Used for CSRF trusted origins and embedded in QR codes. |
| `REDIS_URL` | `redis://127.0.0.1:6379` | Redis URI. Also switches the cache from in-memory to Redis. |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Bind address for `runasgi`. Ignored in Docker, which always binds `0.0.0.0`. |
| `PORT` | `8000` local, `8004` Docker | Bind port. In Docker this also sets the published host port. |
| `APP_NAME` | `orca2echo` | App package name, used to locate the QR output directory. |
| `SECURE_SSL_REDIRECT` | `True` | Only applies when `DEBUG=False`. Set `False` behind a proxy that already redirects, to avoid a redirect loop. |
| `SECURE_HSTS_SECONDS` | `0` | HSTS max-age. Only applies when `DEBUG=False`. Set `31536000` once HTTPS is confirmed everywhere; browsers that see it refuse plain HTTP until it expires. |
| `DJANGO_SUPERUSER_USERNAME` | unset | Only read by `entrypoint.sh`. All three superuser vars must be set for the account to be created; otherwise creation is skipped. |
| `DJANGO_SUPERUSER_EMAIL` | unset | |
| `DJANGO_SUPERUSER_PASSWORD` | unset | |
| `VAPID_PUBLIC_KEY` | unset | Push notifications. Not wired up yet. |
| `VAPID_PRIVATE_KEY` | unset | |

---

## Getting the email OTP working

Sign-in is the only way into the app, and it depends on outbound email. With
bad credentials, `/signin` returns "An error occurred."

For Gmail you need an **app password**, which requires 2-Step Verification:

1. Google Account, then Security, then turn on 2-Step Verification.
2. Security, then App passwords.
3. Generate one for "Mail". You get 16 characters in four groups.
4. Put it in `.env` as `EMAIL_HOST_PASSWORD`, spaces and all.

Your regular account password will not work.

### Developing without sending real email

To print codes to the console instead, add to `orca/settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

The OTP then appears in the server log. Do not commit that change.

---

## Common commands

| Command | Description |
|---------|-------------|
| `python manage.py runasgi` | Run the app with WebSocket support |
| `python manage.py runasgi --host 0.0.0.0 --port 9000` | Override bind address |
| `python manage.py runasgi --no-reload` | Disable auto-reload |
| `python manage.py migrate` | Apply SQLite migrations |
| `python manage.py init_mongo` | Create MongoDB indexes, safe to re-run |
| `python manage.py createsuperuser` | Create an admin account |
| `python manage.py test` | Run the test suite |
| `flake8 .` | Lint |
| `python manage.py collectstatic` | Collect static files |
| `python manage.py runserver` | HTTP only, chat will not work |

---

## Testing and linting

```bash
python manage.py test
flake8 .
```

The suite needs **neither MongoDB nor Redis**. MongoDB calls are patched and
the cache is overridden to local memory, so it runs on a bare checkout. This is
also what CI does, see [`.github/workflows/django.yml`](../.github/workflows/django.yml).

Coverage is focused on authentication and authorization: OTP lifecycle, the
signin and verify views, chat access control, token handling, and form
validation. The MongoDB service layer and the WebSocket consumer are not yet
covered.

---

## Exposing it on a server

Once the app is reachable at something other than `127.0.0.1`, whether that is
`http://<ip>:<port>` or a domain, a few things matter.

### Set DEBUG=False

This is the one that leaks. With `DEBUG=True`, any unhandled exception renders
Django's debug page, which includes the settings module and the request
environment. Anyone who can reach the port and trigger an error reads it.

Docker defaults `DEBUG` to `False` regardless of what `.env` says, and
`entrypoint.sh` prints a loud warning if you deliberately turn it on. Running
directly on a host has no such guard, so set it yourself.

Django masks settings whose names match `KEY`, `SECRET`, `PASS` and similar,
but **not** connection strings. `MONGO_URL` embeds its own username and
password and would otherwise be printed in full. `orca/reporting.py` widens the
mask to cover `MONGO`, `REDIS`, `EMAIL`, `URL`, `DSN` and friends, so those
stay hidden even if `DEBUG` is left on by accident. Treat that as a safety net,
not permission to run with `DEBUG=True`.

### Set ALLOWED_HOSTS

List the exact hostnames or IPs you serve. Never `*`.

```env
ALLOWED_HOSTS=orca.example.com,203.0.113.10
APP_URL=https://orca.example.com
```

`APP_URL` is embedded into generated QR codes, so it must be the address users
can actually reach, not an internal one.

### Check the deployment posture

```bash
DEBUG=False python manage.py check --deploy
```

This should report no issues. It covers cookie flags, the SSL redirect, and
HSTS.

### Databases stay private

`docker-compose.yml` publishes only the app port. MongoDB and Redis have no
`ports:` entry, so they are reachable only from the app container over the
compose network, never from the outside. If you add a `ports:` mapping to
either, you are exposing an unauthenticated database to whoever can reach the
host. Do not.

### TLS

Put a reverse proxy such as nginx or Caddy in front and terminate TLS there.
Then:

- `SECURE_SSL_REDIRECT=False` if the proxy already redirects, to avoid a loop.
- `SECURE_HSTS_SECONDS=31536000` once HTTPS is confirmed working everywhere.

Serving the container port directly to the internet means sessions and OTP
codes travel in the clear.

---

## Rotating keys

Rotating `SECRET_KEY` signs every user out. Rotating `FERNET_KEY`, or rotating
`SECRET_KEY` while `FERNET_KEY` is unset, additionally invalidates every profile
link and QR code ever shared.

When you rotate either, delete the generated QR images:

```bash
rm -rf orca2echo/static/qr/
```

They are cached by filename, so stale files would keep serving links that no
longer decrypt. They rebuild on the next page load.

---

## Troubleshooting

**Chat does not connect, or messages never arrive**
Redis is not reachable, or you started the app with `runserver`. Check
`redis-cli ping` and use `runasgi`.

**`ServerSelectionTimeoutError` from `init_mongo`**
MongoDB is not running or `MONGO_URL` is wrong. Under Docker this is expected
if you started the app alone rather than with `docker compose up`. Note that
only `init_mongo` fails fast this way; other commands connect lazily.

**"An error occurred." on the sign-in page**
Almost always email credentials. See
[Getting the email OTP working](#getting-the-email-otp-working). Check the
server log for the traceback.

**`DisallowedHost` errors**
Add the hostname to `ALLOWED_HOSTS` in `.env`, comma-separated.

**Infinite HTTPS redirect loop behind nginx**
Set `SECURE_SSL_REDIRECT=False`; your proxy is already redirecting.

**Static files 404 with `DEBUG=False`**
Run `python manage.py collectstatic`. The manifest storage backend needs it.

**Profile links or QR codes stopped working**
`SECRET_KEY` or `FERNET_KEY` changed. See [Rotating keys](#rotating-keys).

**Docker: `env file .env not found`**
Run `cp .env.example .env` first.

**Docker: port already in use**
Change `PORT` in `.env`, then `docker compose up -d`.
