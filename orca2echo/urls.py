from django.urls import path
from orca2echo import views

urlpatterns = [
    path("", views.index, name="orca"),     # route to index function of views.py home
    path('mobile-only/', views.mobile_only, name='mobile_only'),
    path("signin", views.signin, name="signin"),
    path("verify_otp", views.verify_otp, name="verify_otp"),
    # path('resend_otp', views.resend_otp, name='resend_otp'),
    # path('home', views.home, name='home'),
    
    # path("about", views.about, name="about"),
    # path("recommendation", views.recommendation, name="recommendation"),
    # path("movie_detail", views.movie_detail, name="movie_detail"),
    # path("detail", views.detail, name="detail"),
    # path("contact", views.contact, name="contact"),
    # path("moderator", views.moderator, name="moderator"),
    # path("preference", views.preference, name="preference"),
    # path("test", views.test, name="test"),
    # path("register", views.register, name="register"),
    # path("signout", views.signout, name="signout"),
    # path("history", views.history, name="history"),
    # path("go_to_history", views.go_to_history, name="go_to_history"),
    # path("trash", views.trash, name="trash"),
    # path('forbidden', views.forbidden, name='forbidden'),

    # if http://127.0.0.1:8000/moderator in url then route to about function of views.py home
    # path("moderator", views.moderator, name="moderator"),

]
