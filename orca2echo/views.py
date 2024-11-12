from django.shortcuts import render
from django.shortcuts import render, HttpResponse, redirect
import requests
from django.core.mail import send_mail
from .services.auth_service import generate_otp,send_otp


# Create your views here.
def index(request):
    return render(request, "signin.html", {"auth_user": request.user})


def mobile_only(request):
    return render(
        request, "mobile_only.html"
    )  # Display a page with the mobile-only message



def signin(request):
    if request.method == "POST":
        otp = generate_otp()
        print(otp)
        email = request.POST.get("email")

        send_otp(otp,email)

        return render(request, "index.html")
    else:
        return render(request, "index.html")
