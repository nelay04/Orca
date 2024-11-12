from django.shortcuts import render
from django.shortcuts import render, HttpResponse, redirect
import requests
from django.core.mail import send_mail
from .services.auth_service import generate_otp,send_otp
from .models import  USER


# Create your views here.
def index(request):
    return render(request, "signin.html", {"auth_user": request.user})


def mobile_only(request):
    return render(
        request, "mobile_only.html"
    )  # Display a page with the mobile-only message



from django.shortcuts import render
from user_agents import parse
import requests

def signin(request):
    if request.method == "POST":
        # Server-side: Fetch user IP address
        ip_address = request.META.get('REMOTE_ADDR')  # Note: Behind a proxy/load balancer, consider 'HTTP_X_FORWARDED_FOR'

        # Get approximate location from IP address using a public API (e.g., ipinfo.io)
        try:
            response = requests.get(f'https://ipinfo.io/{ip_address}/json')
            location_data = response.json()
            ip_location = {
                'ip': location_data.get('ip', 'N/A'),
                'city': location_data.get('city', 'N/A'),
                'region': location_data.get('region', 'N/A'),
                'country': location_data.get('country', 'N/A'),
                'loc': location_data.get('loc', 'N/A'),
            }
        except Exception as e:
            ip_location = {'error': f'Could not fetch IP location - {str(e)}'}

        # Device information
        user_agent_string = request.META.get('HTTP_USER_AGENT', 'unknown')
        user_agent = parse(user_agent_string)
        device_info = {
            'is_mobile': user_agent.is_mobile,
            'is_tablet': user_agent.is_tablet,
            'is_touch_capable': user_agent.is_touch_capable,
            'browser': user_agent.browser.family,
            'browser_version': user_agent.browser.version_string,
            'os': user_agent.os.family,
            'os_version': user_agent.os.version_string,
            'device': user_agent.device.family,
        }

        print("IP Location Data:", ip_location)
        print("Device Information:", device_info)

        # Render or return data to be used by the client-side script
        context = {
            'ip_location': ip_location,
            'device_info': device_info,
        }
        return render(request, 'signin.html', context)

    return render(request, 'signin.html')
