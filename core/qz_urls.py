from django.urls import path

from . import qz_views


urlpatterns = [
    path(
        "cert/",
        qz_views.qz_certificate,
        name="qz-certificate",
    ),
    path(
        "sign/",
        qz_views.qz_sign,
        name="qz-sign",
    ),
]
