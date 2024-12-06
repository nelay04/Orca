"""Service for user authentication -> sqlite"""

import random
from django.core.mail import send_mail  # type: ignore
from django.template.loader import render_to_string  # type: ignore
from django.utils.html import strip_tags  # type: ignore
from datetime import datetime
import time
import os
from django.conf import settings  # type: ignore
import base64
import pytz # type: ignore
import re
from .mongo_service import (
    find_an_object,
)


def auth_user_data(request):
    try:
        if "full_name" not in request.session or "base64_string" not in request.session:
            print("no data in session session")
            user_name = request.user.username
            user_data = find_an_object(
                collection_name="user_profile",
                search_criteria={"user_name": user_name},
            )
            base64_string = user_data.get("profile_picture")
            # Render the page and pass the user to the template
            name = find_an_object(
                collection_name="user_data",
                search_criteria={"user_name": user_name},
            )
            full_name = name.get("full_name")
            request.session["base64_string"] = base64_string
            request.session["full_name"] = full_name
        else:
            print("retrieving from session")
            base64_string = request.session.get("base64_string")
            full_name = request.session.get("full_name")

        auth_user_info = {
            "auth_user": request.user,
            "base64_image": base64_string,
            "name": full_name,
        }
        return auth_user_info
    except Exception as e:
        return None
    
    
def generate_otp():
    # Generate a 6-digit random OTP between 000000 and 999999
    otp = random.randint(111111, 999999)
    return f"{otp:06d}"  # Formats the number to be 6 digits with leading zeros




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
    formatted_time = current_time.strftime("%d-%m-%Y %H:%M:%S:") + str(current_time.microsecond // 1000).zfill(3)
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
        "name":name,
        "otp": otp,
        "brand_name": "Orca",
        "dated": get_current_time_ist(),
        "address_line1": "123 Elf Road, 88888",
        "address_line2": "North Pole",
    }

    # Render the HTML template
    html_message = render_to_string("otp_email_template.html", context)
    plain_message = strip_tags(html_message)  # Generate plain text version if needed

    send_mail(
        "Orca",  # Subject of the email
        plain_message,  # Plain text content (optional fallback)
        "snowflake.2k04@gmail.com",  # Sender's email address
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
    print(username)
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
    print(file_path)
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


def base64_decrypt(encoded_value):
    try:
        # First Base64 decoding (URL-safe)
        first_decode = base64.urlsafe_b64decode(
            encoded_value + "=" * (-len(encoded_value) % 4)
        ).decode("utf-8")
        # Second Base64 decoding (URL-safe)
        second_decode = base64.urlsafe_b64decode(
            first_decode + "=" * (-len(first_decode) % 4)
        ).decode("utf-8")
        return second_decode
    except Exception as e:
        print(f"Decoding failed: {e}")
        return None


def base64_encrypt(original_value):
    try:
        # First Base64 encoding (URL-safe)
        first_encode = base64.urlsafe_b64encode(original_value.encode("utf-8")).decode("utf-8").rstrip("=")
        # Second Base64 encoding (URL-safe)
        second_encode = base64.urlsafe_b64encode(first_encode.encode("utf-8")).decode("utf-8").rstrip("=")
        return second_encode
    except Exception as e:
        print(f"Encoding failed: {e}")
        return None
