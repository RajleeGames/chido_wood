from datetime import datetime, time
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
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
from django.views.decorators.http import require_POST

from accounts.decorators import manager_required
from purchases.models import Purchase

from .forms import SupplierForm, SupplierPaymentForm
from .models import (
    Supplier,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from .services import (
    cancel_supplier_payment,
    post_supplier_payment,
    supplier_current_debt,
)


ZERO_MONEY = Decimal("0.00")


def supplier_queryset_with_debt():
    money_field = DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    purchase_balance_expression = ExpressionWrapper(
        F("total_amount") - F("amount_paid"),
        output_field=money_field,
    )

    purchase_debt_subquery = (
        Purchase.objects
        .filter(
            supplier=OuterRef("pk"),
            status=Purchase.Status.POSTED,
        )
        .values("supplier")
        .annotate(
            total=Sum(purchase_balance_expression)
        )
        .values("total")[:1]
    )

    return (
        Supplier.objects
        .annotate(
            remaining_opening_debt=ExpressionWrapper(
                F("opening_balance") - F("opening_balance_paid"),
                output_field=money_field,
            ),
            purchase_debt=Coalesce(
                Subquery(
                    purchase_debt_subquery,
                    output_field=money_field,
                ),
                Value(ZERO_MONEY),
                output_field=money_field,
            ),
        )
        .annotate(
            account_balance=ExpressionWrapper(
                F("remaining_opening_debt") + F("purchase_debt"),
                output_field=money_field,
            )
        )
    )


@manager_required
def supplier_list(request):
    search_query = request.GET.get("q", "").strip()

    suppliers = supplier_queryset_with_debt().order_by("name")

    if search_query:
        suppliers = suppliers.filter(
            Q(name__icontains=search_query)
            | Q(contact_person__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(tin__icontains=search_query)
        )

    supplier_id = (
        request.GET.get("edit")
        or request.POST.get("object_id")
    )

    supplier_instance = None

    if supplier_id:
        supplier_instance = get_object_or_404(
            Supplier,
            pk=supplier_id,
        )

    form = SupplierForm(
        request.POST or None,
        instance=supplier_instance,
    )

    modal_open = bool(supplier_instance)

    if request.method == "POST":
        modal_open = True

        if form.is_valid():
            supplier = form.save()

            messages.success(
                request,
                f'Supplier "{supplier.name}" saved successfully.',
            )

            return redirect("supplier-list")

    all_suppliers = supplier_queryset_with_debt()

    totals = all_suppliers.aggregate(
        total_opening_balance=Coalesce(
            Sum("opening_balance"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        ),
        total_supplier_payable=Coalesce(
            Sum("account_balance"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        ),
    )

    context = {
        "page_title": "Suppliers",
        "suppliers": suppliers,
        "form": form,
        "editing_supplier": supplier_instance,
        "modal_open": modal_open,
        "search_query": search_query,
        "supplier_count": all_suppliers.count(),
        "active_supplier_count": all_suppliers.filter(
            is_active=True
        ).count(),
        "inactive_supplier_count": all_suppliers.filter(
            is_active=False
        ).count(),
        "total_opening_balance": totals[
            "total_opening_balance"
        ],
        "total_supplier_payable": totals[
            "total_supplier_payable"
        ],
    }

    return render(
        request,
        "suppliers/supplier_list.html",
        context,
    )


@manager_required
def supplier_account_list(request):
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get(
        "status",
        "payables",
    ).strip()

    suppliers = supplier_queryset_with_debt()

    if search_query:
        suppliers = suppliers.filter(
            Q(name__icontains=search_query)
            | Q(contact_person__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(tin__icontains=search_query)
        )

    if status_filter == "payables":
        suppliers = suppliers.filter(
            account_balance__gt=ZERO_MONEY
        )
    elif status_filter == "clear":
        suppliers = suppliers.filter(
            account_balance__lte=ZERO_MONEY
        )
    elif status_filter == "active":
        suppliers = suppliers.filter(is_active=True)
    elif status_filter == "inactive":
        suppliers = suppliers.filter(is_active=False)

    all_accounts = supplier_queryset_with_debt()

    totals = all_accounts.aggregate(
        total_payable=Coalesce(
            Sum("account_balance"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        )
    )

    payments_made = (
        SupplierPayment.objects
        .filter(status=SupplierPayment.Status.POSTED)
        .aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    paginator = Paginator(
        suppliers.order_by(
            "-account_balance",
            "name",
        ),
        25,
    )
    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Supplier Accounts",
        "suppliers": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "supplier_count": all_accounts.count(),
        "payable_count": all_accounts.filter(
            account_balance__gt=ZERO_MONEY
        ).count(),
        "clear_count": all_accounts.filter(
            account_balance__lte=ZERO_MONEY
        ).count(),
        "total_payable": totals["total_payable"],
        "payments_made": payments_made,
    }

    return render(
        request,
        "suppliers/account_list.html",
        context,
    )


@manager_required
def supplier_account_detail(request, pk):
    supplier = get_object_or_404(
        Supplier,
        pk=pk,
    )

    posted_purchases = list(
        Purchase.objects
        .filter(
            supplier=supplier,
            status=Purchase.Status.POSTED,
        )
        .order_by(
            "purchase_date",
            "id",
        )
    )

    payments = (
        SupplierPayment.objects
        .filter(supplier=supplier)
        .select_related(
            "created_by",
            "cancelled_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__purchase",
        )
        .order_by(
            "-payment_date",
            "-id",
        )
    )

    later_allocations = (
        SupplierPaymentAllocation.objects
        .filter(
            payment__supplier=supplier,
            payment__status=SupplierPayment.Status.POSTED,
            allocation_type=(
                SupplierPaymentAllocation.AllocationType.PURCHASE
            ),
            purchase__isnull=False,
        )
        .values("purchase_id")
        .annotate(total=Sum("amount"))
    )

    later_paid_by_purchase = {
        row["purchase_id"]: row["total"] or ZERO_MONEY
        for row in later_allocations
    }

    statement_entries = []

    if supplier.opening_balance > ZERO_MONEY:
        statement_entries.append(
            {
                "date": supplier.created_at,
                "entry_type": "Opening balance",
                "reference": f"SUP-{supplier.pk}",
                "description": (
                    "Supplier debt recorded before system usage"
                ),
                "debit": supplier.opening_balance,
                "credit": ZERO_MONEY,
            }
        )

    for purchase in posted_purchases:
        later_paid = later_paid_by_purchase.get(
            purchase.id,
            ZERO_MONEY,
        )
        initial_paid = max(
            purchase.amount_paid - later_paid,
            ZERO_MONEY,
        )

        statement_entries.append(
            {
                "date": timezone.make_aware(
                    datetime.combine(
                        purchase.purchase_date,
                        time(hour=12),
                    )
                ),
                "entry_type": "Purchase",
                "reference": purchase.purchase_number,
                "description": (
                    f"Posted purchase using "
                    f"{purchase.get_payment_method_display()}"
                ),
                "debit": purchase.total_amount,
                "credit": initial_paid,
            }
        )

    for payment in payments:
        if payment.status != SupplierPayment.Status.POSTED:
            continue

        statement_entries.append(
            {
                "date": payment.payment_date,
                "entry_type": "Supplier payment",
                "reference": payment.payment_number,
                "description": payment.get_payment_method_display(),
                "debit": ZERO_MONEY,
                "credit": payment.amount,
            }
        )

    statement_entries.sort(
        key=lambda entry: (
            entry["date"],
            entry["reference"],
        )
    )

    running_balance = ZERO_MONEY

    for entry in statement_entries:
        running_balance = (
            running_balance
            + entry["debit"]
            - entry["credit"]
        )
        entry["balance"] = running_balance

    total_purchases = sum(
        (purchase.total_amount for purchase in posted_purchases),
        ZERO_MONEY,
    )
    total_paid_on_purchases = sum(
        (purchase.amount_paid for purchase in posted_purchases),
        ZERO_MONEY,
    )

    context = {
        "page_title": supplier.name,
        "supplier": supplier,
        "current_debt": supplier_current_debt(supplier),
        "remaining_opening_balance": (
            supplier.remaining_opening_balance
        ),
        "posted_purchases": posted_purchases,
        "payments": payments,
        "statement_entries": statement_entries,
        "total_purchases": total_purchases,
        "total_paid_on_purchases": total_paid_on_purchases,
    }

    return render(
        request,
        "suppliers/account_detail.html",
        context,
    )


@manager_required
def supplier_payment_create(request, pk):
    supplier = get_object_or_404(
        Supplier,
        pk=pk,
    )

    current_debt = supplier_current_debt(supplier)

    if current_debt <= ZERO_MONEY:
        messages.error(
            request,
            "This supplier has no outstanding balance.",
        )
        return redirect(
            "supplier-account-detail",
            pk=supplier.pk,
        )

    payment = SupplierPayment(
        supplier=supplier,
        created_by=request.user,
        payment_date=timezone.now(),
    )

    form = SupplierPaymentForm(
        request.POST or None,
        instance=payment,
        maximum_amount=current_debt,
    )

    if request.method == "POST" and form.is_valid():
        try:
            payment = post_supplier_payment(
                supplier_id=supplier.id,
                amount=form.cleaned_data["amount"],
                payment_method=form.cleaned_data[
                    "payment_method"
                ],
                payment_date=form.cleaned_data[
                    "payment_date"
                ],
                reference=form.cleaned_data["reference"],
                notes=form.cleaned_data["notes"],
                user=request.user,
            )

            messages.success(
                request,
                (
                    f"Supplier payment "
                    f"{payment.payment_number} posted successfully."
                ),
            )

            return redirect(
                "supplier-payment-detail",
                pk=payment.pk,
            )

        except ValidationError as error:
            form.add_error(None, error.messages[0])

    context = {
        "page_title": "Record Supplier Payment",
        "supplier": supplier,
        "current_debt": current_debt,
        "form": form,
    }

    return render(
        request,
        "suppliers/payment_form.html",
        context,
    )


@manager_required
def supplier_payment_detail(request, pk):
    payment = get_object_or_404(
        SupplierPayment.objects
        .select_related(
            "supplier",
            "created_by",
            "cancelled_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__purchase",
        ),
        pk=pk,
    )

    context = {
        "page_title": payment.payment_number,
        "payment": payment,
        "remaining_balance": supplier_current_debt(
            payment.supplier
        ),
    }

    return render(
        request,
        "suppliers/payment_detail.html",
        context,
    )


@manager_required
def supplier_payment_receipt(request, pk):
    payment = get_object_or_404(
        SupplierPayment.objects
        .select_related(
            "supplier",
            "created_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__purchase",
        ),
        pk=pk,
        status=SupplierPayment.Status.POSTED,
    )

    context = {
        "payment": payment,
        "remaining_balance": supplier_current_debt(
            payment.supplier
        ),
    }

    return render(
        request,
        "suppliers/payment_receipt.html",
        context,
    )


@manager_required
@require_POST
def supplier_payment_cancel(request, pk):
    payment = get_object_or_404(
        SupplierPayment,
        pk=pk,
    )

    reason = request.POST.get("reason", "").strip()

    try:
        cancel_supplier_payment(
            payment_id=payment.id,
            user=request.user,
            reason=reason,
        )

        messages.success(
            request,
            (
                f"Supplier payment {payment.payment_number} "
                f"cancelled successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "supplier-payment-detail",
        pk=payment.pk,
    )
