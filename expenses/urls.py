from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.expense_list,
        name="expense-list",
    ),

    path(
        "categories/",
        views.expense_category_list,
        name="expense-category-list",
    ),

    path(
        "new/",
        views.expense_create,
        name="expense-create",
    ),

    path(
        "<int:pk>/",
        views.expense_detail,
        name="expense-detail",
    ),

    path(
        "<int:pk>/edit/",
        views.expense_edit,
        name="expense-edit",
    ),

    path(
        "<int:pk>/post/",
        views.expense_post,
        name="expense-post",
    ),

    path(
        "<int:pk>/cancel/",
        views.expense_cancel,
        name="expense-cancel",
    ),
]