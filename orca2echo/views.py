from django.shortcuts import render
from django.shortcuts import render, HttpResponse, redirect
import requests

from django.http import HttpResponseForbidden
from django.shortcuts import render
from django_user_agents.utils import get_user_agent



# Create your views here.
def index(request):
    user_agent = get_user_agent(request)
    print(user_agent)
    
    # Check if the device is mobile
    if not user_agent.is_mobile:
        return HttpResponseForbidden("This website is only available on mobile devices.")
    
    # Continue with normal view logic for mobile devices
    # return HttpResponse("hello world!")
    return render(request, "signin.html", {"auth_user": request.user})
