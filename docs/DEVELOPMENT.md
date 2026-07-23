# Development guide

Everything needed to get Orca running, either directly on your machine or with
Docker.

- [Choosing how to run it](#choosing-how-to-run-it)
- [Option A: run locally](#option-a-run-locally)
- [Option B: run with Docker](#option-b-run-with-docker)
- [Choosing your databases](#choosing-your-databases)
- [Environment variables](#environment-variables)
- [Getting the email OTP working](#getting-the-email-otp-working)
- [Common commands](#common-commands)
- [Testing and linting](#testing-and-linting)
- [Rotating keys](#rotating-keys)
- [Troubleshooting](#troubleshooting)

---

## Choosing how to run it

Orca needs three things: the Python app, a PostgreSQL server, and a Redis
server.

| | Local | Docker |
|---|---|---|
| You install | Python, PostgreSQL, Redis | Docker only |
| PostgreSQL and Redis | you run them, or use hosted | started for you as containers |
| Code changes | picked up on reload | restart the container |
| Best for | day-to-day development | trying it out, or a deployment-like run |

Docker is the fastest way to a working app because it brings PostgreSQL and
Redis with it. There is nothing to install and nothing to point at.

A common middle path: run the databases as containers and the app on your
host. `docker compose up -d postgres redis` publishes PostgreSQL on
`127.0.0.1:5434`, which is what the example `DATABASE_URL` below points at.

---

## Option A: run locally

### 1. Prerequisites

- **Python 3.12 or newer**
- **PostgreSQL 14 or newer**, running locally, hosted, or as the bundled container
- **Redis** running locally

On Debian or Ubuntu:

```bash
sudo apt install redis-server postgresql
sudo systemctl enable --now redis-server postgresql
```

Or skip installing PostgreSQL entirely and use the container:

```bash
docker compose up -d postgres
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
DATABASE_URL=postgres://orca:orca@127.0.0.1:5434/orca
REDIS_URL=redis://127.0.0.1:6379
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<gmail app password>
```

`DATABASE_URL` is required. There is no SQLite fallback: without it the app
refuses to start rather than silently using an empty local database.

Generate the two keys:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first is `SECRET_KEY`, the second is `FERNET_KEY`.

### 4. Initialise the database

```bash
python manage.py migrate       # every table: auth, sessions, OTPs, app data
```

Optionally create an admin account. Every model is registered in the admin, so
this is also how you browse profiles, friend requests and messages:

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

`docker-compose.yml` defines four services:

| Service | Image | Published to host | Purpose |
|---------|-------|-------------------|---------|
| `django` | built from `Dockerfile` | yes, on `127.0.0.1:${PORT}` | the app |
| `postgres` | `postgres:17-alpine` | yes, on `127.0.0.1:${POSTGRES_PORT}` | database, data kept in the `postgres_data` volume. Profile `bundled-postgres` |
| `redis` | `redis:7-alpine` | no | Channels layer and cache. Profile `bundled-redis` |
| `pgadmin` | `dpage/pgadmin4` | yes, on `127.0.0.1:${PGADMIN_PORT}` | optional web UI for the database. Profile `pgadmin` |

**Yes, PostgreSQL can run as a container**, so you do not need it installed.
The same goes for Redis. Each is behind its own compose profile, so you can run
both, neither, or one of each. A container outside an active profile is never
created and uses no memory. See
[Choosing your databases](#choosing-your-databases).

Inside the compose network the app addresses them as `postgres:${POSTGRES_PORT}`
and `redis:6379`. PostgreSQL and pgAdmin also publish a host port so psql, an
IDE, or a browser on your machine can reach them; both are bound to `127.0.0.1`
unless you set `DOCKER_BIND`.

### 1. Configure

```bash
cp .env.example .env
```

Set `SECRET_KEY`, `FERNET_KEY`, and your email credentials as described above.

**Leave `DATABASE_URL` and `REDIS_URL` blank** and keep
`COMPOSE_PROFILES=bundled-db` to run both databases as containers. Nothing to
install. To use hosted databases, or a mix of the two, see
[Choosing your databases](#choosing-your-databases).

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

Compose overrides two settings regardless of `.env`, because a container is not
the same environment as your laptop:

| Setting | Value | Why |
|---------|-------|-----|
| `DEBUG` | `False` | Error pages would otherwise dump configuration to anyone who can reach the port. Set `DOCKER_DEBUG=True` to override. |
| `SECURE_SSL_REDIRECT` | `False` | The container speaks HTTP; the proxy in front terminates TLS and does the redirect. Set `DOCKER_SSL_REDIRECT=True` to override. |

`DATABASE_URL` and `REDIS_URL` are *not* overridden. Your `.env` decides. See
[Choosing your databases](#choosing-your-databases).

Because `DEBUG` is off, the session cookie is marked `Secure`. Browsers treat
`127.0.0.1` as a secure origin so sign-in still works locally, but if you reach
the container over plain HTTP from another machine, sign-in will fail until
TLS is in place. Set `DOCKER_DEBUG=True` for that kind of testing.

Migrations and `collectstatic` run automatically on container start via
`entrypoint.sh`.

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

## Choosing your databases

Orca needs PostgreSQL and Redis. Under Docker each can be a bundled container
or something you host yourself, chosen independently.

Two things in `.env` decide it:

- **`COMPOSE_PROFILES`** controls which database *containers exist*.
- **`DATABASE_URL` / `REDIS_URL`** tell the app where to connect. Leave a URL
  blank for anything running as a container.

| What you want | `COMPOSE_PROFILES` | `DATABASE_URL` | `REDIS_URL` |
|---|---|---|---|
| Both as containers | `bundled-db` | blank | blank |
| Both hosted | blank | `postgres://...` | `redis://host:6379` |
| Postgres hosted, Redis in Docker | `bundled-redis` | `postgres://...` | blank |
| Postgres in Docker, Redis hosted | `bundled-postgres` | blank | `redis://host:6379` |
| Both as containers, plus pgAdmin | `bundled-db,pgadmin` | blank | blank |

The list is comma-separated, so `bundled-postgres,bundled-redis` is identical to
`bundled-db`.

A container outside an active profile is **never created**, so it uses no
memory. That is the point of the profiles: with a hosted PostgreSQL you should
not have an idle `postgres` container sitting there.

### Browsing the database with pgAdmin

```env
COMPOSE_PROFILES=bundled-db,pgadmin
```

Then `docker compose up -d` and open `http://127.0.0.1:5050`. It runs in
single-user desktop mode, so it opens straight into the browser with no login
screen; `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` are the account it creates
internally. Register a server pointing at:

| Field | Value |
|---|---|
| Host | `postgres` |
| Port | `POSTGRES_PORT`, default `5434` |
| Database | `POSTGRES_DB`, default `orca` |
| Username / password | `POSTGRES_USER` / `POSTGRES_PASSWORD` |

Use the host name `postgres`, not `127.0.0.1`: inside the pgAdmin container
loopback means pgAdmin itself.

Because desktop mode asks for no password, anyone who can reach port 5050 has
full access to the database. That is fine on `127.0.0.1`; it is why
`DOCKER_BIND` should stay as it is on anything reachable from a network.

For most day-to-day inspection Django's own admin at `/admin/` is quicker,
since every model is registered there.

### Not running Docker?

`COMPOSE_PROFILES` is ignored entirely. Just set both URLs to real addresses:

```env
DATABASE_URL=postgres://orca:orca@127.0.0.1:5434/orca
REDIS_URL=redis://127.0.0.1:6379
```

### Why one variable cannot do it

It would be neater if a filled-in `DATABASE_URL` simply switched the container
off. Compose cannot do that: whether a service exists is resolved before
variable values are looked at, so an empty variable cannot disable a service.
The profile is the only thing that stops the container being created.

### The one address that never works in Docker

Inside a container, `127.0.0.1` means *that container*, not your host. A `.env`
holding `postgres://orca:orca@127.0.0.1:5434/orca` will not reach a PostgreSQL
on your machine; it fails looking inside the container.

Either leave the URL blank and use the bundled container, or give it an address
the container can reach. `entrypoint.sh` warns at startup if it spots a
loopback address, so you are not left staring at a connection timeout.

### Using a hosted PostgreSQL

```env
COMPOSE_PROFILES=bundled-redis
DATABASE_URL=postgres://user:password@db.example.com:5432/orca
REDIS_URL=
```

That runs Redis as a container and the database with your provider, with no
`postgres` container created. Remember to allow your server's address in the
provider's firewall, and to append `?sslmode=require` if they expect TLS.

---

## Environment variables

Copy `.env.example` to `.env` and fill it in. `.env` is gitignored; never
commit it.

### Required

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret, used for sessions and signing. Generate a fresh one, never reuse an example value. |
| `DATABASE_URL` | PostgreSQL connection URI, `postgres://user:password@host:port/dbname`. Required, with no fallback. Leave blank under Docker to use the bundled container. See [Choosing your databases](#choosing-your-databases). |
| `EMAIL_HOST_USER` | Gmail address that sends sign-in codes. |
| `EMAIL_HOST_PASSWORD` | Gmail **app password**, not your account password. |

### Recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `False` | `True` for development. Never `True` in a deployment. |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated hostnames to serve. Set to your domain in production. Never `*`. |
| `COMPOSE_PROFILES` | `bundled-db` | Docker only. Which containers to create: `bundled-db`, `bundled-postgres`, `bundled-redis`, `pgadmin`, or blank for none. Comma-separated. |
| `FERNET_KEY` | derived from `SECRET_KEY` | Dedicated key for profile links. Setting it lets you rotate `SECRET_KEY` without breaking every shared link. |
| `APP_URL` | none | Public base URL. Used for CSRF trusted origins and embedded in QR codes. |
| `REDIS_URL` | bundled container | Redis URI. Leave blank under Docker to use the bundled container. Also switches the cache from in-memory to Redis. |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `orca` | Bundled container only. Database created on first start. Ignored when `DATABASE_URL` points at a hosted server. |
| `POSTGRES_USER` | `orca` | Bundled container only. Role created on first start. |
| `POSTGRES_PASSWORD` | `orca` | Bundled container only. Change it before running anywhere but your own machine. |
| `POSTGRES_PORT` | `5434` | Port the bundled PostgreSQL both listens on and is published to. Not 5432, so it stays clear of a PostgreSQL already installed on the host. |
| `PGADMIN_EMAIL` | `admin@example.com` | Login for the optional pgAdmin container. |
| `PGADMIN_PASSWORD` | `admin` | Password for the same. Local use only. |
| `PGADMIN_PORT` | `5050` | Port pgAdmin both listens on and is published to. |
| `PGADMIN_CONFIG_SERVER_MODE` | `False` | Single-user desktop mode (no login screen). Only set to `True` behind a real login. |
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
| `python manage.py migrate` | Apply database migrations |
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

The suite needs **PostgreSQL** but not Redis: the test runner creates and drops
its own database, and the cache is overridden to local memory. `DATABASE_URL`
must be set, and the role in it needs permission to create databases. CI starts
a `postgres:17-alpine` service container for exactly this, see
[`.github/workflows/django.yml`](../.github/workflows/django.yml).

Coverage is focused on authentication and authorization: OTP lifecycle, the
signin and verify views, chat access control, the friend request lifecycle,
message ordering, token handling, and form validation. The WebSocket consumer
is not yet covered by automated tests.

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
but **not** connection strings. `DATABASE_URL` embeds its own username and
password and would otherwise be printed in full. `orca/reporting.py` widens the
mask to cover `DATABASE`, `REDIS`, `EMAIL`, `URL`, `DSN` and friends, so those
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

### Keep the databases private

Redis has no `ports:` entry, so it is reachable only from the app container
over the compose network. PostgreSQL and pgAdmin do publish a port, because
being able to point psql or an IDE at the database is worth a lot during
development, but both are bound to `127.0.0.1` by default and so are reachable
from this machine only.

`DOCKER_BIND=0.0.0.0` widens *all* of those mappings at once, including the
database and pgAdmin. On a server, leave it alone and reach them over an SSH
tunnel instead.

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

The same key also encrypts message bodies at rest. Unlike links, that ciphertext
is stored, so rotating the key makes existing chat history undecryptable. Before
rotating in an environment with real conversations, re-encrypt the `Message`
rows under the new key (or switch to `MultiFernet`, keeping the old key for
decryption).

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

**`ImproperlyConfigured: DATABASE_URL is not set`**
Copy `.env.example` to `.env` and fill in `DATABASE_URL`. There is deliberately
no SQLite fallback, so the app fails fast instead of starting against an empty
local database.

**`connection refused` or `OperationalError` from `migrate`**
PostgreSQL is not running, or `DATABASE_URL` points somewhere it is not. If you
are using the bundled container, check `docker compose ps postgres` and note
that the published port is `5434`, not `5432`.

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
