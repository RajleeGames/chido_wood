from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def _is_management_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False

    return bool(
        user.is_superuser
        or getattr(user, "role", "") in {"admin", "manager"}
    )


def sms_required(view_function):
    """Allow every active authenticated CHIDO user to use the SMS Center."""

    @wraps(view_function)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        if request.user.is_active:
            return view_function(request, *args, **kwargs)

        messages.error(request, "Your account is inactive.")
        return redirect("login")

    return wrapped_view


def sms_manage_required(view_function):
    """Allow only superusers, administrators and managers."""

    @wraps(view_function)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        if _is_management_user(request.user):
            return view_function(request, *args, **kwargs)

        messages.error(
            request,
            "Administrator or Manager permission is required for that SMS setting.",
        )
        return redirect("sms-dashboard")

    return wrapped_view


def can_manage_sms(user):
    return _is_management_user(user)


def can_send_promotional_sms(user):
    return _is_management_user(user)
