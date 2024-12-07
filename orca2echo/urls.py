from django.urls import path # type: ignore
from orca2echo import views

urlpatterns = [
    # 
    path("", views.index, name="orca"),     # route to index function of views.py home
    path('mobile-only/', views.mobile_only, name='mobile_only'),
    path("signin", views.signin, name="signin"),
    path("verify-otp", views.verify_otp, name="verify-otp"),
    path('logout/', views.user_logout, name='logout'),
    path("signup", views.signup, name="signup"),
    path("add-friend", views.add_friend, name="add-friend"),
    path("cancel-request", views.cancel_request, name="cancel-request"),
    path("search-profile", views.search_profile, name="search-profile"),
    path("friend-requests", views.friend_requests, name="friend-requests"),
    path("friends", views.friends, name="friends"),
    path("sent-requests", views.sent_requests, name="sent-requests"),
    path("response", views.response, name="response"),

    path("direct-message", views.direct_message, name="direct-message"),
]
