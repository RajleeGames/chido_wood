from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
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
        "products/",
        include("products.urls"),
    ),

    path(
        "",
        include("core.urls"),
    ),

    path(
    "suppliers/",
    include("suppliers.urls"),
),

path(
    "purchases/",
    include("purchases.urls"),
),

path(
    "inventory/",
    include("inventory.urls"),
),
path(
    "customers/",
    include("customers.urls"),
),

path(
    "sales/",
    include("sales.urls"),
),


path(
    "expenses/",
    include("expenses.urls"),
),

path(
    "reports/",
    include("reports.urls"),
),

path(
    "accounts/", include("accounts.urls"),
),

path("sms/", include("sms.urls")),

]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )