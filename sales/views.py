from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
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
from django.views.decorators.http import require_POST

from products.models import Product

from .forms import (
    CustomerCuttingServiceForm,
    SaleForm,
    SaleItemFormSet,
)
from .models import (
    CustomerCuttingService,
    Sale,
    SaleItem,
)
from .services import (
    complete_customer_cutting_service,
    complete_sale,
)


ZERO_MONEY = Decimal("0.00")
ZERO_QUANTITY = Decimal("0.000")


def get_sale_product_data():
    products = (
        Product.objects
        .filter(
            is_active=True,
            track_stock=True,
        )
        .select_related("category")
        .annotate(
            available_stock=Coalesce(
                Sum(
                    "stock_batches__remaining_quantity",
                    filter=Q(
                        stock_batches__is_active=True,
                        stock_batches__remaining_quantity__gt=0,
                    ),
                ),
                Value(ZERO_QUANTITY),
                output_field=DecimalField(
                    max_digits=16,
                    decimal_places=3,
                ),
            )
        )
        .order_by(
            "category__name",
            "name",
        )
    )

    product_data = []

    for product in products:
        product_data.append(
            {
                "id": product.id,
                "name": product.name,
                "code": product.code,
                "category": product.category.name,
                "unit": (
                    product.get_measurement_unit_display()
                ),
                "selling_price": str(
                    product.selling_price
                ),
                "minimum_price": (
                    str(product.minimum_selling_price)
                    if product.minimum_selling_price
                    is not None
                    else ""
                ),
                "available_stock": str(
                    product.available_stock
                ),
                "allow_cutting": (
                    product.allow_customer_cutting
                ),
            }
        )

    return product_data

def product_default_cutting_fee(product):
    effective_fee = getattr(
        product,
        "effective_cutting_fee",
        None,
    )

    if callable(effective_fee):
        effective_fee = effective_fee()

    if effective_fee is not None:
        return Decimal(
            str(effective_fee)
        )

    product_fee = getattr(
        product,
        "default_cutting_fee",
        None,
    )

    if (
        product_fee is not None
        and product_fee > 0
    ):
        return Decimal(
            str(product_fee)
        )

    category_fee = getattr(
        product.category,
        "default_cutting_fee",
        None,
    )

    if category_fee is not None:
        return Decimal(
            str(category_fee)
        )

    return ZERO_MONEY


def get_cutting_item_data(sale):
    items = (
        sale.items
        .filter(
            product__category__code="TIMBER",
            product__is_active=True,
        )
        .select_related(
            "product",
            "product__category",
        )
        .order_by(
            "product__name"
        )
    )

    return [
        {
            "id": item.id,
            "product_name": item.product.name,
            "product_code": item.product.code,
            "quantity_sold": str(
                item.quantity
            ),
            "default_fee": str(
                product_default_cutting_fee(
                    item.product
                )
            ),
        }
        for item in items
    ]


@login_required
def sale_list(request):
    search_query = request.GET.get(
        "q",
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

    sales = (
        Sale.objects
        .select_related(
            "customer",
            "created_by",
            "completed_by",
        )
        .prefetch_related(
            "items",
            "items__product",
        )
        .order_by(
            "-sale_date",
            "-id",
        )
    )

    if search_query:
        sales = sales.filter(
            Q(sale_number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(customer__phone__icontains=search_query)
            | Q(items__product__name__icontains=search_query)
            | Q(items__product__code__icontains=search_query)
        ).distinct()

    valid_statuses = {
        choice[0]
        for choice in Sale.Status.choices
    }

    if status_filter in valid_statuses:
        sales = sales.filter(
            status=status_filter
        )

    valid_payment_methods = {
        choice[0]
        for choice in Sale.PaymentMethod.choices
    }

    if payment_filter in valid_payment_methods:
        sales = sales.filter(
            payment_method=payment_filter
        )

    if date_from:
        sales = sales.filter(
            sale_date__date__gte=date_from
        )

    if date_to:
        sales = sales.filter(
            sale_date__date__lte=date_to
        )

    all_sales = Sale.objects.all()

    completed_sales = all_sales.filter(
        status=Sale.Status.COMPLETED
    )

    outstanding_expression = ExpressionWrapper(
        F("total_amount") - F("amount_paid"),
        output_field=DecimalField(
            max_digits=18,
            decimal_places=2,
        ),
    )

    totals = completed_sales.aggregate(
        total_sales=Coalesce(
            Sum("total_amount"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_paid=Coalesce(
            Sum("amount_paid"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_outstanding=Coalesce(
            Sum(outstanding_expression),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_sale_discounts=Coalesce(
            Sum("discount"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
    )

    item_profit_total = (
        SaleItem.objects
        .filter(
            sale__status=Sale.Status.COMPLETED
        )
        .aggregate(
            total=Coalesce(
                Sum("profit_amount"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    total_profit = (
        item_profit_total
        - totals["total_sale_discounts"]
    )

    paginator = Paginator(
        sales,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Sales",
        "sales": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
        "date_from": date_from,
        "date_to": date_to,
        "payment_methods": (
            Sale.PaymentMethod.choices
        ),
        "sale_count": all_sales.count(),
        "completed_count": completed_sales.count(),
        "draft_count": all_sales.filter(
            status=Sale.Status.DRAFT
        ).count(),
        "total_sales": totals["total_sales"],
        "total_paid": totals["total_paid"],
        "total_outstanding": totals[
            "total_outstanding"
        ],
        "total_profit": total_profit,
    }

    return render(
        request,
        "sales/sale_list.html",
        context,
    )


@login_required
def sale_create(request):
    sale = Sale(
        created_by=request.user,
        sale_date=timezone.now(),
    )

    form = SaleForm(
        request.POST or None,
        instance=sale,
    )

    formset = SaleItemFormSet(
        request.POST or None,
        instance=sale,
        prefix="items",
    )

    if request.method == "POST":
        form_is_valid = form.is_valid()

        if form_is_valid:
            sale = form.save(
                commit=False
            )

            sale.created_by = request.user
            sale.status = Sale.Status.DRAFT

            formset.instance = sale

        formset_is_valid = formset.is_valid()

        if form_is_valid and formset_is_valid:
            with transaction.atomic():
                sale.save()

                formset.instance = sale
                formset.save()

            if "save_and_complete" in request.POST:
                try:
                    complete_sale(
                        sale_id=sale.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Sale {sale.sale_number} "
                            f"completed successfully."
                        ),
                    )

                    return redirect(
                        "sale-detail",
                        pk=sale.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "sale-edit",
                        pk=sale.pk,
                    )

            messages.success(
                request,
                (
                    f"Sale {sale.sale_number} "
                    f"saved as draft."
                ),
            )

            return redirect(
                "sale-detail",
                pk=sale.pk,
            )

    context = {
        "page_title": "New Sale",
        "form": form,
        "formset": formset,
        "sale": sale,
        "is_editing": False,
        "product_data": get_sale_product_data(),
    }

    return render(
        request,
        "sales/sale_form.html",
        context,
    )


@login_required
def sale_edit(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related(
            "items"
        ),
        pk=pk,
    )

    if sale.status != Sale.Status.DRAFT:
        messages.error(
            request,
            "Only draft sales can be edited.",
        )

        return redirect(
            "sale-detail",
            pk=sale.pk,
        )

    form = SaleForm(
        request.POST or None,
        instance=sale,
    )

    formset = SaleItemFormSet(
        request.POST or None,
        instance=sale,
        prefix="items",
    )

    if request.method == "POST":
        form_is_valid = form.is_valid()

        if form_is_valid:
            sale = form.save(
                commit=False
            )

            formset.instance = sale

        formset_is_valid = formset.is_valid()

        if form_is_valid and formset_is_valid:
            with transaction.atomic():
                sale.save()
                formset.save()

            if "save_and_complete" in request.POST:
                try:
                    complete_sale(
                        sale_id=sale.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Sale {sale.sale_number} "
                            f"completed successfully."
                        ),
                    )

                    return redirect(
                        "sale-detail",
                        pk=sale.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "sale-edit",
                        pk=sale.pk,
                    )

            messages.success(
                request,
                "Draft sale updated successfully.",
            )

            return redirect(
                "sale-detail",
                pk=sale.pk,
            )

    context = {
        "page_title": "Edit Sale",
        "form": form,
        "formset": formset,
        "sale": sale,
        "is_editing": True,
        "product_data": get_sale_product_data(),
    }

    return render(
        request,
        "sales/sale_form.html",
        context,
    )


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects
        .select_related(
            "customer",
            "created_by",
            "completed_by",
        )
        .prefetch_related(
            "items",
            "items__product",
            "items__product__category",
            "items__batch_usages",
            "items__batch_usages__batch",
            "items__batch_usages__batch__supplier",
            "cutting_services",
            "cutting_services__sale_item",
            "cutting_services__sale_item__product",
        ),
        pk=pk,
    )

    has_cuttable_items = sale.items.filter(
        product__category__code="TIMBER",
    ).exists()

    completed_cutting_services = (
        sale.cutting_services.filter(
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            )
        )
    )

    cutting_totals = (
        completed_cutting_services.aggregate(
            total_fee=Coalesce(
                Sum("total_fee"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            ),
            total_paid=Coalesce(
                Sum("amount_paid"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            ),
        )
    )

    cutting_total_fee = cutting_totals[
        "total_fee"
    ]

    cutting_total_paid = cutting_totals[
        "total_paid"
    ]

    cutting_total_balance = (
        cutting_total_fee
        - cutting_total_paid
    )

    context = {
        "page_title": sale.sale_number,
        "sale": sale,
        "has_cuttable_items": (
            has_cuttable_items
        ),
        "cutting_total_fee": (
            cutting_total_fee
        ),
        "cutting_total_paid": (
            cutting_total_paid
        ),
        "cutting_total_balance": (
            cutting_total_balance
        ),
    }

    return render(
        request,
        "sales/sale_detail.html",
        context,
    )

@login_required
def sale_receipt(request, pk):
    sale = get_object_or_404(
        Sale.objects
        .select_related(
            "customer",
            "created_by",
            "completed_by",
        )
        .prefetch_related(
            "items",
            "items__product",
        ),
        pk=pk,
        status=Sale.Status.COMPLETED,
    )

    context = {
        "sale": sale,
    }

    return render(
        request,
        "sales/sale_receipt.html",
        context,
    )


@login_required
@require_POST
def sale_complete(request, pk):
    sale = get_object_or_404(
        Sale,
        pk=pk,
    )

    try:
        complete_sale(
            sale_id=sale.id,
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Sale {sale.sale_number} "
                f"completed successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "sale-detail",
        pk=sale.pk,
    )


@login_required
@require_POST
def sale_cancel(request, pk):
    sale = get_object_or_404(
        Sale,
        pk=pk,
    )

    if sale.status != Sale.Status.DRAFT:
        messages.error(
            request,
            "Only draft sales can be cancelled.",
        )

        return redirect(
            "sale-detail",
            pk=sale.pk,
        )

    sale.status = Sale.Status.CANCELLED

    sale.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"Sale {sale.sale_number} "
            f"cancelled successfully."
        ),
    )

    return redirect(
        "sale-detail",
        pk=sale.pk,
    )

@login_required
def cutting_service_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
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

    services = (
        CustomerCuttingService.objects
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
            "created_by",
            "completed_by",
        )
        .order_by(
            "-service_date",
            "-id",
        )
    )

    if search_query:
        services = services.filter(
            Q(
                cutting_number__icontains=
                search_query
            )
            | Q(
                sale__sale_number__icontains=
                search_query
            )
            | Q(
                sale__customer__name__icontains=
                search_query
            )
            | Q(
                sale_item__product__name__icontains=
                search_query
            )
            | Q(
                sale_item__product__code__icontains=
                search_query
            )
        )

    valid_statuses = {
        value
        for value, label
        in CustomerCuttingService.Status.choices
    }

    if status_filter in valid_statuses:
        services = services.filter(
            status=status_filter
        )

    if date_from:
        services = services.filter(
            service_date__date__gte=date_from
        )

    if date_to:
        services = services.filter(
            service_date__date__lte=date_to
        )

    all_services = (
        CustomerCuttingService.objects.all()
    )

    completed_services = all_services.filter(
        status=(
            CustomerCuttingService
            .Status
            .COMPLETED
        )
    )

    outstanding_expression = ExpressionWrapper(
        F("total_fee") - F("amount_paid"),
        output_field=DecimalField(
            max_digits=18,
            decimal_places=2,
        ),
    )

    totals = completed_services.aggregate(
        total_income=Coalesce(
            Sum("total_fee"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_paid=Coalesce(
            Sum("amount_paid"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_outstanding=Coalesce(
            Sum(outstanding_expression),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        ),
        total_cuts=Coalesce(
            Sum("number_of_cuts"),
            Value(0),
        ),
    )

    paginator = Paginator(
        services,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Customer Cutting",
        "services": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "service_count": all_services.count(),
        "completed_count": (
            completed_services.count()
        ),
        "draft_count": all_services.filter(
            status=(
                CustomerCuttingService
                .Status
                .DRAFT
            )
        ).count(),
        "total_income": totals["total_income"],
        "total_paid": totals["total_paid"],
        "total_outstanding": totals[
            "total_outstanding"
        ],
        "total_cuts": totals["total_cuts"],
    }

    return render(
        request,
        "sales/cutting_service_list.html",
        context,
    )


@login_required
def cutting_service_create(
    request,
    sale_pk,
):
    sale = get_object_or_404(
        Sale.objects
        .select_related("customer")
        .prefetch_related(
            "items",
            "items__product",
            "items__product__category",
        ),
        pk=sale_pk,
        status=Sale.Status.COMPLETED,
    )

    has_timber = sale.items.filter(
        product__category__code="TIMBER"
    ).exists()

    if not has_timber:
        messages.error(
            request,
            (
                "This sale does not contain any "
                "Timber product that can be cut."
            ),
        )

        return redirect(
            "sale-detail",
            pk=sale.pk,
        )

    cutting_service = (
        CustomerCuttingService(
            sale=sale,
            created_by=request.user,
            service_date=timezone.now(),
        )
    )

    form = CustomerCuttingServiceForm(
        request.POST or None,
        instance=cutting_service,
        sale=sale,
    )

    if request.method == "POST":
        if form.is_valid():
            cutting_service = form.save(
                commit=False
            )

            cutting_service.sale = sale
            cutting_service.created_by = (
                request.user
            )
            cutting_service.status = (
                CustomerCuttingService
                .Status
                .DRAFT
            )

            cutting_service.save()

            if (
                "save_and_complete"
                in request.POST
            ):
                try:
                    complete_customer_cutting_service(
                        cutting_service_id=(
                            cutting_service.id
                        ),
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Cutting service "
                            f"{cutting_service.cutting_number} "
                            f"completed successfully."
                        ),
                    )

                    return redirect(
                        "cutting-service-detail",
                        pk=cutting_service.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "cutting-service-edit",
                        pk=cutting_service.pk,
                    )

            messages.success(
                request,
                (
                    f"Cutting service "
                    f"{cutting_service.cutting_number} "
                    f"saved as draft."
                ),
            )

            return redirect(
                "cutting-service-detail",
                pk=cutting_service.pk,
            )

    context = {
        "page_title": "New Cutting Service",
        "form": form,
        "sale": sale,
        "cutting_service": cutting_service,
        "is_editing": False,
        "cutting_item_data": (
            get_cutting_item_data(sale)
        ),
    }

    return render(
        request,
        "sales/cutting_service_form.html",
        context,
    )


@login_required
def cutting_service_edit(request, pk):
    cutting_service = get_object_or_404(
        CustomerCuttingService.objects
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
        ),
        pk=pk,
    )

    if (
        cutting_service.status
        != CustomerCuttingService.Status.DRAFT
    ):
        messages.error(
            request,
            (
                "Only draft cutting services "
                "can be edited."
            ),
        )

        return redirect(
            "cutting-service-detail",
            pk=cutting_service.pk,
        )

    sale = cutting_service.sale

    form = CustomerCuttingServiceForm(
        request.POST or None,
        instance=cutting_service,
        sale=sale,
    )

    if (
        request.method == "POST"
        and form.is_valid()
    ):
        cutting_service = form.save()

        if "save_and_complete" in request.POST:
            try:
                complete_customer_cutting_service(
                    cutting_service_id=(
                        cutting_service.id
                    ),
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        f"Cutting service "
                        f"{cutting_service.cutting_number} "
                        f"completed successfully."
                    ),
                )

                return redirect(
                    "cutting-service-detail",
                    pk=cutting_service.pk,
                )

            except ValidationError as error:
                messages.error(
                    request,
                    error.messages[0],
                )

                return redirect(
                    "cutting-service-edit",
                    pk=cutting_service.pk,
                )

        messages.success(
            request,
            "Draft cutting service updated.",
        )

        return redirect(
            "cutting-service-detail",
            pk=cutting_service.pk,
        )

    context = {
        "page_title": "Edit Cutting Service",
        "form": form,
        "sale": sale,
        "cutting_service": cutting_service,
        "is_editing": True,
        "cutting_item_data": (
            get_cutting_item_data(sale)
        ),
    }

    return render(
        request,
        "sales/cutting_service_form.html",
        context,
    )


@login_required
def cutting_service_detail(request, pk):
    cutting_service = get_object_or_404(
        CustomerCuttingService.objects
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
            "sale_item__product__category",
            "created_by",
            "completed_by",
        ),
        pk=pk,
    )

    context = {
        "page_title": (
            cutting_service.cutting_number
        ),
        "cutting_service": cutting_service,
    }

    return render(
        request,
        "sales/cutting_service_detail.html",
        context,
    )


@login_required
@require_POST
def cutting_service_complete(request, pk):
    cutting_service = get_object_or_404(
        CustomerCuttingService,
        pk=pk,
    )

    try:
        complete_customer_cutting_service(
            cutting_service_id=(
                cutting_service.id
            ),
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Cutting service "
                f"{cutting_service.cutting_number} "
                f"completed successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "cutting-service-detail",
        pk=cutting_service.pk,
    )


@login_required
@require_POST
def cutting_service_cancel(request, pk):
    cutting_service = get_object_or_404(
        CustomerCuttingService,
        pk=pk,
    )

    if (
        cutting_service.status
        != CustomerCuttingService.Status.DRAFT
    ):
        messages.error(
            request,
            (
                "Only draft cutting services "
                "can be cancelled."
            ),
        )

        return redirect(
            "cutting-service-detail",
            pk=cutting_service.pk,
        )

    cutting_service.status = (
        CustomerCuttingService.Status.CANCELLED
    )

    cutting_service.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"Cutting service "
            f"{cutting_service.cutting_number} "
            f"cancelled."
        ),
    )

    return redirect(
        "cutting-service-detail",
        pk=cutting_service.pk,
    )