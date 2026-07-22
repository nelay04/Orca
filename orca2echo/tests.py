"""Tests for Orca.

These cover the authentication and authorization logic rather than the
MongoDB wrappers: MongoDB calls are patched out so the suite runs against a
bare checkout with no Mongo or Redis server.
"""

import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import SignupForm
from .models import Otp
from .services import model_service
from .services.auth_service import (
    decrypt_token,
    encrypt_token,
    generate_otp,
    generate_profile_qr,
    generate_short_name,
    normalize_full_name,
)

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

    @patch("orca2echo.views.get_user_data_by_email")
    def test_correct_otp_authenticates_existing_user(self, mock_user_data):
        mock_user_data.return_value = {"email": self.email, "is_new_user": False}
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
    @patch("orca2echo.views.find_an_object", return_value=None)
    def test_superuser_gets_the_same_response_as_anyone_else(self, _find, mock_send):
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
    @patch("orca2echo.views.find_an_object", return_value=None)
    def test_second_immediate_request_is_throttled(self, _find, mock_send):
        User.objects.create_user(username="u1", email="u1@example.com", password="pw")

        self.client.post(reverse("signin"), {"email": "u1@example.com"})
        self.assertEqual(mock_send.call_count, 1)

        self.client.post(reverse("signin"), {"email": "u1@example.com"})
        # Still 1: the resend window blocked the second send.
        self.assertEqual(mock_send.call_count, 1)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(reverse("signin"), {"email": "not-an-email"})
        self.assertContains(response, "valid email")


@override_settings(CACHES=LOCMEM_CACHE, STORAGES=TEST_STORAGES)
class ChatAuthorizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="a@example.com", password="pw")
        self.client.force_login(self.user)

    @patch("orca2echo.views.get_friend_id_by_conversation", return_value=None)
    def test_non_member_cannot_open_a_conversation(self, _mock):
        token = encrypt_token("bob_carol")
        response = self.client.get(reverse("chat"), {"with": token})
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

    def test_mongo_url_is_masked_in_request_meta(self):
        # MONGO_URL is an environment variable rather than a Django setting,
        # so it never reaches get_safe_settings(). It does reach request.META
        # under WSGI, where servers copy os.environ into the environ dict, and
        # the debug page renders that table. Django applies the same regex
        # there via get_safe_request_meta.
        self.request.META["MONGO_URL"] = "mongodb+srv://user:sup3rsecret@c.mongodb.net/"
        safe_meta = self.filt.get_safe_request_meta(self.request)

        self.assertEqual(safe_meta["MONGO_URL"], self.filt.cleansed_substitute)
        self.assertNotIn("sup3rsecret", repr(safe_meta))

    def test_secrets_are_masked(self):
        safe = self.safe_settings()
        for name in ["SECRET_KEY", "FERNET_KEY", "EMAIL_HOST_PASSWORD", "EMAIL_HOST_USER"]:
            self.assertEqual(safe[name], self.filt.cleansed_substitute, f"{name} leaked")

    @override_settings(MONGO_URL="mongodb+srv://user:sup3rsecret@c.mongodb.net/")
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
