from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "profile/",
        views.profile,
        name="profile",
    ),
    path(
        "profile/password/",
        views.change_password,
        name="change-password",
    ),
    path(
        "users/",
        views.user_list,
        name="user-list",
    ),
    path(
        "users/create/",
        views.user_create,
        name="user-create",
    ),
    path(
        "users/<int:pk>/",
        views.user_detail,
        name="user-detail",
    ),
    path(
        "users/<int:pk>/edit/",
        views.user_edit,
        name="user-edit",
    ),
    path(
        "users/<int:pk>/password/",
        views.user_password_reset,
        name="user-password-reset",
    ),
    path(
        "users/<int:pk>/toggle-active/",
        views.user_toggle_active,
        name="user-toggle-active",
    ),
]
