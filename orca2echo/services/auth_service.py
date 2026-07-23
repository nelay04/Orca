"""Service for user authentication: OTP delivery, tokens, and share links."""

import base64
import hashlib
import logging
import os
import random
import re
import secrets
import time
from datetime import datetime

import pytz  # type: ignore
import qrcode  # type: ignore
from cryptography.fernet import Fernet
from django.conf import settings  # type: ignore
from django.core.mail import send_mail  # type: ignore
from django.template.loader import render_to_string  # type: ignore
from django.utils.html import strip_tags  # type: ignore

from .data_service import get_profile

logger = logging.getLogger(__name__)


def auth_user_data(request):
    try:
        if "full_name" not in request.session or "base64_string" not in request.session:
            # print("no data in session session")
            profile = get_profile(request.user.username)
            base64_string = profile.profile_picture
            full_name = profile.full_name
            request.session["base64_string"] = base64_string
            request.session["full_name"] = full_name
        else:
            # print("retrieving from session")
            base64_string = request.session.get("base64_string")
            full_name = request.session.get("full_name")

        auth_user_info = {
            "auth_user": request.user,
            "base64_image": base64_string,
            "name": full_name,
        }
        return auth_user_info
    except Exception:
        logger.exception("Error in auth_user_data")
        return None


def generate_otp():
    # Generate a 6-digit OTP in the 111111-999999 range.
    # Uses secrets rather than random: this value is the only authentication
    # factor, and random is seeded predictably enough to be guessable.

    # randbelow(888889) returns a number from 0 to 888888.
    # Adding 111111 shifts the range to 111111 - 999999.
    otp = secrets.randbelow(888_889) + 111_111

    return str(otp)


def extract_first_name(name: str) -> str:
    """
    Extracts the first name from a given name.
    If the name has only one word, returns the entire name.
    If the input is blank or contains only whitespace, returns an empty string.

    Args:
        name (str): The full name of the person.

    Returns:
        str: The first name, full name (if only one word), or an empty string for blank input.
    """
    # Strip whitespace and check if the name is blank
    if not name.strip():
        return ""

    # Split the name into words
    name_parts = name.strip().split()

    # Return the first part of the name
    return name_parts[0]


def get_current_time_ist():
    # Set timezone to IST (Indian Standard Time)
    ist = pytz.timezone("Asia/Kolkata")
    # Get current time in IST
    current_time = datetime.now(ist)
    # Format the current time as "DD-MM-YYYY HH:MM:SS.milliseconds"
    formatted_time = current_time.strftime("%d-%m-%Y %H:%M:%S:") + str(
        current_time.microsecond // 1000
    ).zfill(3)
    return formatted_time


def generate_nanoseconds():
    # Step 2: Get the current time formatted as YYYYMMDDHHMMSS
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    # Step 3: Add nanoseconds for even finer granularity
    nanoseconds = int(time.time_ns() % 1_000_000_000)  # Get the current nanoseconds
    # Step 4: Combine the prefix, current time, and nanoseconds to form the username
    search_id = f"{current_time}{nanoseconds}"

    return search_id


def send_otp(otp, email, name):
    # Define the context for rendering the template
    context = {
        "name": name,
        "otp": otp,
        "brand_name": "Orca",
        "dated": get_current_time_ist(),
        "address_line1": "Sector V, Salt Lake City",
        "address_line2": "Kolkata, WB",
    }

    # Render the HTML template
    html_message = render_to_string("otp_email_template.html", context)
    plain_message = strip_tags(html_message)  # Generate plain text version if needed

    send_mail(
        "Orca",  # Subject of the email
        plain_message,  # Plain text content (optional fallback)
        settings.EMAIL_HOST_USER,  # Sender's email address
        [email],  # List of recipient email addresses
        fail_silently=False,
        html_message=html_message,  # HTML content of the email
    )


def generate_search_id(nanoseconds):
    # Extract the middle portion by omitting the first 4 and last 6 digits
    extracted = str(nanoseconds)[4:-6]

    # Desired total length of the final search ID
    total_length = 20  # Adjust as needed

    # Calculate the remaining length for random digits (before and after)
    remaining_length = total_length - len(extracted)
    prefix_length = remaining_length // 2
    suffix_length = remaining_length - prefix_length

    # Generate random digits for prefix and suffix
    prefix = "".join(random.choices("123456789", k=prefix_length))
    suffix = "".join(random.choices("123456789", k=suffix_length))

    # Combine prefix, extracted portion, and suffix
    search_id = f"{prefix}{extracted}{suffix}"
    return search_id


def generate_username(email, nanosecond):
    """
    Generate a username by extracting the prefix from the email and appending nanoseconds.
    Removes special characters and numbers from the prefix.

    Args:
        email (str): The user's email address.
        nanosecond (int): A nanosecond value to ensure uniqueness.

    Returns:
        str: The generated username.
    """
    # Step 1: Extract the part before '@' from the email
    username_prefix = email.split("@")[0]

    # Step 2: Remove special characters and numbers
    clean_prefix = re.sub(r"[^a-zA-Z]", "", username_prefix)

    # Step 3: Combine the cleaned prefix and nanoseconds to form the username
    username = f"{clean_prefix}{nanosecond}"
    logger.info(f"Generated username: {username}")
    return username


def get_demo_img_text(gender):
    if gender == "male":
        file_path = os.path.join(settings.MEDIA_ROOT, "boy_profile.txt")
    elif gender == "female":
        file_path = os.path.join(settings.MEDIA_ROOT, "girl_profile.txt")
    else:
        file_path = os.path.join(settings.MEDIA_ROOT, "other_profile.txt")

    # Read the content of the text file
    try:
        with open(file_path, "r") as file:
            file_content = (
                file.read()
            )  # Store the content in the variable 'file_content'
            return file_content
    except FileNotFoundError:
        return "File not found."


def get_oops_img_text(theme):
    # Dynamically create the file path based on the theme parameter
    file_name = f"{theme}.txt"
    file_path = os.path.join(settings.MEDIA_ROOT, file_name)
    logger.info(f"Oops img path: {file_path}")
    # Read the content of the text file
    try:
        with open(file_path, "r") as file:
            file_content = (
                file.read()
            )  # Store the content in the variable 'file_content'
            return file_content
    except FileNotFoundError:
        return "File not found."


def generate_short_name(full_name):
    # Split the name into parts and remove any extra spaces
    name_parts = full_name.strip().split()
    # Get the first letter of each part and convert to uppercase
    short_name = "".join([part[0].upper() for part in name_parts])
    return short_name


def normalize_full_name(full_name):
    # Remove leading, trailing, and extra spaces between words
    cleaned_name = " ".join(full_name.strip().split())
    # Convert the name to title case
    normalized_name = cleaned_name.title()
    return normalized_name


def get_fernet() -> Fernet:
    """Build the Fernet used for profile and conversation tokens.

    Prefers a dedicated FERNET_KEY so the token key can be rotated without
    invalidating every session. Falls back to deriving one from SECRET_KEY,
    which is what older deployments used, so existing links keep working.
    """
    configured_key = getattr(settings, "FERNET_KEY", None)
    if configured_key:
        return Fernet(configured_key)

    key = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def decrypt_token(encoded_value: str) -> str | None:
    """Decrypt a Fernet token, returning None if it is absent or invalid."""
    if not encoded_value:
        return None
    try:
        f = get_fernet()
        return f.decrypt(encoded_value.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.exception("Token decryption failed")
        return None


def encrypt_token(original_value: str) -> str | None:
    """Encrypt a value into a Fernet token. Output is not deterministic."""
    if not original_value:
        return None
    try:
        f = get_fernet()
        return f.encrypt(str(original_value).encode("utf-8")).decode("utf-8")
    except Exception:
        logger.exception("Token encryption failed")
        return None


def encrypt_message(plaintext: str) -> str:
    """Encrypt a chat message for storage at rest.

    Uses the same Fernet as the tokens, so a stolen database holds only
    ciphertext. This is encryption at rest, not end to end: the server holds
    the key and can decrypt. An empty body is stored as-is.

    Note: because the message body is encrypted with the token key, rotating
    FERNET_KEY makes stored history unreadable. See docs/DEVELOPMENT.md.
    """
    if not plaintext:
        return plaintext
    f = get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_message(stored: str) -> str:
    """Decrypt a stored chat message.

    Returns the value unchanged if it is empty or cannot be decrypted, so a
    display path never raises on an unexpected value.
    """
    if not stored:
        return stored
    try:
        f = get_fernet()
        return f.decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        logger.exception("Message decryption failed")
        return stored


def generate_profile_qr(user_name, short_name, search_id):
    """
    Generate (or reuse) the QR code image for a user's profile link.

    The filename is keyed on user_name because it is unique and stable.
    It must not be keyed on encrypt_token output: Fernet embeds a timestamp
    and random IV, so the same input yields a different token every call, the
    on-disk cache never hits, and a fresh PNG is written on every request.

    Returns:
        str | None: the image filename, or None if the user has no profile ids.
    """
    if not short_name or not search_id or not user_name:
        return None

    # user_name is generated from a letters-only prefix plus digits, but strip
    # anything else defensively so it can never escape the qr directory.
    safe_user_name = re.sub(r"[^A-Za-z0-9_-]", "", str(user_name))
    if not safe_user_name:
        return None

    img_name = f"qr_{safe_user_name}.png"

    app_name = os.environ.get("APP_NAME", "orca2echo")
    qr_dir = os.path.join(settings.BASE_DIR, app_name, "static", "qr")
    qr_image_path = os.path.join(qr_dir, img_name)
    # Ensure the directory exists before checking for the file or saving
    os.makedirs(qr_dir, exist_ok=True)
    if os.path.exists(qr_image_path):
        return img_name

    enc_short_name = encrypt_token(short_name)
    enc_search_id = encrypt_token(search_id)

    host = os.environ.get("APP_URL", "")
    redirect_url = f"{host}/search-profile?short-name={enc_short_name}&id-number={enc_search_id}"

    # Generate the QR code image for the redirect_url
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(redirect_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img.save(qr_image_path)

    return img_name


def get_profile_share_context(user_name: str, request) -> dict:
    """Helper to generate profile QR and share URL for context."""
    profile = get_profile(user_name)
    img_name = generate_profile_qr(
        user_name,
        profile.short_name if profile else None,
        profile.search_id if profile else None,
    )
    if profile:
        _enc_sn = encrypt_token(str(profile.short_name or ""))
        _enc_si = encrypt_token(str(profile.search_id or ""))
        _host = request.build_absolute_uri("/").rstrip("/")
        profile_share_url = (
            f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
        )
    else:
        profile_share_url = ""

    return {
        "img_name": img_name,
        "profile_share_url": profile_share_url,
    }
