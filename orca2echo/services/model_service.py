from datetime import timedelta

from django.contrib.auth.models import User  # type: ignore
from django.utils import timezone  # type: ignore

from ..models import Otp

# An OTP is the only authentication factor, so it is short-lived, capped at a
# small number of guesses, and cannot be re-requested in a tight loop.
OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_INTERVAL = timedelta(seconds=60)


def get_user_by_email(email):
    users = User.objects.filter(email=email)  # Get all users with this email
    if users.exists():
        return users.first()  # Return the first user if found
    else:
        return None  # Return None if no users are found


def get_user_by_username(username):
    users = User.objects.filter(username=username)  # Get all users with this email
    if users.exists():
        return users.first()  # Return the first user if found
    else:
        return None  # Return None if no users are found


def get_otp_instance(email):
    """Return the Otp row for this email, or None. Never raises."""
    if not email:
        return None
    try:
        return Otp.objects.get(email=email)
    except Otp.DoesNotExist:
        return None
    except Otp.MultipleObjectsReturned:
        # Should not happen, but a duplicate row must not authenticate anyone.
        return None


def retrieve_otp(email):
    otp_instance = get_otp_instance(email)
    if otp_instance is None:
        return None
    return otp_instance.otp


def is_otp_expired(otp_instance):
    if otp_instance is None or otp_instance.created_at is None:
        return True
    return timezone.now() - otp_instance.created_at > OTP_TTL


def register_failed_attempt(otp_instance):
    """Count a wrong guess. Deletes the OTP once the cap is reached.

    Returns True when the OTP was burned so the caller can tell the user to
    request a new one.
    """
    if otp_instance is None:
        return False
    otp_instance.attempts += 1
    if otp_instance.attempts >= OTP_MAX_ATTEMPTS:
        otp_instance.delete()
        return True
    otp_instance.save(update_fields=["attempts"])
    return False


def can_send_otp(email):
    """False while the previous OTP for this email is still within the resend window.

    Without this, signin doubles as an open relay: anyone can POST repeatedly
    and have the configured mailbox send unlimited mail to an arbitrary address.
    """
    otp_instance = get_otp_instance(email)
    if otp_instance is None or otp_instance.created_at is None:
        return True
    return timezone.now() - otp_instance.created_at >= OTP_RESEND_INTERVAL


def add_otp(email, otp):
    Otp.objects.update_or_create(
        email=email,  # Use the email to search for an existing record
        # Reset the attempt counter so a fresh OTP starts with a full budget.
        defaults={"otp": otp, "attempts": 0},
    )


def delete_otp_by_email(email):
    try:
        # Find the OTP object with the given email
        otp_obj = Otp.objects.get(email=email)

        # Delete the OTP object
        otp_obj.delete()
        return None
    except Otp.DoesNotExist:
        return None
