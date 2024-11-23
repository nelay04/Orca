from django.shortcuts import render, HttpResponse, redirect  # type: ignore
import requests
from django.core.mail import send_mail  # type: ignore
from .models import Otp
import sys
from django.contrib.auth.decorators import login_required, user_passes_test  # type: ignore
from django.contrib.auth import authenticate, login, logout  # type: ignore
from .models import UserData, UserProfile, FriendRequestList
from datetime import datetime
import re

# from .models import  User
from django.contrib.auth.models import User  # type: ignore
import time
from django.core.exceptions import ValidationError  # type: ignore
from django.core.validators import validate_email  # type: ignore
from django.http import Http404  # type: ignore
from .services.auth_service import (
    generate_otp,
    send_otp,
    generate_username,
    get_demo_img_text,
    generate_nanoseconds,
    generate_search_id,
    generate_short_name,
    normalize_full_name,
    get_oops_img_text,
    decrypt,
    get_current_time_ist,
)
from .services.model_service import (
    get_user_by_email,
    retrieve_otp,
    add_otp,
    get_user_by_username,
    delete_otp_by_email,
)
from .services.mongo_service import (
    update_fields_by_email,
    get_user_data_by_email,
    get_user_data_by_user_name,
    update_fields_by_user_name,
    find_an_object,
)

# Create your views here.


@login_required(login_url="signin")
def index(request):
    user_name = request.user.username
    user_data = get_user_data_by_user_name(
        collection_name="user_profile",
        user_name=user_name,
    )
    base64_string = user_data.get("profile_picture")
    # Render the page and pass the user to the template
    name = get_user_data_by_user_name(
        collection_name="user_data",
        user_name=user_name,
    )
    # print(user_name)
    full_name = name.get("full_name")

    request.session["base64_string"] = base64_string
    request.session["full_name"] = full_name

    return render(
        request,
        "index.html",
        {"auth_user": request.user, "base64_image": base64_string, "name": full_name},
    )


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
    if request.user.is_authenticated:
        # Redirect to a different page (e.g., home or dashboard)
        return redirect("orca")
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
                    return HttpResponse(
                        "You're a superuser. login in admin page to automatically login here"
                    )  # Response for superuser

                # Update the password to OTP if the user exists
                if_user.set_password(
                    otp
                )  # `set_password` method will hash the password (OTP in this case)
                if_user.save()  # Save the updated user
                add_otp(email, otp)
                username = if_user.username

                # Save OTP and ID in session
                request.session["email"] = email
                request.session["username"] = username

                # Redirect to OTP page or render the OTP template
                return render(request, "otp.html")

            else:
                # Generate username for new user
                nanoseconds = generate_nanoseconds()
                search_id = generate_search_id(nanoseconds)
                username = generate_username(email, nanoseconds)

                # Add a new user if not found
                new_user = User.objects.create_user(
                    username=username, email=email, password=otp
                )
                new_user.save()
                add_otp(email, otp)

                # Mongo user_data table
                new_user_obj = UserData(email=email)
                result = new_user_obj.save()
                new_profile_picture_object = UserProfile(user_name=username)
                result = new_profile_picture_object.save()

                # Save OTP and ID in session
                request.session["email"] = email
                request.session["username"] = username
                request.session["search_id"] = search_id

                # Redirect to OTP page or render the OTP template
                return render(request, "otp.html")
        except Exception as e:
            # Print error message for debugging
            return render(request, "signin.html", {"error": "An error occurred."})
    else:
        return render(request, "signin.html")


def verify_otp(request):
    if request.user.is_authenticated:
        # Redirect to a different page (e.g., home or dashboard)
        return redirect("orca")
    if request.method == "POST":
        entered_otp = request.POST.get("otp")  # Get OTP entered by the user
        email = request.session.get("email")  # Retrieve the user ID from session
        username = request.session.get("username")  # Retrieve the user ID from session
        original_otp = retrieve_otp(email)
        # sys.exit()

        if entered_otp == str(original_otp):
            # OTP is correct, proceed with logging in
            delete_otp_by_email(email)
            user = get_user_data_by_email(collection_name="user_data", email=email)

            if user.get("is_new_user"):
                request.session["original_otp"] = original_otp
                # Redirect to OTP page or render the OTP template
                return render(request, "signup.html")  # Redirect to the home page
            else:
                auth_user = authenticate(
                    request, username=username, password=original_otp, email=email
                )  # Create User instance
                login(request, auth_user)
                # Check if session variables exist before deleting
                if "email" in request.session:
                    del request.session["email"]

                if "username" in request.session:
                    del request.session["username"]

                return redirect("orca")  # Redirect to the home page

        else:
            error_message = "Invalid OTP"
            return render(request, "otp.html", {"error_message": error_message})

    else:
        return redirect("signin")


# Log out the user and redirect to the signin page
def user_logout(request):
    logout(request)  # This will log out the user
    return redirect("signin")  # Redirect to the signin page


def signup(request):
    if request.method == "POST":
        email = request.session.get("email")  # Retrieve the user data from session
        username = request.session.get("username")
        search_id = request.session.get("search_id")
        original_otp = request.session.get("original_otp")

        full_name = request.POST.get("full_name")
        gender = request.POST.get("gender")
        dob = request.POST.get("dob")
        # Validate `full_name`
        if not full_name:
            return render(request, "signup.html", {"error": "Full name is required."})

        if not re.match(r"^[A-Za-z ]+$", full_name):
            return render(
                request,
                "signup.html",
                {"error": "Name must only contain letters (A-Z or a-z) and spaces."},
            )

        if len(full_name) < 2:
            return render(
                request,
                "signup.html",
                {"error": "Full name must be at least 2 characters long."},
            )
        if not full_name.replace(" ", "").isalpha():
            return render(
                request,
                "signup.html",
                {"error": "Full name should only contain alphabets."},
            )

        # Validate `gender`
        if not gender:
            return render(request, "signup.html", {"error": "Gender is required."})
        if gender not in ["male", "female", "other", "prefer_not_to_say"]:
            return render(
                request,
                "signup.html",
                {
                    "error": "Gender must be one of 'Male', 'Female','Other' or 'prefer not to say'."
                },
            )

        # Validate `dob` (Date of Birth)
        if not dob:
            return render(
                request, "signup.html", {"error": "Date of birth is required."}
            )
        try:
            # Assuming `dob` is in the format 'YYYY-MM-DD'
            dob_date = datetime.strptime(dob, "%Y-%m-%d")
            if dob_date > datetime.now():
                return render(
                    request,
                    "signup.html",
                    {"error": "Date of birth cannot be in the future."},
                )
        except ValueError:
            return render(
                request,
                "signup.html",
                {"error": "Invalid date of birth format. Use 'YYYY-MM-DD'."},
            )

        # If validation passes, proceed with your logic
        # Render the page or redirect as necessary
        normalized_full_name = normalize_full_name(full_name)
        short_name = generate_short_name(normalized_full_name)
        update_fields_by_email(
            collection_name="user_data",
            email=email,
            updates={
                "user_name": username,
                "full_name": normalized_full_name,
                "gender": gender,
                "dob": dob,
                "search_id": search_id,
                "short_name": short_name,
                "is_new_user": False,
            },
        )

        demo_img_text = get_demo_img_text(gender)
        result_id = update_fields_by_user_name(
            collection_name="user_profile",
            user_name=username,
            updates={"profile_picture": demo_img_text},
        )

        auth_user = authenticate(
            request, username=username, password=original_otp, email=email
        )  # Create User instance
        login(request, auth_user)
        # Check if session variables exist before deleting
        if "email" in request.session:
            del request.session["email"]

        if "username" in request.session:
            del request.session["username"]

        if "original_otp" in request.session:
            del request.session["original_otp"]
        return redirect("orca")  # Redirect to the home page
    else:
        return redirect("signin")


@login_required(login_url="signin")
def add_friend(request):
    base64_string = request.session.get(
        "base64_string"
    )  # Retrieve the user ID from session
    full_name = request.session.get("full_name")  # Retrieve the user ID from session

    if request.method == "POST":
        receiver_short_name_enc = request.POST.get("short_name_enc")
        receiver_id_number_enc = request.POST.get("id_number_enc")
        receiver_short_name = decrypt(receiver_short_name_enc)
        receiver_id_number = decrypt(receiver_id_number_enc)
        searched_receiver_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": receiver_short_name,
                "search_id": receiver_id_number,
            },
        )
        user_name_receiver = searched_receiver_data.get("user_name")
        searched_receiver_profile_data = get_user_data_by_user_name(
            collection_name="user_profile",
            user_name=user_name_receiver,
        )

        current_time = get_current_time_ist()
        new_request_object = FriendRequestList(
            user_name_sender=request.user.username,
            user_name_receiver=user_name_receiver,
            request_time=current_time,
        )
        result = new_request_object.save()

        searched_base64_string = searched_receiver_profile_data.get("profile_picture")
        searched_about = searched_receiver_profile_data.get("about")
        searched_name = searched_receiver_data.get("full_name")
        searched_gender = searched_receiver_data.get("gender")
        if searched_gender == "male":
            gender_icon_string = "fa-mars"
        elif searched_gender == "female":
            gender_icon_string = "fa-venus"
        else:
            gender_icon_string = "fa-mars-and-venus"


        return render(
            request,
            "profile_card.html",
            {
                "auth_user": request.user,
                "base64_image": base64_string,
                "name": full_name,
                "btn_text": "Cancel Request",
                "btn_color": "#f50100",
                "searched_base64_string": searched_base64_string,
                "searched_about": searched_about,
                "searched_name": searched_name,
                "gender_icon_string": gender_icon_string,
                "its_me": "",
                "short_name_enc": receiver_short_name_enc,
                "id_number_enc": receiver_id_number_enc,
            },
        )
    else:
        return render(
            request,
            "add_friend.html",
            {
                "auth_user": request.user,
                "base64_image": base64_string,
                "name": full_name,
            },
        )


@login_required(login_url="signin")
def search_profile(request):
    if request.method == "GET":
        short_name_enc = request.GET.get("short-name", "").strip()
        id_number_enc = request.GET.get("id-number", "").strip()
        short_name = decrypt(short_name_enc)
        id_number = decrypt(id_number_enc)

        base64_string = request.session.get(
            "base64_string"
        )  # Retrieve the user ID from session
        full_name = request.session.get(
            "full_name"
        )  # Retrieve the user ID from session

        # searched_user_data = get_profile_card(short_name, id_number)
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": short_name,
                "search_id": id_number,
            },
        )

        oops_string = get_oops_img_text("oops")
        oops_dark_string = get_oops_img_text("oops_dark")
        if searched_user_data is None:
            return render(
                request,
                "profile_card.html",
                {
                    "auth_user": request.user,
                    "base64_image": base64_string,
                    "name": full_name,
                    "oops_string": oops_string,
                    "oops_dark_string": oops_dark_string,
                },
            )

        searched_name = searched_user_data.get("full_name")
        its_me = request.user.username == searched_user_data.get("user_name")

        searched_user_profile_data = get_user_data_by_user_name(
            collection_name="user_profile",
            user_name=searched_user_data.get("user_name"),
        )

        searched_user_profile_data = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": searched_user_data.get("user_name"),
            },
        )
        searched_base64_string = searched_user_profile_data.get("profile_picture")
        searched_about = searched_user_profile_data.get("about")
        searched_gender = searched_user_data.get("gender")
        if searched_gender == "male":
            gender_icon_string = "fa-mars"
        elif searched_gender == "female":
            gender_icon_string = "fa-venus"
        else:
            gender_icon_string = "fa-mars-and-venus"

        #check if sent request is already active
        if_friend_request = find_an_object(
            collection_name="friend_request_list",
            search_criteria={
                "user_name_sender": request.user.username,
                "user_name_receiver": searched_user_data.get("user_name"),
            },
        )
        if if_friend_request:
            if if_friend_request.get("is_active") is True:
                btn_text = "Cancel request"
                btn_color = "#f50100"
                action = "/cancel-request"
        else:
            btn_text = "Add Friend"
            btn_color = "#766bc9"
            action = "/add-friend"

        return render(
            request,
            "profile_card.html",
            {
                "auth_user": request.user,
                "base64_image": base64_string,
                "name": full_name,
                "btn_text": btn_text,
                "btn_color": btn_color,
                "action": action,
                "searched_base64_string": searched_base64_string,
                "searched_about": searched_about,
                "searched_name": searched_name,
                "gender_icon_string": gender_icon_string,
                "its_me": its_me,
                "short_name_enc": short_name_enc,
                "id_number_enc": id_number_enc,
            },
        )


@login_required(login_url="signin")
def cancel_request(request):
    return HttpResponse(
    "Cancel Request"
    )  # Response for superuser