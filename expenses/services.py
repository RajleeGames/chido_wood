from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Expense


ZERO_MONEY = Decimal("0.00")


@transaction.atomic
def post_expense(
    *,
    expense_id,
    user,
):
    expense = (
        Expense.objects
        .select_for_update()
        .select_related("category")
        .get(pk=expense_id)
    )

    if expense.status != Expense.Status.DRAFT:
        raise ValidationError(
            "Only draft expenses can be posted."
        )

    if not expense.category.is_active:
        raise ValidationError(
            (
                "The selected expense category "
                "is inactive."
            )
        )

    if expense.amount <= ZERO_MONEY:
        raise ValidationError(
            (
                "Expense amount must be greater "
                "than zero."
            )
        )

    if not str(
        expense.description or ""
    ).strip():
        raise ValidationError(
            "Enter an expense description."
        )

    expense.status = Expense.Status.POSTED
    expense.posted_by = user
    expense.posted_at = timezone.now()

    expense.save(
        update_fields=[
            "status",
            "posted_by",
            "posted_at",
            "updated_at",
        ]
    )

    return expense


@transaction.atomic
def cancel_expense(
    *,
    expense_id,
    user,
    reason,
):
    expense = (
        Expense.objects
        .select_for_update()
        .get(pk=expense_id)
    )

    if expense.status == Expense.Status.CANCELLED:
        raise ValidationError(
            "This expense is already cancelled."
        )

    reason = str(
        reason or ""
    ).strip()

    if not reason:
        raise ValidationError(
            (
                "Enter a reason for cancelling "
                "the expense."
            )
        )

    expense.status = Expense.Status.CANCELLED
    expense.cancelled_by = user
    expense.cancelled_at = timezone.now()
    expense.cancellation_reason = reason

    expense.save(
        update_fields=[
            "status",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )

    return expense