from django.shortcuts import render
from django.shortcuts import render, HttpResponse, redirect
import requests


# Create your views here.
def index(request):
    # return HttpResponse("hello world!")
    return render(request, "signin.html", {"auth_user": request.user})
