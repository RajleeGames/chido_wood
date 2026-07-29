from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def management_required(view_function):
    """
    Allow only:

    - Django superusers
    - Administrators
    - Managers

    Cashiers are redirected to Sales.
    Use this only for Dashboard and Users & Roles.
    """

    @wraps(view_function)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        user = request.user

        allowed_roles = {
            user.Role.ADMIN,
            user.Role.MANAGER,
        }

        if (
            user.is_superuser
            or user.role in allowed_roles
        ):
            return view_function(
                request,
                *args,
                **kwargs,
            )

        messages.error(
            request,
            (
                "You do not have permission to access "
                "that section."
            ),
        )

        return redirect("sale-list")

    return wrapped_view


def admin_required(view_function):
    """
    Kept for compatibility with Users & Roles views.

    Administrators, Managers and superusers are allowed.
    Cashiers are blocked.
    """

    return management_required(view_function)


def manager_required(view_function):
    """
    Allow every authenticated CHIDO user.

    Existing Products, Inventory, Purchases,
    Wood Conversion and other operational pages
    already use this decorator.

    Cashiers are therefore allowed to access them.
    """

    return login_required(view_function)


def staff_required(view_function):
    """
    Allow every authenticated user.
    """

    return login_required(view_function)