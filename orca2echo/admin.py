from django.contrib import admin

from .models import FriendRequest, Friendship, Message, Otp, Profile


@admin.register(Otp)
class OtpAdmin(admin.ModelAdmin):
    list_display = ("email", "otp", "attempts", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "short_name", "search_id", "gender", "is_new_user")
    list_filter = ("gender", "is_active", "is_new_user")
    search_fields = ("user__username", "user__email", "full_name", "short_name", "search_id")
    # The picture is a base64 blob, so it is not worth loading into a widget on
    # the change form by default.
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "is_active", "is_accepted", "is_declined", "is_cancelled", "request_time")
    list_filter = ("is_active", "is_accepted", "is_declined", "is_cancelled")
    search_fields = ("sender__username", "receiver__username")
    raw_id_fields = ("sender", "receiver")


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("user_1", "user_2", "public_id", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user_1__username", "user_2__username", "public_id")
    raw_id_fields = ("user_1", "user_2")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "message", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("sender__username", "receiver__username", "message")
    raw_id_fields = ("friendship", "sender", "receiver")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
