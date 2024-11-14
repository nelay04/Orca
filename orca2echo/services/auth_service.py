import random
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime

def generate_otp():
    # Generate a 6-digit random OTP between 000000 and 999999
    otp = random.randint(0, 999999)
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
    username_prefix = email.split('@')[0]

    # Step 2: Get the current time formatted as YYYYMMDDHHMMSS
    current_time = datetime.now().strftime('%Y%m%d%H%M%S')

    # Step 3: Combine the prefix and current time to form the username
    username = f"{username_prefix}{current_time}"

    return username