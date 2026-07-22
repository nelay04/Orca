# Standard Library Imports
import json
import logging
from datetime import datetime

# Third-Party Library Imports
from django.contrib.auth import authenticate, login, logout  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from django.core.cache import cache  # type: ignore
from django.http import HttpResponse, HttpResponseBadRequest  # type: ignore
from django.shortcuts import redirect, render  # type: ignore
from django.urls import reverse  # type: ignore

# Local App Imports - Models
from .forms import SigninForm, SignupForm
from .models import Conversation, FriendList, FriendRequestList, UserData, UserProfile

# Local App Imports - Services
from .services.auth_service import (
    auth_user_data,
    decrypt_token,
    encrypt_token,
    extract_first_name,
    generate_nanoseconds,
    generate_otp,
    generate_search_id,
    generate_short_name,
    generate_username,
    get_current_time_ist,
    get_demo_img_text,
    get_oops_img_text,
    get_profile_share_context,
    normalize_full_name,
    send_otp,
)
from .services.model_service import (
    add_otp,
    can_send_otp,
    delete_otp_by_email,
    get_otp_instance,
    get_user_by_email,
    is_otp_expired,
    register_failed_attempt,
)
from .services.mongo_service import (
    find_all_objects,
    find_an_object,
    find_friend_users_alphabetically_sorted,
    find_friend_users_sorted_by_updated_at,
    find_friendship,
    get_conversation_by_id,
    get_conversation_id_for_friendship,
    get_friend_id_by_conversation,
    get_latest_conversation,
    get_user_data_by_email,
    update_fields_by_email,
    update_fields_by_user_name,
    update_objects,
)

logger = logging.getLogger(__name__)

# Ceiling on OTP requests from a single client address per hour. The per-email
# throttle in model_service stops one mailbox being flooded; this stops an
# attacker cycling through many addresses from the same origin.
OTP_REQUESTS_PER_IP_PER_HOUR = 10


def get_client_ip(request):
    """Best-effort client address, honouring a reverse proxy if present."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def within_ip_rate_limit(request):
    """Count this OTP request against the caller's hourly budget.

    Returns False once the budget is spent. Backed by the configured cache,
    which is Redis in deployments and local memory otherwise.
    """
    cache_key = f"otp-requests:{get_client_ip(request)}"
    try:
        # add() only sets the key when absent, which starts the hour window.
        cache.add(cache_key, 0, timeout=3600)
        count = cache.incr(cache_key)
    except ValueError:
        # Key expired between add() and incr(); treat as the first request.
        cache.set(cache_key, 1, timeout=3600)
        count = 1
    return count <= OTP_REQUESTS_PER_IP_PER_HOUR


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
                        "encrypted_conversation_id": encrypt_token(get_conversation_id_for_friendship(request.user.username, searched_user_data["user_name"]))
                    },
                    "user_profile": {
                        "profile_picture": searched_user_profile["profile_picture"],
                    },
                }
            )
    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friends_data": friends_data,
        "auth_user_info": auth_user_info,
        **share_context,
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
        form = SigninForm(request.POST)
        if not form.is_valid():
            error_message = next(iter(form.errors.values()))[0]
            return render(request, "signin.html", {"error": error_message})

        email = form.cleaned_data.get("email")

        # Throttle before doing any work. Without these two checks signin acts
        # as an open relay: anyone can POST in a loop and make the configured
        # mailbox send unlimited mail to an address of their choosing.
        if not can_send_otp(email):
            logger.warning("OTP resend throttled for email")
            return render(request, "otp.html", {
                "error_message": "An OTP was sent recently. Check your inbox, or wait a minute to request another.",
            })

        if not within_ip_rate_limit(request):
            logger.warning("OTP request rate limit hit for client address")
            return render(request, "signin.html", {
                "error": "Too many sign-in attempts. Please try again later.",
            })

        try:
            # Check if user exists. This has to happen before the OTP is sent
            # so that superusers can be excluded without mailing them first.
            if_user = get_user_by_email(email)

            # Superusers do not sign in through OTP, they use the admin page.
            # Render the normal OTP screen anyway rather than saying so: a
            # distinct response here would tell an attacker which address is
            # the administrator. No OTP row is created, so verification fails.
            if if_user is not None and if_user.is_superuser:
                logger.info("Superuser attempted OTP signin, suppressing OTP")
                request.session["email"] = email
                request.session["username"] = if_user.username
                return render(request, "otp.html")

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
            except Exception:
                logger.exception("Error in finding user data from MongoDB")
                name = "user"

            # Generate OTP
            otp = generate_otp()

            # Send OTP to email
            send_otp(otp, email, name)

            if if_user is not None:
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
        except Exception:
            logger.exception("Error during signin logic")
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

        otp_instance = get_otp_instance(email)

        # No pending OTP means there is nothing to verify. This must be an
        # explicit check: retrieve_otp() returns None when the row is absent,
        # and the old code compared against str(None), so posting the literal
        # string "None" authenticated the session.
        if otp_instance is None:
            return render(request, "otp.html", {
                "error_message": "This code has expired or was already used. Please sign in again.",
            })

        if is_otp_expired(otp_instance):
            delete_otp_by_email(email)
            return render(request, "otp.html", {
                "error_message": "This code has expired. Please sign in again.",
            })

        original_otp = otp_instance.otp

        if entered_otp and entered_otp == str(original_otp):
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
            # Count the miss. A 6-digit code is brute-forceable in well under a
            # day of unthrottled guessing, so the OTP is burned after a small
            # number of failures and the user has to request a new one.
            burned = register_failed_attempt(otp_instance)
            if burned:
                error_message = "Too many incorrect attempts. Please sign in again to get a new code."
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

        form = SignupForm(request.POST)
        if not form.is_valid():
            error_message = next(iter(form.errors.values()))[0]
            return render(request, "signup.html", {"error": error_message})

        full_name = form.cleaned_data.get("full_name")
        gender = form.cleaned_data.get("gender")
        dob = str(form.cleaned_data.get("dob"))

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
        receiver_short_name = decrypt_token(receiver_short_name_enc)
        receiver_id_number = decrypt_token(receiver_id_number_enc)

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
        share_context = get_profile_share_context(request.user.username, request)

        return render(
            request,
            "add_friend.html",
            {
                "auth_user_info": auth_user_info,
                **share_context,
            },
        )


@login_required(login_url="signin")
def search_profile(request):
    # handle profile card view
    if request.method == "GET":
        # get cncrypted short-name and id-number and decrypt
        short_name_enc = request.GET.get("short-name", "").strip()
        id_number_enc = request.GET.get("id-number", "").strip()
        short_name = decrypt_token(short_name_enc)
        id_number = decrypt_token(id_number_enc)

        # get user data
        auth_user_info = auth_user_data(request)

        # fetch current user's data for QR / share link
        share_context = get_profile_share_context(request.user.username, request)

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
                    **share_context,
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

        # print("Friend Request Object:", if_friend_request)  # Debugging print statement
        # print("Reverse Friend Request Object:", if_friends_reverse)  # Debugging print statement

        if if_friends_reverse:
            if if_friends_reverse.get("is_accepted") is True:
                btn_text = "You're Friends"
                btn_color = "#00e800"
                action = "/"
            if if_friends_reverse.get("is_active") is True and if_friends_reverse.get("is_accepted") is False:
                btn_text = "Accept Request"
                btn_color = "#00e800"
                action = "/response"
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
                **share_context,
            },
        )

    return redirect("orca")


@login_required(login_url="signin")
def cancel_request(request):
    # handle cancel friend request
    if request.method == "POST":

        from_sent_request = request.POST.get("from_sent_request")

        if from_sent_request == '0':
            # get cncrypted short-name and id-number and decrypt
            receiver_short_name_enc = request.POST.get("short_name_enc")
            receiver_id_number_enc = request.POST.get("id_number_enc")
            receiver_short_name = decrypt_token(receiver_short_name_enc)
            receiver_id_number = decrypt_token(receiver_id_number_enc)
            # show profile card accourding to current relation and allowed action
            redirect_url = reverse('search-profile') + f'?short-name={
                receiver_short_name_enc}&id-number={receiver_id_number_enc}'
        elif from_sent_request == '1':
            receiver_short_name = request.POST.get("short_name_enc")
            receiver_id_number = request.POST.get("id_number_enc")
            # show profile card accourding to current relation and allowed action
            redirect_url = reverse('sent-requests')
        else:
            # Unexpected value for from_sent_request. Bail out rather than
            # falling through to an unbound redirect_url further down.
            return redirect(reverse('orca'))

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

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friend_request_data": friend_request_data,
        # You can add a logic here to determine if the user is the sender of the request
        "its_me": False,
        "auth_user_info": auth_user_info,
        **share_context,
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

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friend_request_data": friend_request_data,
        # You can add a logic here to determine if the user is the sender of the request
        "its_me": False,
        "auth_user_info": auth_user_info,
        **share_context,
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
                        "search_id_enc": encrypt_token(searched_user_data["search_id"]),
                        "short_name_enc": encrypt_token(searched_user_data["short_name"]),
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

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friend_request_data": friends_data,
        # You can add a logic here to determine if the user is the sender of the request
        "auth_user_info": auth_user_info,
        **share_context,
    }
    return render(request, "friends.html", context)


@login_required(login_url="signin")
def direct_message(request):
    # if request.method == 'POST':
    if request.method == 'GET':
        # friend_id = request.POST.get('user-id')
        encoded_conversation_id = request.GET.get('with')
        conversation_id = decrypt_token(encoded_conversation_id)

        # Guard against missing or invalid conversation_id
        if not conversation_id:
            return redirect(reverse('orca'))

        # Authorization: this returns the other participant only when the
        # current user is actually a member of the conversation, so a None
        # result means the user has no claim to it. Do not substitute a
        # substring test on conversation_id, usernames can overlap.
        friend_id = get_friend_id_by_conversation(conversation_id, request.user.username)

        if friend_id is None:
            response = redirect(reverse('orca'))
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response

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

            share_context = get_profile_share_context(request.user.username, request)

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
                    **share_context,
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
