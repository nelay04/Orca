from django.contrib.auth.models import User # type: ignore
from ..models import Otp


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

def retrieve_otp(email):
    try:
        otp_instance = Otp.objects.get(email=email)
        otp_value = otp_instance.otp
        return otp_value
    except Otp.DoesNotExist:
        otp_value = None  # Handle the case where no OTP exists for the email
    except Otp.MultipleObjectsReturned:
        otp_value = None  # Handle the case where multiple OTPs exist for the same email


def add_otp(email, otp):
    new_otp, created = Otp.objects.update_or_create(
        email=email,  # Use the email to search for an existing record
        defaults={"otp": otp},  # If found, update the OTP field; if not, create it
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