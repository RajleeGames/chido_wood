from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.purchase_list,
        name="purchase-list",
    ),
    path(
        "new/",
        views.purchase_create,
        name="purchase-create",
    ),
    path(
        "<int:pk>/",
        views.purchase_detail,
        name="purchase-detail",
    ),
    path(
        "<int:pk>/edit/",
        views.purchase_edit,
        name="purchase-edit",
    ),
    path(
        "<int:pk>/post/",
        views.purchase_post,
        name="purchase-post",
    ),
]