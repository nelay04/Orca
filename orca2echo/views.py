# Standard Library Imports
from django.http import HttpResponse, HttpResponseBadRequest  # type: ignore
import json
import re
# import sys
# import time
from datetime import datetime

# Third-Party Library Imports
# import requests
from django.contrib.auth import authenticate, login, logout  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore
# from django.core.mail import send_mail  # type: ignore
from django.core.validators import validate_email  # type: ignore
# from django.http import Http404  # type: ignore
from django.shortcuts import redirect, render  # type: ignore
from django.urls import reverse  # type: ignore

# Local App Imports - Models
from .models import FriendRequestList, UserData, UserProfile, FriendList, Conversation
# from .models import Otp

# Local App Imports - Services
from .services.auth_service import (
    auth_user_data,
    base64_decrypt,
    base64_encrypt,
    generate_nanoseconds,
    generate_otp,
    generate_search_id,
    generate_short_name,
    generate_username,
    get_current_time_ist,
    get_demo_img_text,
    get_oops_img_text,
    normalize_full_name,
    send_otp,
    extract_first_name,
    generate_profile_qr,
)
from .services.model_service import (
    add_otp,
    delete_otp_by_email,
    get_user_by_email,
    # get_user_by_username,
    retrieve_otp,
)
from .services.mongo_service import (
    find_all_objects,
    find_an_object,
    get_user_data_by_email,
    update_fields_by_email,
    update_fields_by_user_name,
    update_objects,
    find_friendship,
    find_friend_users_alphabetically_sorted,
    find_friend_users_sorted_by_updated_at,
    get_conversation_by_id,
    get_conversation_id_for_friendship,
    get_friend_id_by_conversation,
    get_latest_conversation
)


# Create your views here.

@login_required(login_url="signin")
def index(request):

    # Fetch all friends for the logged-in user
    friends = find_friend_users_sorted_by_updated_at(request.user.username)

    friends_data = []
    # Loop through all the friend requests to gather user data and profile information
    for friend in friends:
        # Fetch user data for the sender of the friend request
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "user_name": friend['user_name']},
        )
        # Fetch user profile for the sender of the friend request
        searched_user_profile = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": friend['user_name']},
        )

        # If both user data and profile are found, append to the result list
        if searched_user_data and searched_user_profile:
            _latest = get_latest_conversation(request.user.username, searched_user_data["user_name"])
            latest_conversation_message, is_sender = _latest if _latest is not None else (None, False)
            friends_data.append(
                {
                    "user_data": {
                        "_id": str(
                            searched_user_data["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        # "user_name": searched_user_data["user_name"],
                        "full_name": searched_user_data["full_name"],
                        "latest_conversation_message": latest_conversation_message,
                        "is_sender": is_sender,
                        "encrypted_conversation_id": base64_encrypt(get_conversation_id_for_friendship(request.user.username, searched_user_data["user_name"]))
                    },
                    "user_profile": {
                        "profile_picture": searched_user_profile["profile_picture"],
                    },
                }
            )
    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    # Fetch user data for the sender of the friend request
    user_data = find_an_object(
        collection_name="user_data",
        search_criteria={
            "user_name": request.user.username},
    )
    img_name = generate_profile_qr(
        user_data.get("short_name") if user_data else None,
        user_data.get("search_id") if user_data else None,
    )
    if user_data:
        _enc_sn = base64_encrypt(user_data.get("short_name", ""))
        _enc_si = base64_encrypt(user_data.get("search_id", ""))
        _host = request.build_absolute_uri('/').rstrip('/')
        profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
    else:
        profile_share_url = ""

    context = {
        "friends_data": friends_data,
        "auth_user_info": auth_user_info,
        "img_name": img_name,
        "profile_share_url": profile_share_url,
    }
    auth_user_info = auth_user_data(request)

    return render(
        request,
        "index.html",
        context,
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
                request, "signin.html", {
                    "error": "Please enter a valid email address."}
            )

        # Find out name if available from mongodb
        name = "user"
        try:
            searched_user_data = find_an_object(
                collection_name="user_data",
                search_criteria={
                    "email": email,
                },
            )
            if searched_user_data:
                name = searched_user_data.get("full_name")
                # add a space before name
                name = " " + extract_first_name(name)
        except Exception as e:
            print(f"Error in finding user data from MongoDB: {e}")  # Debugging print statement
            name = "user"

        print(f"Email: {email}, Name: {name}")  # Debugging print statement
        # Generate OTP
        otp = generate_otp()

        # Send OTP to email
        send_otp(otp, email, name)

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
                    # `set_password` method will hash the password (OTP in this case)
                )
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
                new_user_obj.save()
                new_profile_picture_object = UserProfile(user_name=username)
                new_profile_picture_object.save()

                # Save OTP and ID in session
                request.session["email"] = email
                request.session["username"] = username
                request.session["search_id"] = search_id

                # Redirect to OTP page or render the OTP template
                return render(request, "otp.html")
        except Exception as e:
            # Print error message for debugging
            print(f"Error: {e}")
            return render(request, "signin.html", {"error": "An error occurred."})
    else:
        return render(request, "signin.html")


def verify_otp(request):
    if request.user.is_authenticated:
        # Redirect to a different page (e.g., home or dashboard)
        return redirect("orca")
    if request.method == "POST":
        entered_otp = request.POST.get("otp")  # Get OTP entered by the user
        # Retrieve the user ID from session
        email = request.session.get("email")
        # Retrieve the user ID from session
        username = request.session.get("username")
        original_otp = retrieve_otp(email)
        # sys.exit()

        if entered_otp == str(original_otp):
            # OTP is correct, proceed with logging in
            delete_otp_by_email(email)
            user = get_user_data_by_email(
                collection_name="user_data", email=email)

            if user is None or user.get("is_new_user"):
                request.session["original_otp"] = original_otp
                # Redirect to OTP page or render the OTP template
                # Redirect to the home page
                return render(request, "signup.html")
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
        # Retrieve the user data from session
        email = request.session.get("email")
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
        update_fields_by_user_name(
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
    # get user data
    auth_user_info = auth_user_data(request)

    # Handle add friend post request here
    if request.method == "POST":
        # get receiver data and decrypt
        receiver_short_name_enc = request.POST.get("short_name_enc")
        receiver_id_number_enc = request.POST.get("id_number_enc")
        receiver_short_name = base64_decrypt(receiver_short_name_enc)
        receiver_id_number = base64_decrypt(receiver_id_number_enc)

        # get receiver data from user_data table
        searched_receiver_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": receiver_short_name,
                "search_id": receiver_id_number,
            },
        )

        if searched_receiver_data is None:
            return redirect(reverse('orca'))

        # get friend request data from friend_request_list table
        user_name_receiver = searched_receiver_data.get("user_name")
        if_friend_request = find_an_object(
            collection_name="friend_request_list",
            search_criteria={
                "user_name_sender": request.user.username,
                "user_name_receiver": searched_receiver_data.get("user_name"),
            },
        )

        # check if there is inactive request then activate that request
        if if_friend_request:
            if if_friend_request.get("is_active") is False:
                update_objects(
                    collection_name="friend_request_list",
                    search_criteria={
                        "user_name_sender": request.user.username,
                        "user_name_receiver": user_name_receiver,
                    },
                    update_data={
                        "is_active": True,
                        "is_cancelled": False,
                        "is_declined": False,
                        "request_time": get_current_time_ist(),
                        "request_count": int(if_friend_request.get("request_count"))
                        + 1,
                    },
                )
        else:
            # if there is no active request already create a new request
            new_request_object = FriendRequestList(
                user_name_sender=request.user.username,
                user_name_receiver=user_name_receiver,
                request_time=get_current_time_ist(),
                request_count=1,
            )
            new_request_object.save()

        # redirect to profile card page
        redirect_url = reverse('search-profile') + f'?short-name={
            receiver_short_name_enc}&id-number={receiver_id_number_enc}'
        response = redirect(redirect_url)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    else:
        # Search-for-user form
        cur_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={"user_name": request.user.username},
        )
        img_name = generate_profile_qr(
            cur_user_data.get("short_name") if cur_user_data else None,
            cur_user_data.get("search_id") if cur_user_data else None,
        )
        if cur_user_data:
            _enc_sn = base64_encrypt(cur_user_data.get("short_name", ""))
            _enc_si = base64_encrypt(cur_user_data.get("search_id", ""))
            _host = request.build_absolute_uri('/').rstrip('/')
            profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
        else:
            profile_share_url = ""
        return render(
            request,
            "add_friend.html",
            {
                "auth_user_info": auth_user_info,
                "img_name": img_name,
                "profile_share_url": profile_share_url,
            },
        )


@login_required(login_url="signin")
def search_profile(request):
    # handle profile card view
    if request.method == "GET":
        # get cncrypted short-name and id-number and decrypt
        short_name_enc = request.GET.get("short-name", "").strip()
        id_number_enc = request.GET.get("id-number", "").strip()
        short_name = base64_decrypt(short_name_enc)
        id_number = base64_decrypt(id_number_enc)

        # get user data
        auth_user_info = auth_user_data(request)

        # fetch current user's data for QR / share link
        cur_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={"user_name": request.user.username},
        )
        img_name = generate_profile_qr(
            cur_user_data.get("short_name") if cur_user_data else None,
            cur_user_data.get("search_id") if cur_user_data else None,
        )
        if cur_user_data:
            _enc_sn = base64_encrypt(cur_user_data.get("short_name", ""))
            _enc_si = base64_encrypt(cur_user_data.get("search_id", ""))
            _host = request.build_absolute_uri('/').rstrip('/')
            profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
        else:
            profile_share_url = ""

        # get receiver data from user_data table
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": short_name,
                "search_id": id_number,
            },
        )

        # image string for user not found
        oops_string = get_oops_img_text("oops")
        oops_dark_string = get_oops_img_text("oops_dark")

        # if user is not found then return
        if searched_user_data is None:
            return render(
                request,
                "profile_card.html",
                {
                    "auth_user_info": auth_user_info,
                    "oops_string": oops_string,
                    "oops_dark_string": oops_dark_string,
                    "img_name": img_name,
                    "profile_share_url": profile_share_url,
                },
            )

        # name of searched user
        searched_name = searched_user_data.get("full_name")

        # identfy if user is searching himself then hide action buttons.
        its_me = request.user.username == searched_user_data.get("user_name")

        # get profile data from user_data table
        searched_user_profile_data = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": searched_user_data.get("user_name"),
            },
        )
        # Profile image base64 string, about, gender of searched user
        searched_base64_string = searched_user_profile_data.get(
            "profile_picture")
        searched_about = searched_user_profile_data.get("about")
        searched_gender = searched_user_data.get("gender")

        # show icon in profile card according to gender
        if searched_gender == "male":
            gender_icon_string = "fa-mars"
        elif searched_gender == "female":
            gender_icon_string = "fa-venus"
        else:
            gender_icon_string = "fa-mars-and-venus"

        # check current relation with searched user
        if_friend_request = find_an_object(
            collection_name="friend_request_list",
            search_criteria={
                "user_name_sender": request.user.username,
                "user_name_receiver": searched_user_data.get("user_name"),
            },
        )

        # check current relation with searched user
        if_friends_reverse = find_an_object(
            collection_name="friend_request_list",
            search_criteria={
                "user_name_sender": searched_user_data.get("user_name"),
                "user_name_receiver": request.user.username,
            },
        )

        if if_friends_reverse:
            if if_friends_reverse.get("is_accepted") is True:
                btn_text = "You're Friends"
                btn_color = "#00e800"
                action = "/"
        else:
            # if request object is available
            if if_friend_request:
                if if_friend_request.get("is_accepted") is True:
                    btn_text = "You're Friends"
                    btn_color = "#00e800"
                    action = "/"
                # if request object is not available then allow to cancel request
                elif if_friend_request.get("is_active") is True:
                    btn_text = "Cancel Request"
                    btn_color = "#f50100"
                    action = "/cancel-request"
                else:
                    btn_text = "Add Friend"
                    btn_color = "#766bc9"
                    action = "/add-friend"
            # if request object is not available then allow to add friend
            else:
                btn_text = "Add Friend"
                btn_color = "#766bc9"
                action = "/add-friend"

        # show profile card accourding to current relation and allowed action
        return render(
            request,
            "profile_card.html",
            {
                "auth_user_info": auth_user_info,
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
                "img_name": img_name,
                "profile_share_url": profile_share_url,
            },
        )


@login_required(login_url="signin")
def cancel_request(request):
    # handle cancel friend request
    if request.method == "POST":

        from_sent_request = request.POST.get("from_sent_request")

        if from_sent_request == '0':
            # get cncrypted short-name and id-number and decrypt
            receiver_short_name_enc = request.POST.get("short_name_enc")
            receiver_id_number_enc = request.POST.get("id_number_enc")
            receiver_short_name = base64_decrypt(receiver_short_name_enc)
            receiver_id_number = base64_decrypt(receiver_id_number_enc)
            # show profile card accourding to current relation and allowed action
            redirect_url = reverse('search-profile') + f'?short-name={
                receiver_short_name_enc}&id-number={receiver_id_number_enc}'
        elif from_sent_request == '1':
            receiver_short_name = request.POST.get("short_name_enc")
            receiver_id_number = request.POST.get("id_number_enc")
            # show profile card accourding to current relation and allowed action
            redirect_url = reverse('sent-requests')

        # get current user data
        auth_user_data(request)

        # get receiver data from user_data table
        searched_receiver_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "short_name": receiver_short_name,
                "search_id": receiver_id_number,
            },
        )

        if searched_receiver_data is None:
            return redirect(reverse('orca'))

        # get request object data
        if_friend_request = find_an_object(
            collection_name="friend_request_list",
            search_criteria={
                "user_name_sender": request.user.username,
                "user_name_receiver": searched_receiver_data.get("user_name"),
            },
        )

        # check if request data object is available
        if if_friend_request:
            # check if request is active
            if if_friend_request.get("is_active") is True:
                # deactivate status and cancel request
                update_objects(
                    collection_name="friend_request_list",
                    search_criteria={
                        "user_name_sender": request.user.username,
                        "user_name_receiver": searched_receiver_data.get("user_name"),
                    },
                    update_data={
                        "is_active": False,
                        "is_cancelled": True,
                        "cancellation_time": get_current_time_ist(),
                        "cancellation_count": int(if_friend_request.get("cancellation_count"))
                        + 1,
                    },
                )

        # redirect
        response = redirect(redirect_url)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@login_required(login_url="signin")
def friend_requests(request):
    # Fetch all active friend requests for the logged-in user
    all_friend_request = find_all_objects(
        collection_name="friend_request_list",
        search_criteria={
            "user_name_receiver": request.user.username,
            "is_active": True,
        },
    )

    friend_request_data = []

    # Loop through all the friend requests to gather user data and profile information
    for friend_request in all_friend_request:
        # Fetch user data for the sender of the friend request
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "user_name": friend_request.get("user_name_sender")},
        )

        # Fetch user profile for the sender of the friend request
        searched_user_profile = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": friend_request.get("user_name_sender")},
        )

        # If both user data and profile are found, append to the result list
        if searched_user_data and searched_user_profile:
            # show icon in profile card according to gender
            if searched_user_data["gender"] == "male":
                gender_icon_string = "fa-mars"
            elif searched_user_data["gender"] == "female":
                gender_icon_string = "fa-venus"
            else:
                gender_icon_string = "fa-mars-and-venus"

            friend_request_data.append(
                {
                    "user_data": {
                        "_id": str(
                            searched_user_data["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "email": searched_user_data["email"],
                        "user_name": searched_user_data["user_name"],
                        "full_name": searched_user_data["full_name"],
                        "dob": searched_user_data["dob"],
                        "gender": searched_user_data["gender"],
                        "short_name": searched_user_data["short_name"],
                        "search_id": searched_user_data["search_id"],
                        "is_active": searched_user_data["is_active"],
                        "is_new_user": searched_user_data["is_new_user"],
                        "gender_icon_string": gender_icon_string,
                    },
                    "user_profile": {
                        "_id": str(
                            searched_user_profile["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "user_name": searched_user_profile["user_name"],
                        "profile_picture": searched_user_profile["profile_picture"],
                        "about": searched_user_profile["about"],
                        "qr_code": searched_user_profile["qr_code"],
                    },
                }
            )
    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    # Fetch user data for the sender of the friend request
    user_data = find_an_object(
        collection_name="user_data",
        search_criteria={
            "user_name": request.user.username},
    )
    img_name = generate_profile_qr(
        user_data.get("short_name") if user_data else None,
        user_data.get("search_id") if user_data else None,
    )
    if user_data:
        _enc_sn = base64_encrypt(user_data.get("short_name", ""))
        _enc_si = base64_encrypt(user_data.get("search_id", ""))
        _host = request.build_absolute_uri('/').rstrip('/')
        profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
    else:
        profile_share_url = ""

    context = {
        "friend_request_data": friend_request_data,
        # You can add a logic here to determine if the user is the sender of the request
        "its_me": False,
        "auth_user_info": auth_user_info,
        "img_name": img_name,
        "profile_share_url": profile_share_url,
    }
    return render(request, "friend_requests.html", context)


@login_required(login_url="signin")
def sent_requests(request):
    # Fetch all active friend requests for the logged-in user
    all_friend_request = find_all_objects(
        collection_name="friend_request_list",
        search_criteria={
            "user_name_sender": request.user.username,
            "is_active": True,
        },
    )

    friend_request_data = []

    # Loop through all the friend requests to gather user data and profile information
    for friend_request in all_friend_request:
        # Fetch user data for the sender of the friend request
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "user_name": friend_request.get("user_name_receiver")},
        )

        # Fetch user profile for the sender of the friend request
        searched_user_profile = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": friend_request.get("user_name_receiver")},
        )

        # If both user data and profile are found, append to the result list
        if searched_user_data and searched_user_profile:
            # show icon in profile card according to gender
            if searched_user_data["gender"] == "male":
                gender_icon_string = "fa-mars"
            elif searched_user_data["gender"] == "female":
                gender_icon_string = "fa-venus"
            else:
                gender_icon_string = "fa-mars-and-venus"
            friend_request_data.append(
                {
                    "user_data": {
                        "_id": str(
                            searched_user_data["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "email": searched_user_data["email"],
                        "user_name": searched_user_data["user_name"],
                        "full_name": searched_user_data["full_name"],
                        "dob": searched_user_data["dob"],
                        "gender": searched_user_data["gender"],
                        "short_name": searched_user_data["short_name"],
                        "search_id": searched_user_data["search_id"],
                        "is_active": searched_user_data["is_active"],
                        "is_new_user": searched_user_data["is_new_user"],
                        "gender_icon_string": gender_icon_string,
                    },
                    "user_profile": {
                        "_id": str(
                            searched_user_profile["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "user_name": searched_user_profile["user_name"],
                        "profile_picture": searched_user_profile["profile_picture"],
                        "about": searched_user_profile["about"],
                        "qr_code": searched_user_profile["qr_code"],
                    },
                }
            )
    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    # Fetch user data for the sender of the friend request
    user_data = find_an_object(
        collection_name="user_data",
        search_criteria={
            "user_name": request.user.username},
    )
    img_name = generate_profile_qr(
        user_data.get("short_name") if user_data else None,
        user_data.get("search_id") if user_data else None,
    )
    if user_data:
        _enc_sn = base64_encrypt(user_data.get("short_name", ""))
        _enc_si = base64_encrypt(user_data.get("search_id", ""))
        _host = request.build_absolute_uri('/').rstrip('/')
        profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
    else:
        profile_share_url = ""

    context = {
        "friend_request_data": friend_request_data,
        # You can add a logic here to determine if the user is the sender of the request
        "its_me": False,
        "auth_user_info": auth_user_info,
        "img_name": img_name,
        "profile_share_url": profile_share_url,
    }
    return render(request, "sent_requests.html", context)


@login_required(login_url="signin")
def response(request):
    # handle cancel friend request
    if request.method == "POST":
        response = request.POST.get('response')
        if response == 'decline':
            sender_short_name = request.POST.get("short_name_enc")
            sender_id_number = request.POST.get("id_number_enc")

            # get receiver data from user_data table
            searched_sender_data = find_an_object(
                collection_name="user_data",
                search_criteria={
                    "short_name": sender_short_name,
                    "search_id": sender_id_number,
                },
            )

            if searched_sender_data is None:
                return redirect(reverse('friend-requests'))

            # get request object data
            if_friend_request = find_an_object(
                collection_name="friend_request_list",
                search_criteria={
                    "user_name_sender": searched_sender_data.get("user_name"),
                    "user_name_receiver": request.user.username,
                },
            )

            # check if request data object is available
            if if_friend_request:
                # check if request is active
                if if_friend_request.get("is_active") is True:
                    # deactivate status and cancel request
                    update_objects(
                        collection_name="friend_request_list",
                        search_criteria={
                            "user_name_receiver": request.user.username,
                            "user_name_sender": searched_sender_data.get("user_name"),
                        },
                        update_data={
                            "is_active": False,
                            "is_declined": True,
                            "response_time": get_current_time_ist(),
                            "declination_count": int(if_friend_request.get("declination_count"))
                            + 1,
                        },
                    )

        elif response == 'accept':
            sender_short_name = request.POST.get("short_name_enc")
            sender_id_number = request.POST.get("id_number_enc")

            # get receiver data from user_data table
            searched_sender_data = find_an_object(
                collection_name="user_data",
                search_criteria={
                    "short_name": sender_short_name,
                    "search_id": sender_id_number,
                },
            )

            if searched_sender_data is None:
                return redirect(reverse('friend-requests'))

            # get request object data
            if_friend_request = find_an_object(
                collection_name="friend_request_list",
                search_criteria={
                    "user_name_sender": searched_sender_data.get("user_name"),
                    "user_name_receiver": request.user.username,
                },
            )

            # check if request data object is available
            if if_friend_request:
                # check if request is active
                if if_friend_request.get("is_active") is True:
                    # deactivate status and cancel request
                    update_objects(
                        collection_name="friend_request_list",
                        search_criteria={
                            "user_name_receiver": request.user.username,
                            "user_name_sender": searched_sender_data.get("user_name"),
                        },
                        update_data={
                            "is_active": False,
                            "is_accepted": True,
                            "response_time": get_current_time_ist(),
                            "acceptance_count": int(if_friend_request.get("acceptance_count"))
                            + 1,
                        },
                    )

            # check if friendship object is created already in friend_list collection
            friendship = find_friendship(
                request.user.username, searched_sender_data.get("user_name"))
            if not friendship:
                # if there is no active friend object create one
                new_friend = FriendList(
                    user_1=request.user.username,
                    user_2=searched_sender_data.get("user_name"),
                    created_at=get_current_time_ist(),
                    conversation_id=request.user.username + "_" + searched_sender_data.get("user_name"),
                )
                new_friend.save()
            friendship = find_friendship(
                request.user.username, searched_sender_data.get("user_name"))

    redirect_url = reverse('friend-requests')
    response = redirect(redirect_url)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required(login_url="signin")
def friends(request):
    # base_url = request.build_absolute_uri('/').rstrip('/')
    # Fetch all friends for the logged-in user
    friends = find_friend_users_alphabetically_sorted(request.user.username)

    friends_data = []
    # Loop through all the friend requests to gather user data and profile information
    for friend in friends:
        # Fetch user data for the sender of the friend request
        searched_user_data = find_an_object(
            collection_name="user_data",
            search_criteria={
                "user_name": friend['user_name']},
        )

        # Fetch user profile for the sender of the friend request
        searched_user_profile = find_an_object(
            collection_name="user_profile",
            search_criteria={
                "user_name": friend['user_name']},
        )

        # If both user data and profile are found, append to the result list
        if searched_user_data and searched_user_profile:
            # show icon in profile card according to gender
            if searched_user_data["gender"] == "male":
                gender_icon_string = "fa-mars"
            elif searched_user_data["gender"] == "female":
                gender_icon_string = "fa-venus"
            else:
                gender_icon_string = "fa-mars-and-venus"

            friends_data.append(
                {
                    "user_data": {
                        "_id": str(
                            searched_user_data["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "email": searched_user_data["email"],
                        "user_name": searched_user_data["user_name"],
                        "full_name": searched_user_data["full_name"],
                        "dob": searched_user_data["dob"],
                        "gender": searched_user_data["gender"],
                        "short_name": searched_user_data["short_name"],
                        "search_id": searched_user_data["search_id"],
                        "search_id_enc": base64_encrypt(searched_user_data["search_id"]),
                        "short_name_enc": base64_encrypt(searched_user_data["short_name"]),
                        "is_active": searched_user_data["is_active"],
                        "is_new_user": searched_user_data["is_new_user"],
                        "gender_icon_string": gender_icon_string,
                    },
                    "user_profile": {
                        "_id": str(
                            searched_user_profile["_id"]
                        ),  # Converting ObjectId to string for JSON serializability
                        "user_name": searched_user_profile["user_name"],
                        "profile_picture": searched_user_profile["profile_picture"],
                        "about": searched_user_profile["about"],
                        "qr_code": searched_user_profile["qr_code"],
                    },
                }
            )
    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    # Fetch user data for the sender of the friend request
    user_data = find_an_object(
        collection_name="user_data",
        search_criteria={
            "user_name": request.user.username},
    )
    img_name = generate_profile_qr(
        user_data.get("short_name") if user_data else None,
        user_data.get("search_id") if user_data else None,
    )
    if user_data:
        _enc_sn = base64_encrypt(user_data.get("short_name", ""))
        _enc_si = base64_encrypt(user_data.get("search_id", ""))
        _host = request.build_absolute_uri('/').rstrip('/')
        profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
    else:
        profile_share_url = ""

    context = {
        "friend_request_data": friends_data,
        # You can add a logic here to determine if the user is the sender of the request
        "auth_user_info": auth_user_info,
        "img_name": img_name,
        "profile_share_url": profile_share_url,
    }
    return render(request, "friends.html", context)


@login_required(login_url="signin")
def direct_message(request):
    # if request.method == 'POST':
    if request.method == 'GET':
        # friend_id = request.POST.get('user-id')
        encoded_conversation_id = request.GET.get('with')
        conversation_id = base64_decrypt(encoded_conversation_id)

        # Guard against missing or invalid conversation_id
        if not conversation_id:
            return redirect(reverse('orca'))

        # Check if conversation_id contains the full request.user.username
        if request.user.username not in conversation_id:
            # If user tries to access another user's conversation, redirect to home
            redirect_url = reverse('orca')
            response = redirect(redirect_url)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response

        friend_id = get_friend_id_by_conversation(conversation_id, request.user.username)

        if conversation_id:
            conversations = get_conversation_by_id(conversation_id, request.user.username)
            # Parse and sort by datetime (oldest first)

            def parse_dt(msg):
                val = msg.get('created_at')
                for fmt in ("%d-%m-%Y %H:%M:%S:%f", "%d-%m-%Y %H:%M:%S"):
                    try:
                        return datetime.strptime(val, fmt)
                    except Exception:
                        continue
                return None

            for msg in conversations:
                dt = parse_dt(msg)
                if dt:
                    msg['created_at_dt'] = dt
                    msg['created_at_formatted'] = dt.strftime(
                        "%I:%M %p").lstrip('0').lower()
                else:
                    msg['created_at_dt'] = None
                    msg['created_at_formatted'] = msg.get('created_at', '')

            conversations_sorted = sorted(
                conversations,
                key=lambda x: x.get('created_at_dt') or datetime.min
            )

            # get current user data
            auth_user_info = auth_user_data(request)
            # Get the first name of the friend
            searched_user_data = find_an_object(
                collection_name="user_data",
                search_criteria={
                    "user_name": friend_id,
                },
            )
            first_name = searched_user_data['full_name'].split(
            )[0] if searched_user_data and 'full_name' in searched_user_data else ''
            encrypted_conversation_id = get_conversation_id_for_friendship(request.user.username, friend_id)

            # Fetch user data for the sender of the friend request
            user_data = find_an_object(
                collection_name="user_data",
                search_criteria={
                    "user_name": request.user.username},
            )
            img_name = generate_profile_qr(
                user_data.get("short_name") if user_data else None,
                user_data.get("search_id") if user_data else None,
            )
            if user_data:
                _enc_sn = base64_encrypt(user_data.get("short_name", ""))
                _enc_si = base64_encrypt(user_data.get("search_id", ""))
                _host = request.build_absolute_uri('/').rstrip('/')
                profile_share_url = f"{_host}/search-profile?short-name={_enc_sn}&id-number={_enc_si}"
            else:
                profile_share_url = ""

            # print(conversations_sorted)
            return render(
                request,
                "chat.html",
                {
                    "friend_id": friend_id,
                    "first_name": first_name,
                    "messages": conversations_sorted,
                    "auth_user_info": auth_user_info,
                    "encrypted_conversation_id": encrypted_conversation_id,
                    "img_name": img_name,
                    "profile_share_url": profile_share_url,
                }
            )
        else:
            return HttpResponseBadRequest("User ID is missing.")
    else:
        return HttpResponseBadRequest("Invalid request method.")


@login_required(login_url="signin")
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message')
            friend_id = data.get('friend_id')
            created_at = data.get('created_at')

            conversation_id = get_conversation_id_for_friendship(
                request.user.username, friend_id)

            conversation_document = Conversation(  # Create a dictionary for the user data
                conversation_id=conversation_id,
                sender=request.user.username,
                message=message,
                receiver=friend_id,
                created_at=created_at,
            )
            result = conversation_document.save()
            if not result:
                return HttpResponseBadRequest("Failed to send message.")
            return HttpResponse("Message sent successfully.")
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON.")
    else:
        return HttpResponseBadRequest("Invalid request method.")
