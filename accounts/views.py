from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from sales.models import Sale

from .decorators import management_required
from .forms import (
    AdminSetPasswordForm,
    OwnPasswordChangeForm,
    ProfileForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import User


ZERO_MONEY = Decimal("0.00")


def administrator_queryset():
    return User.objects.filter(
        Q(is_superuser=True)
        | Q(role=User.Role.ADMIN)
    )


def active_administrator_count():
    return administrator_queryset().filter(
        is_active=True
    ).count()


def user_is_administrator(user):
    return (
        user.is_superuser
        or user.role == User.Role.ADMIN
    )


def actor_can_manage_target(actor, target):
    if target.is_superuser and not actor.is_superuser:
        return False

    return True


def would_remove_last_administrator(
    target,
    *,
    new_role,
    new_is_active,
):
    target_is_active_admin = (
        target.is_active
        and user_is_administrator(target)
    )

    target_remains_active_admin = (
        new_is_active
        and (
            target.is_superuser
            or new_role == User.Role.ADMIN
        )
    )

    if not target_is_active_admin:
        return False

    if target_remains_active_admin:
        return False

    return active_administrator_count() <= 1


@management_required
def user_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    role_filter = request.GET.get(
        "role",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    users = User.objects.all().order_by(
        "first_name",
        "last_name",
        "username",
    )

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    if role_filter in User.Role.values:
        users = users.filter(
            role=role_filter
        )

    if status_filter == "active":
        users = users.filter(
            is_active=True
        )
    elif status_filter == "inactive":
        users = users.filter(
            is_active=False
        )

    all_users = User.objects.all()

    summary = {
        "total": all_users.count(),
        "active": all_users.filter(
            is_active=True
        ).count(),
        "administrators": administrator_queryset().count(),
        "managers": all_users.filter(
            role=User.Role.MANAGER
        ).count(),
        "cashiers": all_users.filter(
            role=User.Role.CASHIER
        ).count(),
    }

    paginator = Paginator(
        users,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Users & Roles",
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "summary": summary,
        "search_query": search_query,
        "role_filter": role_filter,
        "status_filter": status_filter,
        "role_choices": User.Role.choices,
    }

    return render(
        request,
        "accounts/user_list.html",
        context,
    )


@management_required
def user_create(request):
    form = UserCreateForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():
        user = form.save()

        messages.success(
            request,
            (
                f'User "{user.username}" was created '
                "successfully."
            ),
        )

        return redirect(
            "user-detail",
            pk=user.pk,
        )

    context = {
        "page_title": "Create User",
        "form": form,
        "editing_user": None,
    }

    return render(
        request,
        "accounts/user_form.html",
        context,
    )


@management_required
def user_edit(request, pk):
    target_user = get_object_or_404(
        User,
        pk=pk,
    )

    if not actor_can_manage_target(
        request.user,
        target_user,
    ):
        messages.error(
            request,
            "Only a superuser can edit this account.",
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    form = UserUpdateForm(
        request.POST or None,
        instance=target_user,
    )

    if request.method == "POST" and form.is_valid():
        new_role = form.cleaned_data["role"]
        new_is_active = form.cleaned_data["is_active"]

        if target_user.pk == request.user.pk:
            if not new_is_active:
                form.add_error(
                    "is_active",
                    "You cannot deactivate your own account.",
                )

            if new_role != target_user.role:
                form.add_error(
                    "role",
                    "You cannot change your own role.",
                )

        if would_remove_last_administrator(
            target_user,
            new_role=new_role,
            new_is_active=new_is_active,
        ):
            form.add_error(
                "role",
                (
                    "The final active administrator cannot "
                    "be downgraded or deactivated."
                ),
            )

        if not form.errors:
            user = form.save()

            messages.success(
                request,
                (
                    f'User "{user.username}" was updated '
                    "successfully."
                ),
            )

            return redirect(
                "user-detail",
                pk=user.pk,
            )

    context = {
        "page_title": "Edit User",
        "form": form,
        "editing_user": target_user,
    }

    return render(
        request,
        "accounts/user_form.html",
        context,
    )


@management_required
def user_detail(request, pk):
    target_user = get_object_or_404(
        User,
        pk=pk,
    )

    completed_sales = (
        Sale.objects
        .filter(
            completed_by=target_user,
            status=Sale.Status.COMPLETED,
        )
        .select_related("customer")
        .order_by(
            "-sale_date",
            "-id",
        )
    )

    sales_summary = completed_sales.aggregate(
        sale_count=Count("id"),
        sales_revenue=Coalesce(
            Sum("total_amount"),
            Value(ZERO_MONEY),
        ),
    )

    context = {
        "page_title": str(target_user),
        "managed_user": target_user,
        "sales_summary": sales_summary,
        "recent_sales": completed_sales[:10],
        "can_manage_target": actor_can_manage_target(
            request.user,
            target_user,
        ),
    }

    return render(
        request,
        "accounts/user_detail.html",
        context,
    )

@management_required
def user_password_reset(request, pk):
    target_user = get_object_or_404(
        User,
        pk=pk,
    )

    if not actor_can_manage_target(
        request.user,
        target_user,
    ):
        messages.error(
            request,
            "Only a superuser can reset this account password.",
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    form = AdminSetPasswordForm(
        target_user,
        request.POST or None,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(
            request,
            (
                f'Password for "{target_user.username}" '
                "was reset successfully."
            ),
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    context = {
        "page_title": "Reset Password",
        "managed_user": target_user,
        "form": form,
    }

    return render(
        request,
        "accounts/user_password_reset.html",
        context,
    )


@management_required
@require_POST
def user_toggle_active(request, pk):
    target_user = get_object_or_404(
        User,
        pk=pk,
    )

    if not actor_can_manage_target(
        request.user,
        target_user,
    ):
        messages.error(
            request,
            "Only a superuser can change this account status.",
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    if target_user.pk == request.user.pk:
        messages.error(
            request,
            "You cannot deactivate your own account.",
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    new_is_active = not target_user.is_active

    if would_remove_last_administrator(
        target_user,
        new_role=target_user.role,
        new_is_active=new_is_active,
    ):
        messages.error(
            request,
            "The final active administrator cannot be deactivated.",
        )

        return redirect(
            "user-detail",
            pk=target_user.pk,
        )

    target_user.is_active = new_is_active
    target_user.save(
        update_fields=["is_active"]
    )

    status_label = (
        "activated"
        if new_is_active
        else "deactivated"
    )

    messages.success(
        request,
        (
            f'User "{target_user.username}" was '
            f"{status_label}."
        ),
    )

    next_url = request.POST.get(
        "next",
        "",
    )

    if (
        next_url
        and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    ):
        return redirect(next_url)

    return redirect("user-list")


@login_required
def profile(request):
    form = ProfileForm(
        request.POST or None,
        instance=request.user,
    )

    if request.method == "POST" and form.is_valid():
        form.save()

        messages.success(
            request,
            "Your profile was updated successfully.",
        )

        return redirect("profile")

    context = {
        "page_title": "My Profile",
        "form": form,
    }

    return render(
        request,
        "accounts/profile.html",
        context,
    )


@login_required
def change_password(request):
    form = OwnPasswordChangeForm(
        request.user,
        request.POST or None,
    )

    if request.method == "POST" and form.is_valid():
        user = form.save()

        update_session_auth_hash(
            request,
            user,
        )

        messages.success(
            request,
            "Your password was changed successfully.",
        )

        return redirect("profile")

    context = {
        "page_title": "Change Password",
        "form": form,
    }

    return render(
        request,
        "accounts/password_change.html",
        context,
    )
