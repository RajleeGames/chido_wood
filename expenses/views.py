from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import (
    DecimalField,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import (
    require_POST,
)

from accounts.decorators import manager_required

from .forms import (
    ExpenseCategoryForm,
    ExpenseForm,
)
from .models import (
    Expense,
    ExpenseCategory,
)
from .services import (
    cancel_expense,
    post_expense,
)


ZERO_MONEY = Decimal("0.00")


@manager_required
def expense_category_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    categories = (
        ExpenseCategory.objects
        .all()
        .order_by("name")
    )

    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(
                description__icontains=
                search_query
            )
        )

    category_id = (
        request.GET.get("edit")
        or request.POST.get("object_id")
    )

    category_instance = None

    if category_id:
        category_instance = get_object_or_404(
            ExpenseCategory,
            pk=category_id,
        )

    form = ExpenseCategoryForm(
        request.POST or None,
        instance=category_instance,
    )

    modal_open = bool(category_instance)

    if request.method == "POST":
        modal_open = True

        if form.is_valid():
            category = form.save()

            messages.success(
                request,
                (
                    f'Expense category '
                    f'"{category.name}" saved.'
                ),
            )

            return redirect(
                "expense-category-list"
            )

    all_categories = ExpenseCategory.objects.all()

    context = {
        "page_title": "Expense Categories",
        "categories": categories,
        "form": form,
        "editing_category": category_instance,
        "modal_open": modal_open,
        "search_query": search_query,
        "category_count": (
            all_categories.count()
        ),
        "active_category_count": (
            all_categories.filter(
                is_active=True
            ).count()
        ),
        "inactive_category_count": (
            all_categories.filter(
                is_active=False
            ).count()
        ),
    }

    return render(
        request,
        "expenses/category_list.html",
        context,
    )


@manager_required
def expense_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    category_filter = request.GET.get(
        "category",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    payment_filter = request.GET.get(
        "payment",
        "",
    ).strip()

    date_from = request.GET.get(
        "date_from",
        "",
    ).strip()

    date_to = request.GET.get(
        "date_to",
        "",
    ).strip()

    expenses = (
        Expense.objects
        .select_related(
            "category",
            "created_by",
            "posted_by",
            "cancelled_by",
        )
        .order_by(
            "-expense_date",
            "-id",
        )
    )

    if search_query:
        expenses = expenses.filter(
            Q(
                expense_number__icontains=
                search_query
            )
            | Q(
                description__icontains=
                search_query
            )
            | Q(payee__icontains=search_query)
            | Q(
                reference__icontains=
                search_query
            )
            | Q(
                category__name__icontains=
                search_query
            )
        )

    if category_filter:
        expenses = expenses.filter(
            category_id=category_filter
        )

    valid_statuses = {
        value
        for value, label
        in Expense.Status.choices
    }

    if status_filter in valid_statuses:
        expenses = expenses.filter(
            status=status_filter
        )

    valid_payment_methods = {
        value
        for value, label
        in Expense.PaymentMethod.choices
    }

    if payment_filter in valid_payment_methods:
        expenses = expenses.filter(
            payment_method=payment_filter
        )

    if date_from:
        expenses = expenses.filter(
            expense_date__gte=date_from
        )

    if date_to:
        expenses = expenses.filter(
            expense_date__lte=date_to
        )

    today = timezone.localdate()

    month_start = today.replace(
        day=1
    )

    all_expenses = Expense.objects.all()

    posted_expenses = all_expenses.filter(
        status=Expense.Status.POSTED
    )

    total_posted = posted_expenses.aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        )
    )["total"]

    today_total = posted_expenses.filter(
        expense_date=today
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        )
    )["total"]

    month_total = posted_expenses.filter(
        expense_date__gte=month_start,
        expense_date__lte=today,
    ).aggregate(
        total=Coalesce(
            Sum("amount"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        )
    )["total"]

    paginator = Paginator(
        expenses,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    categories = (
        ExpenseCategory.objects
        .filter(is_active=True)
        .order_by("name")
    )

    context = {
        "page_title": "Expenses",
        "expenses": page_obj.object_list,
        "page_obj": page_obj,
        "categories": categories,
        "payment_methods": (
            Expense.PaymentMethod.choices
        ),
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
        "date_from": date_from,
        "date_to": date_to,
        "expense_count": (
            all_expenses.count()
        ),
        "draft_count": all_expenses.filter(
            status=Expense.Status.DRAFT
        ).count(),
        "posted_count": (
            posted_expenses.count()
        ),
        "total_posted": total_posted,
        "today_total": today_total,
        "month_total": month_total,
    }

    return render(
        request,
        "expenses/expense_list.html",
        context,
    )


@manager_required
def expense_create(request):
    expense = Expense(
        created_by=request.user,
        expense_date=timezone.localdate(),
    )

    form = ExpenseForm(
        request.POST or None,
        instance=expense,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        expense = form.save(
            commit=False
        )

        expense.created_by = request.user
        expense.status = Expense.Status.DRAFT
        expense.save()

        if "save_and_post" in request.POST:
            try:
                post_expense(
                    expense_id=expense.id,
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        f"Expense "
                        f"{expense.expense_number} "
                        f"posted successfully."
                    ),
                )

                return redirect(
                    "expense-detail",
                    pk=expense.pk,
                )

            except ValidationError as error:
                messages.error(
                    request,
                    error.messages[0],
                )

                return redirect(
                    "expense-edit",
                    pk=expense.pk,
                )

        messages.success(
            request,
            (
                f"Expense "
                f"{expense.expense_number} "
                f"saved as draft."
            ),
        )

        return redirect(
            "expense-detail",
            pk=expense.pk,
        )

    context = {
        "page_title": "New Expense",
        "form": form,
        "expense": expense,
        "is_editing": False,
    }

    return render(
        request,
        "expenses/expense_form.html",
        context,
    )


@manager_required
def expense_edit(request, pk):
    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if expense.status != Expense.Status.DRAFT:
        messages.error(
            request,
            "Only draft expenses can be edited.",
        )

        return redirect(
            "expense-detail",
            pk=expense.pk,
        )

    form = ExpenseForm(
        request.POST or None,
        instance=expense,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        expense = form.save()

        if "save_and_post" in request.POST:
            try:
                post_expense(
                    expense_id=expense.id,
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        f"Expense "
                        f"{expense.expense_number} "
                        f"posted successfully."
                    ),
                )

                return redirect(
                    "expense-detail",
                    pk=expense.pk,
                )

            except ValidationError as error:
                messages.error(
                    request,
                    error.messages[0],
                )

                return redirect(
                    "expense-edit",
                    pk=expense.pk,
                )

        messages.success(
            request,
            "Draft expense updated.",
        )

        return redirect(
            "expense-detail",
            pk=expense.pk,
        )

    context = {
        "page_title": "Edit Expense",
        "form": form,
        "expense": expense,
        "is_editing": True,
    }

    return render(
        request,
        "expenses/expense_form.html",
        context,
    )


@manager_required
def expense_detail(request, pk):
    expense = get_object_or_404(
        Expense.objects.select_related(
            "category",
            "created_by",
            "posted_by",
            "cancelled_by",
        ),
        pk=pk,
    )

    context = {
        "page_title": expense.expense_number,
        "expense": expense,
    }

    return render(
        request,
        "expenses/expense_detail.html",
        context,
    )


@manager_required
@require_POST
def expense_post(request, pk):
    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    try:
        post_expense(
            expense_id=expense.id,
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Expense "
                f"{expense.expense_number} "
                f"posted successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "expense-detail",
        pk=expense.pk,
    )


@manager_required
@require_POST
def expense_cancel(request, pk):
    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    reason = request.POST.get(
        "reason",
        "",
    ).strip()

    try:
        cancel_expense(
            expense_id=expense.id,
            user=request.user,
            reason=reason,
        )

        messages.success(
            request,
            (
                f"Expense "
                f"{expense.expense_number} "
                f"cancelled successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "expense-detail",
        pk=expense.pk,
    )