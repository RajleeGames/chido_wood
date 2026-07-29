from decimal import Decimal
from django.core.exceptions import ValidationError
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
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import manager_required
from sales.models import (
    CustomerCuttingService,
    Sale,
)

from .forms import (
    CustomerForm,
    CustomerPaymentForm,
)
from .models import (
    Customer,
    CustomerPayment,
)
from .services import (
    cancel_customer_payment,
    customer_current_debt,
    post_customer_payment,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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

from .forms import CustomerForm
from .models import Customer


ZERO_MONEY = Decimal("0.00")


@login_required
def customer_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    customers = Customer.objects.all()

    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query)
            | Q(customer_code__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(address__icontains=search_query)
        )

    if status_filter == "active":
        customers = customers.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        customers = customers.filter(
            is_active=False
        )

    customer_id = (
        request.GET.get("edit")
        or request.POST.get("object_id")
    )

    customer_instance = None

    if customer_id:
        customer_instance = get_object_or_404(
            Customer,
            pk=customer_id,
        )

    form = CustomerForm(
        request.POST or None,
        instance=customer_instance,
    )

    modal_open = bool(customer_instance)

    if request.method == "POST":
        modal_open = True

        if form.is_valid():
            customer = form.save(
                commit=False
            )

            if not customer.pk:
                customer.created_by = request.user

            customer.save()

            messages.success(
                request,
                (
                    f'Customer "{customer.name}" '
                    f"saved successfully."
                ),
            )

            return redirect(
                "customer-list"
            )

    all_customers = Customer.objects.all()

    active_customer_count = all_customers.filter(
        is_active=True
    ).count()

    inactive_customer_count = all_customers.filter(
        is_active=False
    ).count()

    customers_with_phone_count = (
        all_customers
        .exclude(phone="")
        .count()
    )

    customer_totals = all_customers.aggregate(
        total_opening_balance=Coalesce(
            Sum("opening_balance"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_credit_limit=Coalesce(
            Sum("credit_limit"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
    )

    paginator = Paginator(
        customers.order_by(
            "name",
            "id",
        ),
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Customers",
        "customers": page_obj.object_list,
        "page_obj": page_obj,
        "form": form,
        "editing_customer": customer_instance,
        "modal_open": modal_open,
        "search_query": search_query,
        "status_filter": status_filter,
        "customer_count": all_customers.count(),
        "active_customer_count": active_customer_count,
        "inactive_customer_count": inactive_customer_count,
        "customers_with_phone_count": (
            customers_with_phone_count
        ),
        "total_opening_balance": customer_totals[
            "total_opening_balance"
        ],
        "total_credit_limit": customer_totals[
            "total_credit_limit"
        ],
    }

    return render(
        request,
        "customers/customer_list.html",
        context,
    )


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related(
            "created_by"
        ),
        pk=pk,
    )

    context = {
        "page_title": customer.name,
        "customer": customer,
    }

    return render(
        request,
        "customers/customer_detail.html",
        context,
    )

def customer_queryset_with_debt():
    sale_balance_expression = ExpressionWrapper(
        F("total_amount") - F("amount_paid"),
        output_field=DecimalField(
            max_digits=18,
            decimal_places=2,
        ),
    )

    sale_debt_subquery = (
        Sale.objects
        .filter(
            customer=OuterRef("pk"),
            status=Sale.Status.COMPLETED,
        )
        .values("customer")
        .annotate(
            total=Sum(
                sale_balance_expression
            )
        )
        .values("total")[:1]
    )

    cutting_balance_expression = (
        ExpressionWrapper(
            F("total_fee") - F("amount_paid"),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        )
    )

    cutting_debt_subquery = (
        CustomerCuttingService.objects
        .filter(
            sale__customer=OuterRef("pk"),
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
        )
        .values("sale__customer")
        .annotate(
            total=Sum(
                cutting_balance_expression
            )
        )
        .values("total")[:1]
    )

    money_field = DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    return (
        Customer.objects
        .annotate(
            remaining_opening_debt=(
                ExpressionWrapper(
                    F("opening_balance")
                    - F("opening_balance_paid"),
                    output_field=money_field,
                )
            ),
            sale_debt=Coalesce(
                Subquery(
                    sale_debt_subquery,
                    output_field=money_field,
                ),
                Value(ZERO_MONEY),
                output_field=money_field,
            ),
            cutting_debt=Coalesce(
                Subquery(
                    cutting_debt_subquery,
                    output_field=money_field,
                ),
                Value(ZERO_MONEY),
                output_field=money_field,
            ),
        )
        .annotate(
            account_balance=ExpressionWrapper(
                F("remaining_opening_debt")
                + F("sale_debt")
                + F("cutting_debt"),
                output_field=money_field,
            )
        )
    )


@login_required
def customer_account_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "debtors",
    ).strip()

    customers = customer_queryset_with_debt()

    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(customer_code__icontains=search_query)
        )

    if status_filter == "debtors":
        customers = customers.filter(
            account_balance__gt=ZERO_MONEY
        )

    elif status_filter == "clear":
        customers = customers.filter(
            account_balance__lte=ZERO_MONEY
        )

    elif status_filter == "active":
        customers = customers.filter(
            is_active=True
        )

    elif status_filter == "inactive":
        customers = customers.filter(
            is_active=False
        )

    all_accounts = customer_queryset_with_debt()

    total_debt = (
        all_accounts.aggregate(
            total=Coalesce(
                Sum("account_balance"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    debtor_count = all_accounts.filter(
        account_balance__gt=ZERO_MONEY
    ).count()

    clear_count = all_accounts.filter(
        account_balance__lte=ZERO_MONEY
    ).count()

    payments_collected = (
        CustomerPayment.objects
        .filter(
            status=CustomerPayment.Status.POSTED
        )
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
        customers.order_by(
            "-account_balance",
            "name",
        ),
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Customer Accounts",
        "customers": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "customer_count": all_accounts.count(),
        "debtor_count": debtor_count,
        "clear_count": clear_count,
        "total_debt": total_debt,
        "payments_collected": payments_collected,
    }

    return render(
        request,
        "customers/account_list.html",
        context,
    )


@login_required
def customer_account_detail(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related(
            "created_by"
        ),
        pk=pk,
    )

    completed_sales = list(
        Sale.objects
        .filter(
            customer=customer,
            status=Sale.Status.COMPLETED,
        )
        .order_by(
            "sale_date",
            "id",
        )
    )

    cutting_services = list(
        CustomerCuttingService.objects
        .filter(
            sale__customer=customer,
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
        )
        .select_related(
            "sale",
            "sale_item",
            "sale_item__product",
        )
        .order_by(
            "service_date",
            "id",
        )
    )

    payments = (
        CustomerPayment.objects
        .filter(customer=customer)
        .select_related(
            "created_by",
            "cancelled_by",
        )
        .prefetch_related(
            "allocations",
        )
        .order_by(
            "-payment_date",
            "-id",
        )
    )

    statement_entries = []

    if customer.opening_balance > ZERO_MONEY:
        statement_entries.append(
            {
                "date": customer.created_at,
                "entry_type": "Opening balance",
                "reference": customer.customer_code,
                "description": (
                    "Customer debt recorded before "
                    "system usage"
                ),
                "debit": customer.opening_balance,
                "credit": ZERO_MONEY,
            }
        )

    for sale in completed_sales:
        initial_paid = min(
            sale.amount_tendered,
            sale.total_amount,
        )

        statement_entries.append(
            {
                "date": sale.sale_date,
                "entry_type": "Credit sale",
                "reference": sale.sale_number,
                "description": (
                    f"Completed sale using "
                    f"{sale.get_payment_method_display()}"
                ),
                "debit": sale.total_amount,
                "credit": initial_paid,
            }
        )

    for service in cutting_services:
        initial_paid = min(
            service.amount_tendered,
            service.total_fee,
        )

        statement_entries.append(
            {
                "date": service.service_date,
                "entry_type": "Cutting service",
                "reference": service.cutting_number,
                "description": (
                    f"{service.product.name} customer cutting"
                ),
                "debit": service.total_fee,
                "credit": initial_paid,
            }
        )

    for payment in payments:
        if payment.status != CustomerPayment.Status.POSTED:
            continue

        statement_entries.append(
            {
                "date": payment.payment_date,
                "entry_type": "Customer payment",
                "reference": payment.payment_number,
                "description": (
                    payment.get_payment_method_display()
                ),
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

    current_debt = customer_current_debt(
        customer
    )

    context = {
        "page_title": customer.name,
        "customer": customer,
        "current_debt": current_debt,
        "remaining_opening_balance": (
            customer.remaining_opening_balance
        ),
        "completed_sales": completed_sales,
        "cutting_services": cutting_services,
        "payments": payments,
        "statement_entries": statement_entries,
    }

    return render(
        request,
        "customers/account_detail.html",
        context,
    )


@login_required
def customer_payment_create(request, pk):
    customer = get_object_or_404(
        Customer,
        pk=pk,
    )

    current_debt = customer_current_debt(
        customer
    )

    if current_debt <= ZERO_MONEY:
        messages.error(
            request,
            "This customer has no outstanding balance.",
        )

        return redirect(
            "customer-account-detail",
            pk=customer.pk,
        )

    payment = CustomerPayment(
        customer=customer,
        created_by=request.user,
        payment_date=timezone.now(),
    )

    form = CustomerPaymentForm(
        request.POST or None,
        instance=payment,
        maximum_amount=current_debt,
    )

    if request.method == "POST" and form.is_valid():
        try:
            payment = post_customer_payment(
                customer_id=customer.id,
                amount=form.cleaned_data["amount"],
                payment_method=(
                    form.cleaned_data[
                        "payment_method"
                    ]
                ),
                payment_date=(
                    form.cleaned_data[
                        "payment_date"
                    ]
                ),
                reference=(
                    form.cleaned_data[
                        "reference"
                    ]
                ),
                notes=form.cleaned_data["notes"],
                user=request.user,
            )

            messages.success(
                request,
                (
                    f"Payment {payment.payment_number} "
                    f"posted successfully."
                ),
            )

            return redirect(
                "customer-payment-detail",
                pk=payment.pk,
            )

        except ValidationError as error:
            form.add_error(
                None,
                error.messages[0],
            )

    context = {
        "page_title": "Record Customer Payment",
        "customer": customer,
        "current_debt": current_debt,
        "form": form,
    }

    return render(
        request,
        "customers/payment_form.html",
        context,
    )


@login_required
def customer_payment_detail(request, pk):
    payment = get_object_or_404(
        CustomerPayment.objects
        .select_related(
            "customer",
            "created_by",
            "cancelled_by",
        )
        .prefetch_related(
            "allocations",
            "allocations__sale",
            "allocations__cutting_service",
        ),
        pk=pk,
    )

    remaining_balance = customer_current_debt(
        payment.customer
    )

    context = {
        "page_title": payment.payment_number,
        "payment": payment,
        "remaining_balance": remaining_balance,
    }

    return render(
        request,
        "customers/payment_detail.html",
        context,
    )


@login_required
def customer_payment_receipt(request, pk):
    payment = get_object_or_404(
        CustomerPayment.objects.select_related(
            "customer",
            "created_by",
        ),
        pk=pk,
        status=CustomerPayment.Status.POSTED,
    )

    remaining_balance = customer_current_debt(
        payment.customer
    )

    context = {
        "payment": payment,
        "remaining_balance": remaining_balance,
    }

    return render(
        request,
        "customers/payment_receipt.html",
        context,
    )


@manager_required
@require_POST
def customer_payment_cancel(request, pk):
    payment = get_object_or_404(
        CustomerPayment,
        pk=pk,
    )

    reason = request.POST.get(
        "reason",
        "",
    ).strip()

    try:
        cancel_customer_payment(
            payment_id=payment.id,
            user=request.user,
            reason=reason,
        )

        messages.success(
            request,
            (
                f"Payment {payment.payment_number} "
                f"cancelled successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "customer-payment-detail",
        pk=payment.pk,
    )