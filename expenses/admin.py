from django.contrib import admin

from .models import (
    Expense,
    ExpenseCategory,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "code",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "code",
        "description",
    )

    ordering = (
        "name",
    )


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "expense_number",
        "expense_date",
        "category",
        "description",
        "amount",
        "payment_method",
        "status",
        "created_by",
    )

    list_filter = (
        "status",
        "category",
        "payment_method",
        "expense_date",
    )

    search_fields = (
        "expense_number",
        "description",
        "payee",
        "reference",
        "notes",
    )

    autocomplete_fields = (
        "category",
        "created_by",
        "posted_by",
        "cancelled_by",
    )

    readonly_fields = (
        "expense_number",
        "status",
        "posted_by",
        "posted_at",
        "cancelled_by",
        "cancelled_at",
        "cancellation_reason",
        "created_at",
        "updated_at",
    )

    date_hierarchy = "expense_date"