from django.shortcuts import render
from django.shortcuts import render, HttpResponse, redirect
import requests
from django.core.mail import send_mail
from .services.auth_service import generate_otp,send_otp
from .models import  User
import time    
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
# Create your views here.
def index(request):
    return render(request, "signin.html", {"auth_user": request.user})


def mobile_only(request):
    return render(
        request, "mobile_only.html"
    )  # Display a page with the mobile-only message



def signin(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # Validate the email format using Django's EmailValidator
        try:
            validate_email(email)
        except ValidationError:
            return render(request, "signin.html", {
                "error": "Please enter a valid email address."  # Error message to show in the template
            })

        # Generate and print OTP for debugging (remove this in production)
        otp = generate_otp()
        print(otp)

        # Send OTP to email
        send_otp(otp, email)

        try:
            # Check if user exists
            if_user = User.get_user_by_email(email)
            if if_user is not None:
                # Update user's OTP if user already exists
                result = User.update_field(email, "otp", otp)
            else:
                # Add a new user if not found
                new_user = User(email=email, otp=otp)
                result = new_user.save()
        except Exception as e:
            # Print error message for debugging
            print(f"An error occurred: {e}")
            return render(request, "signin.html", {"error": "An unexpected error occurred."})

        # Save OTP and ID in session
        request.session['otp'] = otp
        request.session['id'] = str(result)  # Assuming `result` is the user's ID or a unique identifier

        # Redirect to OTP page or render the OTP template
        return render(request, "otp.html", {"otp": otp, "id": result})
    else:
        return render(request, "signin.html")
    

def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')  # Retrieve the concatenated OTP value from the hidden input
        print(entered_otp)
        # Retrieve data from session
        original_otp = request.session.get('otp')
        user_id = request.session.get('id')

        # Validate OTP
        if entered_otp == original_otp:
            # Proceed with verification
            # Optionally, clear sensitive session data
            del request.session['otp']
            del request.session['id']
            return HttpResponse("OTP verified successfully.")
        else:
            return HttpResponse("Invalid OTP.")
