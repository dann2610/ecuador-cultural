from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (("Ecuador Cultural", {"fields": ("role", "phone", "bio", "avatar")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Ecuador Cultural", {"fields": ("email", "role")}),)
