from django.urls import path # type: ignore
from orca2echo import views

urlpatterns = [
    # 
    path("", views.index, name="orca"),     # route to index function of views.py home
    path('mobile-only/', views.mobile_only, name='mobile_only'),
    path("signin", views.signin, name="signin"),
    path("verify_otp", views.verify_otp, name="verify_otp"),
    path('logout/', views.user_logout, name='logout'),
    path('show/', views.show_base64_image, name='show'),
    path("signup", views.signup, name="signup"),
]
