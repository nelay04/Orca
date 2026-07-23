"""Tests for Orca.

These cover authentication, authorization and the friendship lifecycle. They
run against a real PostgreSQL test database, which the test runner creates and
drops; only the cache is overridden, so no Redis server is needed.
"""

import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import SignupForm
from .models import FriendRequest, Friendship, Message, Otp, Profile
from .services import model_service
from .services.auth_service import (
    decrypt_message,
    decrypt_token,
    encrypt_message,
    encrypt_token,
    generate_otp,
    generate_profile_qr,
    generate_short_name,
    normalize_full_name,
)
from .services.data_service import (
    find_friendship,
    get_messages,
    list_friends_by_recent_activity,
    resolve_friendship,
)


def make_user(username, email, full_name="Test User", short_name="TU", search_id=None, **profile_fields):
    """A user with the profile every logged-in view expects to find."""
    user = User.objects.create_user(username=username, email=email, password="pw")
    Profile.objects.create(
        user=user,
        full_name=full_name,
        short_name=short_name,
        search_id=search_id or f"id-{username}",
        is_new_user=False,
        **profile_fields,
    )
    return user


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "orca-test-cache",
    }
}

# Tests run with DEBUG=False, where the manifest storage insists every static
# file has a hashed entry built by collectstatic. Use plain storage instead so
# rendering a template does not require a collectstatic run first.
TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class GenerateOtpTests(TestCase):
    def test_otp_is_always_six_digits(self):
        for _ in range(200):
            otp = generate_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())

    def test_otp_uses_the_full_keyspace(self):
        # The old implementation started at 111111, silently discarding
        # roughly 11% of the range. Values below that must be reachable.
        seen_low = any(int(generate_otp()) < 111111 for _ in range(2000))
        self.assertTrue(seen_low, "OTP range appears truncated below 111111")


class OtpLifecycleTests(TestCase):
    def setUp(self):
        self.email = "user@example.com"

    def test_add_otp_resets_attempt_counter(self):
        model_service.add_otp(self.email, "123456")
        otp = model_service.get_otp_instance(self.email)
        otp.attempts = 3
        otp.save()

        model_service.add_otp(self.email, "654321")
        self.assertEqual(model_service.get_otp_instance(self.email).attempts, 0)

    def test_missing_otp_returns_none_not_the_string_none(self):
        # Regression: retrieve_otp() returning None was compared with
        # str(original_otp), so posting the literal "None" authenticated.
        self.assertIsNone(model_service.retrieve_otp("nobody@example.com"))
        self.assertIsNone(model_service.get_otp_instance("nobody@example.com"))

    def test_fresh_otp_is_not_expired(self):
        model_service.add_otp(self.email, "123456")
        self.assertFalse(model_service.is_otp_expired(model_service.get_otp_instance(self.email)))

    def test_otp_expires_after_its_ttl(self):
        model_service.add_otp(self.email, "123456")
        otp = model_service.get_otp_instance(self.email)
        Otp.objects.filter(pk=otp.pk).update(
            created_at=timezone.now() - model_service.OTP_TTL - timedelta(seconds=1)
        )
        self.assertTrue(model_service.is_otp_expired(model_service.get_otp_instance(self.email)))

    def test_missing_otp_counts_as_expired(self):
        self.assertTrue(model_service.is_otp_expired(None))

    def test_otp_is_burned_after_max_attempts(self):
        model_service.add_otp(self.email, "123456")
        for _ in range(model_service.OTP_MAX_ATTEMPTS - 1):
            burned = model_service.register_failed_attempt(
                model_service.get_otp_instance(self.email)
            )
            self.assertFalse(burned)

        burned = model_service.register_failed_attempt(model_service.get_otp_instance(self.email))
        self.assertTrue(burned)
        self.assertIsNone(model_service.get_otp_instance(self.email))

    def test_resend_is_throttled_then_allowed(self):
        self.assertTrue(model_service.can_send_otp(self.email))

        model_service.add_otp(self.email, "123456")
        self.assertFalse(model_service.can_send_otp(self.email))

        otp = model_service.get_otp_instance(self.email)
        Otp.objects.filter(pk=otp.pk).update(
            created_at=timezone.now() - model_service.OTP_RESEND_INTERVAL - timedelta(seconds=1)
        )
        self.assertTrue(model_service.can_send_otp(self.email))


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class VerifyOtpViewTests(TestCase):
    def setUp(self):
        self.email = "user@example.com"
        self.username = "user123"
        User.objects.create_user(username=self.username, email=self.email, password="123456")
        session = self.client.session
        session["email"] = self.email
        session["username"] = self.username
        session.save()

    def post_otp(self, value):
        return self.client.post(reverse("verify-otp"), {"otp": value})

    def test_literal_none_does_not_authenticate(self):
        # No Otp row exists, so the old str(None) comparison would match.
        response = self.post_otp("None")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "expired or was already used")

    def test_empty_otp_does_not_authenticate(self):
        self.post_otp("")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_otp_is_rejected_and_cleared(self):
        model_service.add_otp(self.email, "123456")
        otp = model_service.get_otp_instance(self.email)
        Otp.objects.filter(pk=otp.pk).update(
            created_at=timezone.now() - model_service.OTP_TTL - timedelta(seconds=1)
        )

        response = self.post_otp("123456")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "expired")
        self.assertIsNone(model_service.get_otp_instance(self.email))

    def test_wrong_otp_increments_attempts(self):
        model_service.add_otp(self.email, "123456")
        self.post_otp("000000")
        self.assertEqual(model_service.get_otp_instance(self.email).attempts, 1)

    def test_repeated_wrong_otps_burn_the_code(self):
        model_service.add_otp(self.email, "123456")
        for _ in range(model_service.OTP_MAX_ATTEMPTS):
            self.post_otp("000000")

        self.assertIsNone(model_service.get_otp_instance(self.email))
        # The correct code no longer works once the OTP has been burned.
        self.post_otp("123456")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_correct_otp_authenticates_existing_user(self):
        Profile.objects.create(user=User.objects.get(username=self.username), is_new_user=False)
        model_service.add_otp(self.email, "123456")

        response = self.post_otp("123456")
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_get_redirects_to_signin(self):
        response = self.client.get(reverse("verify-otp"))
        self.assertRedirects(response, reverse("signin"), fetch_redirect_response=False)


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class SigninViewTests(TestCase):
    @patch("orca2echo.views.send_otp")
    def test_superuser_gets_the_same_response_as_anyone_else(self, mock_send):
        User.objects.create_superuser(
            username="root", email="root@example.com", password="pw"
        )
        response = self.client.post(reverse("signin"), {"email": "root@example.com"})

        self.assertEqual(response.status_code, 200)
        # No enumeration: the old code returned a distinct "You're a superuser"
        # body identifying the administrator account.
        self.assertNotContains(response, "superuser")
        # And no OTP mail is sent to a superuser.
        mock_send.assert_not_called()

    @patch("orca2echo.views.send_otp")
    def test_second_immediate_request_is_throttled(self, mock_send):
        make_user("u1", "u1@example.com")

        self.client.post(reverse("signin"), {"email": "u1@example.com"})
        self.assertEqual(mock_send.call_count, 1)

        self.client.post(reverse("signin"), {"email": "u1@example.com"})
        # Still 1: the resend window blocked the second send.
        self.assertEqual(mock_send.call_count, 1)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(reverse("signin"), {"email": "not-an-email"})
        self.assertContains(response, "valid email")

    @patch("orca2echo.views.send_otp")
    def test_new_user_gets_a_profile(self, _mock_send):
        self.client.post(reverse("signin"), {"email": "fresh@example.com"})

        user = User.objects.get(email="fresh@example.com")
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(user.profile.is_new_user)

    @patch("orca2echo.views.send_otp")
    @patch("orca2echo.views.Profile.objects.create", side_effect=RuntimeError("db blew up"))
    def test_a_failed_profile_write_rolls_the_user_back(self, _mock_profile, _mock_send):
        # Without the atomic block, an auth_user with no profile would hold the
        # address and the user could never complete signup.
        self.client.post(reverse("signin"), {"email": "doomed@example.com"})
        self.assertFalse(User.objects.filter(email="doomed@example.com").exists())


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class ChatAuthorizationTests(TestCase):
    def setUp(self):
        self.user = make_user("alice", "a@example.com", full_name="Alice Ash", short_name="AA")
        self.bob = make_user("bob", "b@example.com", full_name="Bob Birch", short_name="BB")
        self.carol = make_user("carol", "c@example.com", full_name="Carol Cedar", short_name="CC")
        self.client.force_login(self.user)

    def test_member_can_open_their_conversation(self):
        friendship = Friendship.objects.create(user_1=self.user, user_2=self.bob)
        response = self.client.get(reverse("chat"), {"with": encrypt_token(str(friendship.public_id))})
        self.assertEqual(response.status_code, 200)

    def test_non_member_cannot_open_a_conversation(self):
        # A conversation between two other people. The token decrypts fine,
        # which is exactly why membership has to be a database lookup.
        friendship = Friendship.objects.create(user_1=self.bob, user_2=self.carol)
        response = self.client.get(reverse("chat"), {"with": encrypt_token(str(friendship.public_id))})
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)

    def test_unknown_conversation_redirects_home(self):
        response = self.client.get(
            reverse("chat"), {"with": encrypt_token("6f1e4b0e-0000-4000-8000-000000000000")}
        )
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)

    def test_token_that_is_not_a_uuid_redirects_home(self):
        response = self.client.get(reverse("chat"), {"with": encrypt_token("alice_bob")})
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)

    def test_missing_token_redirects_home(self):
        response = self.client.get(reverse("chat"))
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)

    def test_garbage_token_redirects_home(self):
        response = self.client.get(reverse("chat"), {"with": "not-a-real-token"})
        self.assertRedirects(response, reverse("orca"), fetch_redirect_response=False)

    def test_anonymous_user_is_sent_to_signin(self):
        self.client.logout()
        response = self.client.get(reverse("chat"), {"with": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("signin", response["Location"])


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class FriendRequestLifecycleTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", "a@example.com", full_name="Alice Ash", short_name="AA", search_id="111")
        self.bob = make_user("bob", "b@example.com", full_name="Bob Birch", short_name="BB", search_id="222")
        self.client.force_login(self.alice)

    def send_request(self):
        return self.client.post(
            reverse("add-friend"),
            {
                "short_name_enc": encrypt_token("BB"),
                "id_number_enc": encrypt_token("222"),
            },
        )

    def test_request_is_created_once_and_reactivated_on_resend(self):
        self.send_request()
        self.assertEqual(FriendRequest.objects.count(), 1)

        # Cancel, then send again. The same row is reused, which is what the
        # unique constraint on the pair enforces.
        self.client.post(
            reverse("cancel-request"),
            {"from_sent_request": "0", "short_name_enc": encrypt_token("BB"), "id_number_enc": encrypt_token("222")},
        )
        self.send_request()

        self.assertEqual(FriendRequest.objects.count(), 1)
        friend_request = FriendRequest.objects.get()
        self.assertTrue(friend_request.is_active)
        self.assertFalse(friend_request.is_cancelled)
        self.assertEqual(friend_request.request_count, 2)

    def test_accepting_creates_exactly_one_friendship(self):
        self.send_request()

        self.client.force_login(self.bob)
        # These identifiers are posted unencrypted from the requests page.
        self.client.post(
            reverse("response"),
            {"response": "accept", "short_name_enc": "AA", "id_number_enc": "111"},
        )

        self.assertEqual(Friendship.objects.count(), 1)
        self.assertTrue(FriendRequest.objects.get().is_accepted)
        self.assertIsNotNone(find_friendship(self.alice, self.bob))
        # And the reverse lookup finds the same row, whichever order it asks in.
        self.assertEqual(
            find_friendship(self.bob, self.alice).pk, find_friendship(self.alice, self.bob).pk
        )

    def test_declining_leaves_no_friendship(self):
        self.send_request()

        self.client.force_login(self.bob)
        self.client.post(
            reverse("response"),
            {"response": "decline", "short_name_enc": "AA", "id_number_enc": "111"},
        )

        self.assertEqual(Friendship.objects.count(), 0)
        friend_request = FriendRequest.objects.get()
        self.assertTrue(friend_request.is_declined)
        self.assertFalse(friend_request.is_active)


class MessageTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", "a@example.com")
        self.bob = make_user("bob", "b@example.com")
        self.friendship = Friendship.objects.create(user_1=self.alice, user_2=self.bob)

    def test_messages_come_back_oldest_first(self):
        for body in ["first", "second", "third"]:
            Message.objects.create(
                friendship=self.friendship, sender=self.alice, receiver=self.bob, message=body
            )

        self.assertEqual(
            [m.message for m in self.friendship.messages.all()], ["first", "second", "third"]
        )

    def test_created_at_is_set_by_the_server(self):
        before = timezone.now()
        message = Message.objects.create(
            friendship=self.friendship, sender=self.alice, receiver=self.bob, message="hi"
        )
        self.assertGreaterEqual(message.created_at, before)

    def test_resolve_friendship_returns_the_other_member(self):
        resolved = resolve_friendship(str(self.friendship.public_id), self.alice)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved[1], self.bob)

    def test_resolve_friendship_rejects_a_stranger(self):
        stranger = make_user("carol", "c@example.com")
        self.assertIsNone(resolve_friendship(str(self.friendship.public_id), stranger))


class MessageEncryptionTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", "a@example.com")
        self.bob = make_user("bob", "b@example.com")
        self.friendship = Friendship.objects.create(user_1=self.alice, user_2=self.bob)

    def test_encrypt_decrypt_roundtrip(self):
        self.assertEqual(decrypt_message(encrypt_message("hello there")), "hello there")

    def test_ciphertext_is_not_the_plaintext(self):
        self.assertNotEqual(encrypt_message("secret"), "secret")

    def test_empty_body_is_left_untouched(self):
        self.assertEqual(encrypt_message(""), "")
        self.assertEqual(decrypt_message(""), "")

    def test_undecryptable_value_is_returned_as_is(self):
        # A display path must never raise on an unexpected value.
        self.assertEqual(decrypt_message("not a token"), "not a token")

    def test_get_messages_returns_decrypted_bodies(self):
        Message.objects.create(
            friendship=self.friendship, sender=self.alice, receiver=self.bob,
            message=encrypt_message("ciphered hi"),
        )
        [message] = get_messages(self.friendship)
        self.assertEqual(message.message, "ciphered hi")

    def test_body_is_stored_as_ciphertext(self):
        Message.objects.create(
            friendship=self.friendship, sender=self.alice, receiver=self.bob,
            message=encrypt_message("on disk"),
        )
        raw = Message.objects.get().message
        self.assertNotIn("on disk", raw)
        self.assertEqual(decrypt_message(raw), "on disk")

    def test_conversation_preview_is_decrypted(self):
        Message.objects.create(
            friendship=self.friendship, sender=self.alice, receiver=self.bob,
            message=encrypt_message("latest note"),
        )
        [entry] = list_friends_by_recent_activity(self.bob)
        self.assertEqual(entry["last_message_text"], "latest note")

    def test_save_message_encrypts_then_reads_back(self):
        from asgiref.sync import async_to_sync

        from .consumers import save_message

        saved = async_to_sync(save_message)(self.alice, self.bob.username, "via consumer")
        self.assertIsNotNone(saved)
        self.assertNotIn("via consumer", saved.message)
        [message] = get_messages(self.friendship)
        self.assertEqual(message.message, "via consumer")


class TokenTests(TestCase):
    def test_roundtrip(self):
        self.assertEqual(decrypt_token(encrypt_token("hello")), "hello")

    def test_tokens_are_not_deterministic(self):
        # Fernet embeds a timestamp and IV. Anything caching on token output
        # (the QR filename used to) will never get a hit.
        self.assertNotEqual(encrypt_token("hello"), encrypt_token("hello"))

    def test_tampered_token_returns_none(self):
        self.assertIsNone(decrypt_token(encrypt_token("hello")[:-4] + "AAAA"))

    def test_empty_input_returns_none(self):
        self.assertIsNone(encrypt_token(""))
        self.assertIsNone(decrypt_token(""))
        self.assertIsNone(decrypt_token(None))

    @override_settings(FERNET_KEY=None)
    def test_falls_back_to_secret_key_derivation(self):
        self.assertEqual(decrypt_token(encrypt_token("legacy")), "legacy")


class ProfileQrTests(TestCase):
    """generate_profile_qr writes real PNG files, so point BASE_DIR at a
    temporary directory to keep the project's static/qr folder clean."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(BASE_DIR=self._tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_filename_is_stable_across_calls(self):
        # Regression: keying the filename on encrypt_token output meant the
        # on-disk cache never hit and a new PNG was written per request.
        first = generate_profile_qr("alice123", "AT", "12345")
        second = generate_profile_qr("alice123", "AT", "12345")
        self.assertEqual(first, second)
        self.assertEqual(first, "qr_alice123.png")

    def test_missing_identifiers_return_none(self):
        self.assertIsNone(generate_profile_qr(None, "AT", "12345"))
        self.assertIsNone(generate_profile_qr("alice123", None, "12345"))
        self.assertIsNone(generate_profile_qr("alice123", "AT", None))

    def test_path_traversal_in_username_is_stripped(self):
        name = generate_profile_qr("../../etc/passwd", "AT", "12345")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class QrImageViewTests(TestCase):
    """The QR PNG is served straight from disk by views.qr_image, not
    through django.contrib.staticfiles/WhiteNoise: it is generated at
    request time, which is after collectstatic and WhiteNoise's static
    index have already run, so the static pipeline never sees it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        override = override_settings(BASE_DIR=self._tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = make_user("alice", "a@example.com", full_name="Alice Ash", short_name="AA", search_id="111")

    def test_serves_png_for_the_logged_in_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("qr-image"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_anonymous_user_is_sent_to_signin(self):
        response = self.client.get(reverse("qr-image"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("signin", response["Location"])


class SignupFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {"full_name": "Snow Flake", "gender": "male", "dob": "2000-01-01"}
        data.update(overrides)
        return data

    def test_accepts_valid_input(self):
        self.assertTrue(SignupForm(self.valid_data()).is_valid())

    def test_rejects_future_date_of_birth(self):
        future = (timezone.now() + timedelta(days=365)).date().isoformat()
        self.assertFalse(SignupForm(self.valid_data(dob=future)).is_valid())

    def test_rejects_digits_in_name(self):
        self.assertFalse(SignupForm(self.valid_data(full_name="Snow 123")).is_valid())

    def test_rejects_markup_in_name(self):
        self.assertFalse(SignupForm(self.valid_data(full_name="<script>x</script>")).is_valid())

    def test_rejects_unknown_gender(self):
        self.assertFalse(SignupForm(self.valid_data(gender="wizard")).is_valid())


class ExceptionReportFilterTests(TestCase):
    """The debug page and 500 emails dump the settings module. Connection
    URIs carry embedded credentials, so they must not appear in cleartext."""

    def setUp(self):
        from django.http import HttpRequest
        from orca.reporting import OrcaExceptionReporterFilter

        self.filt = OrcaExceptionReporterFilter()
        self.request = HttpRequest()

    def safe_settings(self):
        return self.filt.get_safe_settings()

    def test_redis_url_setting_is_masked(self):
        self.assertEqual(
            self.safe_settings()["REDIS_URL"],
            self.filt.cleansed_substitute,
            "REDIS_URL would be shown in cleartext on an error page",
        )

    def test_database_url_is_masked_in_request_meta(self):
        # DATABASE_URL reaches request.META under WSGI, where servers copy
        # os.environ into the environ dict, and the debug page renders that
        # table. Django applies the same regex there via get_safe_request_meta.
        self.request.META["DATABASE_URL"] = "postgres://user:sup3rsecret@db.example.com:5432/orca"
        safe_meta = self.filt.get_safe_request_meta(self.request)

        self.assertEqual(safe_meta["DATABASE_URL"], self.filt.cleansed_substitute)
        self.assertNotIn("sup3rsecret", repr(safe_meta))

    def test_secrets_are_masked(self):
        safe = self.safe_settings()
        for name in ["SECRET_KEY", "FERNET_KEY", "EMAIL_HOST_PASSWORD", "EMAIL_HOST_USER"]:
            self.assertEqual(safe[name], self.filt.cleansed_substitute, f"{name} leaked")

    @override_settings(DATABASE_URL="postgres://user:sup3rsecret@db.example.com:5432/orca")
    def test_no_password_survives_in_the_settings_dump(self):
        # Scans the whole rendered dump rather than one key, so a password
        # cannot slip through via some other setting that happens to hold it.
        self.assertNotIn("sup3rsecret", repr(self.safe_settings()))

    def test_harmless_settings_are_still_visible(self):
        # Over-masking would make the debug page useless, so confirm the
        # filter has not simply hidden everything.
        self.assertNotEqual(
            self.safe_settings()["ALLOWED_HOSTS"], self.filt.cleansed_substitute
        )


class NameHelperTests(TestCase):
    def test_normalize_collapses_whitespace_and_title_cases(self):
        self.assertEqual(normalize_full_name("  snow   flake  "), "Snow Flake")

    def test_short_name_uses_initials(self):
        self.assertEqual(generate_short_name("Snow Flake"), "SF")
