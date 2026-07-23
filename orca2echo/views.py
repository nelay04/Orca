# Standard Library Imports
import json
import logging
import os

# Third-Party Library Imports
from django.contrib.auth import authenticate, login, logout  # type: ignore
from django.contrib.auth.decorators import login_required  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from django.core.cache import cache  # type: ignore
from django.db import transaction  # type: ignore
from django.db.models import F  # type: ignore
from django.http import (  # type: ignore
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import redirect, render  # type: ignore
from django.urls import reverse  # type: ignore
from django.utils import timezone  # type: ignore

# Local App Imports - Models
from .forms import SigninForm, SignupForm
from .models import FriendRequest, Friendship, Message, Profile

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
    get_demo_img_text,
    get_oops_img_text,
    get_profile_share_context,
    normalize_full_name,
    qr_image_path,
    send_otp,
)
from .services.data_service import (
    find_friendship,
    find_profile,
    get_friend_request,
    get_messages,
    get_profile,
    get_profile_by_email,
    list_friends_alphabetically,
    list_friends_by_recent_activity,
    list_incoming_requests,
    list_outgoing_requests,
    resolve_friendship,
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

logger = logging.getLogger(__name__)

# Ceiling on OTP requests from a single client address per hour. The per-email
# throttle in model_service stops one mailbox being flooded; this stops an
# attacker cycling through many addresses from the same origin.
OTP_REQUESTS_PER_IP_PER_HOUR = 10

GENDER_ICONS = {
    "male": "fa-mars",
    "female": "fa-venus",
}
DEFAULT_GENDER_ICON = "fa-mars-and-venus"


def gender_icon(gender):
    return GENDER_ICONS.get(gender, DEFAULT_GENDER_ICON)


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


def profile_card_payload(profile, **extra):
    """The template context a profile is rendered with.

    Kept in one place because the friends, requests and sent-requests pages all
    render the same card from the same fields.
    """
    payload = {
        "user_name": profile.user.username,
        "email": profile.user.email,
        "full_name": profile.full_name,
        "dob": profile.dob,
        "gender": profile.gender,
        "short_name": profile.short_name,
        "search_id": profile.search_id,
        "is_active": profile.is_active,
        "is_new_user": profile.is_new_user,
        "gender_icon_string": gender_icon(profile.gender),
    }
    payload.update(extra)
    return payload


# Create your views here.

@login_required(login_url="signin")
def index(request):

    # Fetch all friends for the logged-in user, most recent conversation first
    friends_data = []
    for entry in list_friends_by_recent_activity(request.user):
        profile = entry["profile"]
        if profile is None:
            continue

        friends_data.append(
            {
                "user_data": {
                    "full_name": profile.full_name,
                    "latest_conversation_message": entry["last_message_text"],
                    "is_sender": entry["last_message_is_mine"],
                    "encrypted_conversation_id": encrypt_token(str(entry["friendship"].public_id)),
                },
                "user_profile": {
                    "profile_picture": profile.profile_picture,
                },
            }
        )

    auth_user_info = auth_user_data(request)

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friends_data": friends_data,
        "auth_user_info": auth_user_info,
        **share_context,
    }

    return render(
        request,
        "index.html",
        context,
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

            # Find out name if available
            name = "user"
            try:
                existing_profile = get_profile_by_email(email)
                if existing_profile:
                    # add a space before name
                    name = " " + extract_first_name(existing_profile.full_name)
            except Exception:
                logger.exception("Error in finding profile")
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

                # Add a new user if not found. Both rows are written together:
                # a user without a profile can never finish signup, and would
                # hold the email address against a second attempt.
                with transaction.atomic():
                    new_user = User.objects.create_user(
                        username=username, email=email, password=otp
                    )
                    Profile.objects.create(user=new_user)

                add_otp(email, otp)

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
            profile = get_profile_by_email(email)

            if profile is None or profile.is_new_user:
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
        dob = form.cleaned_data.get("dob")

        profile = get_profile(username)
        if profile is None:
            logger.error("Signup posted with no profile for the session username")
            return redirect("signin")

        # If validation passes, proceed with your logic
        normalized_full_name = normalize_full_name(full_name)
        profile.full_name = normalized_full_name
        profile.short_name = generate_short_name(normalized_full_name)
        profile.search_id = search_id
        profile.gender = gender
        profile.dob = dob
        profile.profile_picture = get_demo_img_text(gender)
        profile.is_new_user = False
        profile.save()

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
def qr_image(request):
    # Served from disk directly rather than through django.contrib.staticfiles
    # / WhiteNoise: the PNG is generated on demand at request time, which is
    # after collectstatic has run and after WhiteNoise has already indexed
    # STATIC_ROOT, so the static pipeline never sees it in production.
    share_context = get_profile_share_context(request.user.username, request)
    img_name = share_context.get("img_name")
    if not img_name:
        raise Http404

    image_path = qr_image_path(img_name)
    if not os.path.exists(image_path):
        raise Http404

    return FileResponse(open(image_path, "rb"), content_type="image/png")


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

        receiver_profile = find_profile(receiver_short_name, receiver_id_number)

        if receiver_profile is None:
            return redirect(reverse('orca'))

        if_friend_request = get_friend_request(request.user, receiver_profile.user)

        # check if there is inactive request then activate that request
        if if_friend_request:
            if if_friend_request.is_active is False:
                if_friend_request.is_active = True
                if_friend_request.is_cancelled = False
                if_friend_request.is_declined = False
                if_friend_request.request_time = timezone.now()
                if_friend_request.request_count = F("request_count") + 1
                if_friend_request.save()
        else:
            # if there is no active request already create a new request
            FriendRequest.objects.create(
                sender=request.user,
                receiver=receiver_profile.user,
                request_time=timezone.now(),
                request_count=1,
            )

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
        # get encrypted short-name and id-number and decrypt
        short_name_enc = request.GET.get("short-name", "").strip()
        id_number_enc = request.GET.get("id-number", "").strip()
        short_name = decrypt_token(short_name_enc)
        id_number = decrypt_token(id_number_enc)

        # get user data
        auth_user_info = auth_user_data(request)

        # fetch current user's data for QR / share link
        share_context = get_profile_share_context(request.user.username, request)

        searched_profile = find_profile(short_name, id_number)

        # image string for user not found
        oops_string = get_oops_img_text("oops")
        oops_dark_string = get_oops_img_text("oops_dark")

        # if user is not found then return
        if searched_profile is None:
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

        searched_user = searched_profile.user

        # identify if user is searching himself then hide action buttons.
        its_me = request.user.username == searched_user.username

        # check current relation with searched user, in both directions
        if_friend_request = get_friend_request(request.user, searched_user)
        if_friends_reverse = get_friend_request(searched_user, request.user)

        if if_friends_reverse:
            if if_friends_reverse.is_accepted is True:
                btn_text = "You're Friends"
                btn_color = "#00e800"
                action = "/"
            if if_friends_reverse.is_active is True and if_friends_reverse.is_accepted is False:
                btn_text = "Accept Request"
                btn_color = "#00e800"
                action = "/response"
        else:
            # if request object is available
            if if_friend_request:
                if if_friend_request.is_accepted is True:
                    btn_text = "You're Friends"
                    btn_color = "#00e800"
                    action = "/"
                # if request object is not available then allow to cancel request
                elif if_friend_request.is_active is True:
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

        # show profile card according to current relation and allowed action
        return render(
            request,
            "profile_card.html",
            {
                "auth_user_info": auth_user_info,
                "btn_text": btn_text,
                "btn_color": btn_color,
                "action": action,
                "searched_base64_string": searched_profile.profile_picture,
                "searched_about": searched_profile.about,
                "searched_name": searched_profile.full_name,
                "gender_icon_string": gender_icon(searched_profile.gender),
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
            # get encrypted short-name and id-number and decrypt
            receiver_short_name_enc = request.POST.get("short_name_enc")
            receiver_id_number_enc = request.POST.get("id_number_enc")
            receiver_short_name = decrypt_token(receiver_short_name_enc)
            receiver_id_number = decrypt_token(receiver_id_number_enc)
            # show profile card according to current relation and allowed action
            redirect_url = reverse('search-profile') + f'?short-name={
                receiver_short_name_enc}&id-number={receiver_id_number_enc}'
        elif from_sent_request == '1':
            receiver_short_name = request.POST.get("short_name_enc")
            receiver_id_number = request.POST.get("id_number_enc")
            # show profile card according to current relation and allowed action
            redirect_url = reverse('sent-requests')
        else:
            # Unexpected value for from_sent_request. Bail out rather than
            # falling through to an unbound redirect_url further down.
            return redirect(reverse('orca'))

        receiver_profile = find_profile(receiver_short_name, receiver_id_number)

        if receiver_profile is None:
            return redirect(reverse('orca'))

        # get request object data
        if_friend_request = get_friend_request(request.user, receiver_profile.user)

        # check if request data object is available and still active
        if if_friend_request and if_friend_request.is_active is True:
            # deactivate status and cancel request
            if_friend_request.is_active = False
            if_friend_request.is_cancelled = True
            if_friend_request.cancellation_time = timezone.now()
            if_friend_request.cancellation_count = F("cancellation_count") + 1
            if_friend_request.save()

        # redirect
        response = redirect(redirect_url)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


@login_required(login_url="signin")
def friend_requests(request):
    # Fetch all active friend requests addressed to the logged-in user
    friend_request_data = []
    for friend_request in list_incoming_requests(request.user):
        sender_profile = getattr(friend_request.sender, "profile", None)
        if sender_profile is None:
            continue

        friend_request_data.append(
            {
                "user_data": profile_card_payload(sender_profile),
                "user_profile": {
                    "user_name": friend_request.sender.username,
                    "profile_picture": sender_profile.profile_picture,
                    "about": sender_profile.about,
                    "qr_code": sender_profile.qr_code,
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
    # Fetch all active friend requests sent by the logged-in user
    friend_request_data = []
    for friend_request in list_outgoing_requests(request.user):
        receiver_profile = getattr(friend_request.receiver, "profile", None)
        if receiver_profile is None:
            continue

        friend_request_data.append(
            {
                "user_data": profile_card_payload(receiver_profile),
                "user_profile": {
                    "user_name": friend_request.receiver.username,
                    "profile_picture": receiver_profile.profile_picture,
                    "about": receiver_profile.about,
                    "qr_code": receiver_profile.qr_code,
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
    # handle friend request response
    if request.method == "POST":
        response = request.POST.get('response')
        if response in ('accept', 'decline'):
            sender_short_name = request.POST.get("short_name_enc")
            sender_id_number = request.POST.get("id_number_enc")

            sender_profile = find_profile(sender_short_name, sender_id_number)

            if sender_profile is None:
                return redirect(reverse('friend-requests'))

            # get request object data
            if_friend_request = get_friend_request(sender_profile.user, request.user)

            # check if request data object is available and still active
            if if_friend_request and if_friend_request.is_active is True:
                if_friend_request.is_active = False
                if_friend_request.response_time = timezone.now()
                if response == 'decline':
                    if_friend_request.is_declined = True
                    if_friend_request.declination_count = F("declination_count") + 1
                else:
                    if_friend_request.is_accepted = True
                    if_friend_request.acceptance_count = F("acceptance_count") + 1
                if_friend_request.save()

            if response == 'accept':
                # create the friendship, which is also the conversation, unless
                # one already exists in either direction
                if not find_friendship(request.user, sender_profile.user):
                    Friendship.objects.create(
                        user_1=request.user,
                        user_2=sender_profile.user,
                    )

    redirect_url = reverse('friend-requests')
    response = redirect(redirect_url)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required(login_url="signin")
def friends(request):
    friends_data = []
    for entry in list_friends_alphabetically(request.user):
        profile = entry["profile"]
        if profile is None:
            continue

        friends_data.append(
            {
                "user_data": profile_card_payload(
                    profile,
                    search_id_enc=encrypt_token(profile.search_id),
                    short_name_enc=encrypt_token(profile.short_name),
                ),
                "user_profile": {
                    "user_name": entry["friend"].username,
                    "profile_picture": profile.profile_picture,
                    "about": profile.about,
                    "qr_code": profile.qr_code,
                },
            }
        )

    # Pass the friend request data to the template
    auth_user_info = auth_user_data(request)

    share_context = get_profile_share_context(request.user.username, request)

    context = {
        "friend_request_data": friends_data,
        "auth_user_info": auth_user_info,
        **share_context,
    }
    return render(request, "friends.html", context)


@login_required(login_url="signin")
def direct_message(request):
    if request.method == 'GET':
        encoded_conversation_id = request.GET.get('with')
        public_id = decrypt_token(encoded_conversation_id)

        # Guard against missing or invalid token
        if not public_id:
            return redirect(reverse('orca'))

        # Authorization: this resolves the friendship only when the current
        # user is one of its two members, so a None result means the user has
        # no claim to the conversation. The token itself proves nothing.
        resolved = resolve_friendship(public_id, request.user)

        if resolved is None:
            response = redirect(reverse('orca'))
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response

        friendship, friend = resolved

        # Messages come back in created_at order from the database.
        messages = get_messages(friendship)
        for message in messages:
            message.is_sender = message.sender_id == request.user.id

        # get current user data
        auth_user_info = auth_user_data(request)

        friend_profile = getattr(friend, "profile", None)
        first_name = ''
        if friend_profile and friend_profile.full_name:
            first_name = friend_profile.full_name.split()[0]

        share_context = get_profile_share_context(request.user.username, request)

        return render(
            request,
            "chat.html",
            {
                "friend_id": friend.username,
                "first_name": first_name,
                "messages": messages,
                "auth_user_info": auth_user_info,
                "conversation_id": str(friendship.public_id),
                **share_context,
            }
        )
    else:
        return HttpResponseBadRequest("Invalid request method.")


@login_required(login_url="signin")
def send_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message')
            friend_id = data.get('friend_id')

            friend = User.objects.filter(username=friend_id).first()
            friendship = find_friendship(request.user, friend) if friend else None

            if not message or friendship is None:
                return HttpResponseBadRequest("Failed to send message.")

            # created_at is set by the database, never by the caller.
            Message.objects.create(
                friendship=friendship,
                sender=request.user,
                receiver=friend,
                message=message,
            )
            return HttpResponse("Message sent successfully.")
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON.")
    else:
        return HttpResponseBadRequest("Invalid request method.")
