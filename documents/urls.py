from django.urls import path
from . import views

urlpatterns = [
    path("", views.document_list, name="document-list"),
    path("new/", views.document_create, name="document-create"),
    path("<int:pk>/edit/", views.document_edit, name="document-edit"),
    path("<int:pk>/preview/", views.document_preview, name="document-preview"),
    path("<int:pk>/pdf/", views.document_pdf, name="document-pdf"),
    path("<int:pk>/delete/", views.document_delete, name="document-delete"),
    path(
        "share/<uuid:token>/pdf/",
        views.public_document_pdf,
        name="document-public-pdf",
    ),
]
