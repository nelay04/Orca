"""Service for user authentication -> sqlite"""

import random
from django.core.mail import send_mail  # type: ignore
from django.template.loader import render_to_string  # type: ignore
from django.utils.html import strip_tags  # type: ignore
from datetime import datetime
import time
import os
from django.conf import settings


def generate_otp():
    # Generate a 6-digit random OTP between 000000 and 999999
    otp = random.randint(111111, 999999)
    return f"{otp:06d}"  # Formats the number to be 6 digits with leading zeros


def send_otp(otp, email):
    # Define the context for rendering the template
    context = {
        "otp": otp,
        "brand_name": "Orca",
        "address_line1": "123 Elf Road, 88888",
        "address_line2": "North Pole",
    }

    # Render the HTML template
    html_message = render_to_string("otp_email_template.html", context)
    plain_message = strip_tags(html_message)  # Generate plain text version if needed

    send_mail(
        otp,  # Subject of the email
        plain_message,  # Plain text content (optional fallback)
        "coffeecold97@gmail.com",  # Sender's email address
        [email],  # List of recipient email addresses
        fail_silently=False,
        html_message=html_message,  # HTML content of the email
    )


def generate_username(email):
    # Step 1: Extract the part before '@' from the email
    username_prefix = email.split("@")[0]

    # Step 2: Get the current time formatted as YYYYMMDDHHMMSS
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")

    # Step 3: Add nanoseconds for even finer granularity
    nanoseconds = int(time.time_ns() % 1_000_000_000)  # Get the current nanoseconds

    # Step 4: Combine the prefix, current time, and nanoseconds to form the username
    username = f"{username_prefix}{current_time}{nanoseconds}"

    return username


def get_demo_img_text():
    # Construct the file path for 'demo_profile_img.txt' in the media folder
    file_path = os.path.join(settings.MEDIA_ROOT, "demo_profile_img.txt")

    # Read the content of the text file
    try:
        with open(file_path, "r") as file:
            file_content = (
                file.read()
            )  # Store the content in the variable 'file_content'
            return file_content
    except FileNotFoundError:
        return "File not found."
