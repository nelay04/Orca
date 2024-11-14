from django.shortcuts import render, HttpResponse, redirect
import requests
from django.core.mail import send_mail
from .models import Otp
import sys
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout

# from .models import  User
from django.contrib.auth.models import User
import time
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from .services.auth_service import generate_otp, send_otp, generate_username
from .services.model_service import (
    get_user_by_email,
    retrieve_otp,
    add_otp,
    get_user_by_username,
    delete_otp_by_email,
)


# Create your views here.

@login_required(login_url="signin")
def index(request):
    # Render the page and pass the user to the template
    return render(request, "index.html", {"auth_user": request.user})


def mobile_only(request):
    return render(
        request,
        "error.html",
        {
            "error_code": "403",
            "error_header": "Error 403 - Forbidden",
            "error_body": "This website is only available on mobile devices.",
        },
    )


def signin(request):
    if request.method == "POST":
        email = request.POST.get("email")

        if not email:  # Check if email is not provided
            return render(request, "signin.html", {"error": "Email is required."})

        # Validate the email format using Django's EmailValidator
        try:
            validate_email(email)  # Validate email format
        except ValidationError:
            return render(
                request, "signin.html", {"error": "Please enter a valid email address."}
            )

        # Generate OTP
        otp = generate_otp()
        # print(otp)

        # Send OTP to email
        send_otp(otp, email)

        try:
            # Check if user exists
            if_user = get_user_by_email(email)

            if if_user is not None:
                # Check if the user is a superuser
                if if_user.is_superuser:
                    return HttpResponse("You're a superuser. login in admin page to automatically login here")  # Response for superuser

                # Update the password to OTP if the user exists
                if_user.set_password(
                    otp
                )  # `set_password` method will hash the password (OTP in this case)
                if_user.save()  # Save the updated user
                add_otp(email, otp)
                username = if_user.username
            else:
                # Generate username for new user
                username = generate_username(email)
                # Add a new user if not found
                new_user = User.objects.create_user(
                    username=username, email=email, password=otp
                )
                new_user.save()
                add_otp(email, otp)

        except Exception as e:
            # Print error message for debugging
            return render(request, "signin.html", {"error": "An error occurred."})

        # Save OTP and ID in session
        request.session["email"] = email
        request.session["username"] = username

        # Redirect to OTP page or render the OTP template
        return render(request, "otp.html")
    else:
        return render(request, "signin.html")


def verify_otp(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp")  # Get OTP entered by the user
        email = request.session.get("email")  # Retrieve the user ID from session
        username = request.session.get("username")  # Retrieve the user ID from session
        original_otp = retrieve_otp(email)
        # sys.exit()

        if entered_otp == str(original_otp):
            # OTP is correct, proceed with logging in
            auth_user = authenticate(
                request, username=username, password=original_otp, email=email
            )  # Create User instance
            login(request, auth_user)
            delete_otp_by_email(email)

            # Example of deleting a specific session variable
            del request.session["email"]
            del request.session["username"]
            return redirect("orca")  # Redirect to the home page
        else:
            error_message = "Invalid OTP"
            return render(request, "otp.html", {"error_message": error_message})

    else:
        return render(
            request,
            "error.html",
            {
                "error_code": "404",
                "error_header": "Error 404 - Not Found",
                # "error_body": "This website is only available on mobile devices.",
            },
        )


# Log out the user and redirect to the signin page
def user_logout(request):
    logout(request)  # This will log out the user
    return redirect("signin")  # Redirect to the signin page
