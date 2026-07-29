from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.business_report,
        name="business-report",
    ),

    path(
        "export/csv/",
        views.business_report_csv,
        name="business-report-csv",
    ),
]