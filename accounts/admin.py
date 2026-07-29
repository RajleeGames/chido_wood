from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class ChidoUserAdmin(UserAdmin):
    list_display = [
        "username",
        "first_name",
        "last_name",
        "role",
        "phone",
        "is_active",
        "is_staff",
        "last_login",
    ]

    list_filter = [
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    ]

    search_fields = [
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
    ]

    ordering = [
        "first_name",
        "last_name",
        "username",
    ]

    fieldsets = UserAdmin.fieldsets + (
        (
            "CHIDO Wood ERP",
            {
                "fields": (
                    "role",
                    "phone",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "CHIDO Wood ERP",
            {
                "classes": ("wide",),
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "role",
                    "is_active",
                ),
            },
        ),
    )
