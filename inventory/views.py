from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import (
    Count,
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
from django.views.decorators.http import require_POST

from accounts.decorators import manager_required
from products.models import Category, Product

from .forms import (
    ConversionOutputFormSet,
    StockAdjustmentForm,
    WoodConversionForm,
)
from .models import (
    ConversionOutput,
    StockAdjustment,
    StockBatch,
    StockMovement,
    WoodConversion,
)
from .services import (
    post_stock_adjustment,
    post_wood_conversion,
)


ZERO_QUANTITY = Decimal("0.000")
ZERO_MONEY = Decimal("0.00")
ZERO_COST = Decimal("0.0000")

QUANTITY_PLACES = Decimal("0.001")
MONEY_PLACES = Decimal("0.01")
UNIT_COST_PLACES = Decimal("0.0001")


def round_quantity(value):
    return Decimal(str(value or 0)).quantize(
        QUANTITY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def round_money(value):
    return Decimal(str(value or 0)).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def round_unit_cost(value):
    return Decimal(str(value or 0)).quantize(
        UNIT_COST_PLACES,
        rounding=ROUND_HALF_UP,
    )


def active_batch_filter():
    return Q(
        stock_batches__is_active=True,
        stock_batches__remaining_quantity__gt=0,
    )


def inventory_products_queryset():
    batch_filter = active_batch_filter()

    batch_value_expression = ExpressionWrapper(
        F("stock_batches__remaining_quantity")
        * F("stock_batches__unit_cost"),
        output_field=DecimalField(
            max_digits=20,
            decimal_places=4,
        ),
    )

    return (
        Product.objects
        .filter(track_stock=True)
        .select_related("category")
        .annotate(
            current_stock=Coalesce(
                Sum(
                    "stock_batches__remaining_quantity",
                    filter=batch_filter,
                ),
                Value(ZERO_QUANTITY),
                output_field=DecimalField(
                    max_digits=16,
                    decimal_places=3,
                ),
            ),
            current_stock_value=Coalesce(
                Sum(
                    batch_value_expression,
                    filter=batch_filter,
                ),
                Value(ZERO_COST),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=4,
                ),
            ),
            active_batch_count=Count(
                "stock_batches",
                filter=batch_filter,
                distinct=True,
            ),
        )
        .order_by(
            "category__name",
            "name",
        )
    )


def prepare_product_inventory_values(product):
    product.current_stock = round_quantity(
        product.current_stock
    )

    product.current_stock_value = round_money(
        product.current_stock_value
    )

    if product.current_stock > ZERO_QUANTITY:
        product.average_unit_cost = round_unit_cost(
            product.current_stock_value
            / product.current_stock
        )
    else:
        product.average_unit_cost = ZERO_COST

    product.expected_selling_value = round_money(
        product.current_stock
        * product.selling_price
    )

    product.expected_profit = round_money(
        product.expected_selling_value
        - product.current_stock_value
    )

    if product.current_stock <= ZERO_QUANTITY:
        product.inventory_status = "out"
        product.inventory_status_label = "Out of stock"

    elif product.current_stock <= product.low_stock_level:
        product.inventory_status = "low"
        product.inventory_status_label = "Low stock"

    else:
        product.inventory_status = "available"
        product.inventory_status_label = "Available"

    return product


@manager_required
def inventory_list(request):
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

    products = inventory_products_queryset()

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(barcode__icontains=search_query)
        )

    if category_filter:
        products = products.filter(
            category_id=category_filter
        )

    if status_filter == "available":
        products = products.filter(
            current_stock__gt=F("low_stock_level")
        )

    elif status_filter == "low":
        products = products.filter(
            current_stock__gt=ZERO_QUANTITY,
            current_stock__lte=F("low_stock_level"),
        )

    elif status_filter == "out":
        products = products.filter(
            current_stock__lte=ZERO_QUANTITY
        )

    all_inventory_products = inventory_products_queryset()

    total_product_count = all_inventory_products.count()

    available_product_count = all_inventory_products.filter(
        current_stock__gt=F("low_stock_level")
    ).count()

    low_stock_count = all_inventory_products.filter(
        current_stock__gt=ZERO_QUANTITY,
        current_stock__lte=F("low_stock_level"),
    ).count()

    out_of_stock_count = all_inventory_products.filter(
        current_stock__lte=ZERO_QUANTITY
    ).count()

    stock_value_expression = ExpressionWrapper(
        F("remaining_quantity") * F("unit_cost"),
        output_field=DecimalField(
            max_digits=20,
            decimal_places=4,
        ),
    )

    selling_value_expression = ExpressionWrapper(
        F("remaining_quantity")
        * F("product__selling_price"),
        output_field=DecimalField(
            max_digits=20,
            decimal_places=4,
        ),
    )

    inventory_totals = (
        StockBatch.objects
        .filter(
            is_active=True,
            remaining_quantity__gt=0,
        )
        .aggregate(
            total_stock_quantity=Coalesce(
                Sum("remaining_quantity"),
                Value(ZERO_QUANTITY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=3,
                ),
            ),
            total_stock_value=Coalesce(
                Sum(stock_value_expression),
                Value(ZERO_COST),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=4,
                ),
            ),
            total_selling_value=Coalesce(
                Sum(selling_value_expression),
                Value(ZERO_COST),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=4,
                ),
            ),
        )
    )

    total_stock_quantity = round_quantity(
        inventory_totals["total_stock_quantity"]
    )

    total_stock_value = round_money(
        inventory_totals["total_stock_value"]
    )

    total_selling_value = round_money(
        inventory_totals["total_selling_value"]
    )

    total_expected_profit = round_money(
        total_selling_value - total_stock_value
    )

    paginator = Paginator(
        products,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    for product in page_obj.object_list:
        prepare_product_inventory_values(product)

    categories = (
        Category.objects
        .filter(is_active=True)
        .order_by("name")
    )

    context = {
        "page_title": "Inventory",
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "categories": categories,
        "search_query": search_query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "total_product_count": total_product_count,
        "available_product_count": available_product_count,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_stock_quantity": total_stock_quantity,
        "total_stock_value": total_stock_value,
        "total_selling_value": total_selling_value,
        "total_expected_profit": total_expected_profit,
    }

    return render(
        request,
        "inventory/inventory_list.html",
        context,
    )


@manager_required
def inventory_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=pk,
        track_stock=True,
    )

    batches = (
        StockBatch.objects
        .filter(product=product)
        .select_related(
            "supplier",
            "created_by",
        )
        .order_by(
            "-received_at",
            "-id",
        )
    )

    active_batches = batches.filter(
        is_active=True,
        remaining_quantity__gt=0,
    )

    stock_summary = active_batches.aggregate(
        current_stock=Coalesce(
            Sum("remaining_quantity"),
            Value(ZERO_QUANTITY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=3,
            ),
        ),
        received_stock=Coalesce(
            Sum("received_quantity"),
            Value(ZERO_QUANTITY),
            output_field=DecimalField(
                max_digits=18,
                decimal_places=3,
            ),
        ),
        stock_value=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("remaining_quantity")
                    * F("unit_cost"),
                    output_field=DecimalField(
                        max_digits=20,
                        decimal_places=4,
                    ),
                )
            ),
            Value(ZERO_COST),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=4,
            ),
        ),
    )

    current_stock = round_quantity(
        stock_summary["current_stock"]
    )

    received_stock = round_quantity(
        stock_summary["received_stock"]
    )

    stock_value = round_money(
        stock_summary["stock_value"]
    )

    if current_stock > ZERO_QUANTITY:
        average_unit_cost = round_unit_cost(
            stock_value / current_stock
        )
    else:
        average_unit_cost = ZERO_COST

    expected_selling_value = round_money(
        current_stock * product.selling_price
    )

    expected_profit = round_money(
        expected_selling_value - stock_value
    )

    if current_stock <= ZERO_QUANTITY:
        stock_status = "out"
        stock_status_label = "Out of stock"

    elif current_stock <= product.low_stock_level:
        stock_status = "low"
        stock_status_label = "Low stock"

    else:
        stock_status = "available"
        stock_status_label = "Available"

    movements = (
        StockMovement.objects
        .filter(product=product)
        .select_related(
            "batch",
            "created_by",
        )
        .order_by(
            "-created_at",
            "-id",
        )
    )

    movement_paginator = Paginator(
        movements,
        30,
    )

    movement_page = movement_paginator.get_page(
        request.GET.get("movement_page")
    )

    context = {
        "page_title": product.name,
        "product": product,
        "batches": batches,
        "movement_page": movement_page,
        "current_stock": current_stock,
        "received_stock": received_stock,
        "stock_value": stock_value,
        "average_unit_cost": average_unit_cost,
        "expected_selling_value": expected_selling_value,
        "expected_profit": expected_profit,
        "stock_status": stock_status,
        "stock_status_label": stock_status_label,
        "active_batch_count": active_batches.count(),
    }

    return render(
        request,
        "inventory/inventory_detail.html",
        context,
    )

@manager_required
def stock_adjustment_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    type_filter = request.GET.get(
        "type",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    adjustments = (
        StockAdjustment.objects
        .select_related(
            "product",
            "product__category",
            "created_by",
            "posted_by",
        )
        .order_by(
            "-adjustment_date",
            "-id",
        )
    )

    if search_query:
        adjustments = adjustments.filter(
            Q(
                adjustment_number__icontains=
                search_query
            )
            | Q(product__name__icontains=search_query)
            | Q(product__code__icontains=search_query)
            | Q(reason__icontains=search_query)
        )

    valid_types = {
        choice[0]
        for choice in StockAdjustment.AdjustmentType.choices
    }

    if type_filter in valid_types:
        adjustments = adjustments.filter(
            adjustment_type=type_filter
        )

    valid_statuses = {
        choice[0]
        for choice in StockAdjustment.Status.choices
    }

    if status_filter in valid_statuses:
        adjustments = adjustments.filter(
            status=status_filter
        )

    all_adjustments = StockAdjustment.objects.all()

    posted_adjustments = all_adjustments.filter(
        status=StockAdjustment.Status.POSTED
    )

    added_value = (
        posted_adjustments
        .filter(
            adjustment_type__in=[
                StockAdjustment.AdjustmentType.OPENING,
                StockAdjustment.AdjustmentType.INCREASE,
            ]
        )
        .aggregate(total=Sum("total_cost"))["total"]
        or Decimal("0.00")
    )

    removed_value = (
        posted_adjustments
        .filter(
            adjustment_type__in=[
                StockAdjustment.AdjustmentType.DECREASE,
                StockAdjustment.AdjustmentType.DAMAGE,
                StockAdjustment.AdjustmentType.WASTE,
            ]
        )
        .aggregate(total=Sum("total_cost"))["total"]
        or Decimal("0.00")
    )

    paginator = Paginator(
        adjustments,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Stock Adjustments",
        "adjustments": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "adjustment_types": (
            StockAdjustment.AdjustmentType.choices
        ),
        "adjustment_count": all_adjustments.count(),
        "draft_count": all_adjustments.filter(
            status=StockAdjustment.Status.DRAFT
        ).count(),
        "posted_count": posted_adjustments.count(),
        "added_value": added_value,
        "removed_value": removed_value,
    }

    return render(
        request,
        "inventory/adjustment_list.html",
        context,
    )


@manager_required
def stock_adjustment_create(request):
    adjustment = StockAdjustment(
        created_by=request.user,
    )

    form = StockAdjustmentForm(
        request.POST or None,
        instance=adjustment,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            adjustment = form.save(
                commit=False
            )

            adjustment.created_by = request.user
            adjustment.status = (
                StockAdjustment.Status.DRAFT
            )

            adjustment.save()

        if "save_and_post" in request.POST:
            try:
                post_stock_adjustment(
                    adjustment_id=adjustment.id,
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        f"Stock adjustment "
                        f"{adjustment.adjustment_number} "
                        f"posted successfully."
                    ),
                )

                return redirect(
                    "stock-adjustment-detail",
                    pk=adjustment.pk,
                )

            except ValidationError as error:
                messages.error(
                    request,
                    error.messages[0],
                )

                return redirect(
                    "stock-adjustment-edit",
                    pk=adjustment.pk,
                )

        messages.success(
            request,
            (
                f"Stock adjustment "
                f"{adjustment.adjustment_number} "
                f"saved as draft."
            ),
        )

        return redirect(
            "stock-adjustment-detail",
            pk=adjustment.pk,
        )

    context = {
        "page_title": "New Stock Adjustment",
        "form": form,
        "adjustment": adjustment,
        "is_editing": False,
    }

    return render(
        request,
        "inventory/adjustment_form.html",
        context,
    )


@manager_required
def stock_adjustment_edit(request, pk):
    adjustment = get_object_or_404(
        StockAdjustment,
        pk=pk,
    )

    if adjustment.status != StockAdjustment.Status.DRAFT:
        messages.error(
            request,
            "Only draft adjustments can be edited.",
        )

        return redirect(
            "stock-adjustment-detail",
            pk=adjustment.pk,
        )

    form = StockAdjustmentForm(
        request.POST or None,
        instance=adjustment,
    )

    if request.method == "POST" and form.is_valid():
        adjustment = form.save()

        if "save_and_post" in request.POST:
            try:
                post_stock_adjustment(
                    adjustment_id=adjustment.id,
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        f"Stock adjustment "
                        f"{adjustment.adjustment_number} "
                        f"posted successfully."
                    ),
                )

                return redirect(
                    "stock-adjustment-detail",
                    pk=adjustment.pk,
                )

            except ValidationError as error:
                messages.error(
                    request,
                    error.messages[0],
                )

                return redirect(
                    "stock-adjustment-edit",
                    pk=adjustment.pk,
                )

        messages.success(
            request,
            "Draft stock adjustment updated.",
        )

        return redirect(
            "stock-adjustment-detail",
            pk=adjustment.pk,
        )

    context = {
        "page_title": "Edit Stock Adjustment",
        "form": form,
        "adjustment": adjustment,
        "is_editing": True,
    }

    return render(
        request,
        "inventory/adjustment_form.html",
        context,
    )


@manager_required
def stock_adjustment_detail(request, pk):
    adjustment = get_object_or_404(
        StockAdjustment.objects
        .select_related(
            "product",
            "product__category",
            "created_batch",
            "created_by",
            "posted_by",
        )
        .prefetch_related(
            "batch_usages",
            "batch_usages__batch",
        ),
        pk=pk,
    )

    context = {
        "page_title": adjustment.adjustment_number,
        "adjustment": adjustment,
    }

    return render(
        request,
        "inventory/adjustment_detail.html",
        context,
    )


@manager_required
@require_POST
def stock_adjustment_post(request, pk):
    adjustment = get_object_or_404(
        StockAdjustment,
        pk=pk,
    )

    try:
        post_stock_adjustment(
            adjustment_id=adjustment.id,
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Stock adjustment "
                f"{adjustment.adjustment_number} "
                f"posted successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "stock-adjustment-detail",
        pk=adjustment.pk,
    )


@manager_required
@require_POST
def stock_adjustment_cancel(request, pk):
    adjustment = get_object_or_404(
        StockAdjustment,
        pk=pk,
    )

    if adjustment.status != StockAdjustment.Status.DRAFT:
        messages.error(
            request,
            "Only draft adjustments can be cancelled.",
        )

        return redirect(
            "stock-adjustment-detail",
            pk=adjustment.pk,
        )

    adjustment.status = StockAdjustment.Status.CANCELLED

    adjustment.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"Stock adjustment "
            f"{adjustment.adjustment_number} cancelled."
        ),
    )

    return redirect(
        "stock-adjustment-detail",
        pk=adjustment.pk,
    )

@manager_required
def wood_conversion_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    conversions = (
        WoodConversion.objects
        .select_related(
            "source_product",
            "source_product__category",
            "created_by",
            "posted_by",
        )
        .prefetch_related(
            "outputs",
            "outputs__product",
        )
        .order_by(
            "-conversion_date",
            "-id",
        )
    )

    if search_query:
        conversions = conversions.filter(
            Q(
                conversion_number__icontains=
                search_query
            )
            | Q(
                source_product__name__icontains=
                search_query
            )
            | Q(
                source_product__code__icontains=
                search_query
            )
            | Q(notes__icontains=search_query)
        )

    valid_statuses = {
        choice[0]
        for choice in WoodConversion.Status.choices
    }

    if status_filter in valid_statuses:
        conversions = conversions.filter(
            status=status_filter
        )

    all_conversions = WoodConversion.objects.all()

    posted_conversions = all_conversions.filter(
        status=WoodConversion.Status.POSTED
    )

    totals = posted_conversions.aggregate(
        total_source_cost=Coalesce(
            Sum("source_cost"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        ),
        total_cutting_cost=Coalesce(
            Sum("additional_cutting_cost"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        ),
        total_conversion_cost=Coalesce(
            Sum("total_conversion_cost"),
            Value(ZERO_MONEY),
            output_field=DecimalField(
                max_digits=20,
                decimal_places=2,
            ),
        ),
    )

    paginator = Paginator(
        conversions,
        25,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    context = {
        "page_title": "Wood Conversions",
        "conversions": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "conversion_count": all_conversions.count(),
        "draft_count": all_conversions.filter(
            status=WoodConversion.Status.DRAFT
        ).count(),
        "posted_count": posted_conversions.count(),
        "total_source_cost": round_money(
            totals["total_source_cost"]
        ),
        "total_cutting_cost": round_money(
            totals["total_cutting_cost"]
        ),
        "total_conversion_cost": round_money(
            totals["total_conversion_cost"]
        ),
    }

    return render(
        request,
        "inventory/conversion_list.html",
        context,
    )


@manager_required
def wood_conversion_create(request):
    conversion = WoodConversion(
        created_by=request.user,
    )

    form = WoodConversionForm(
        request.POST or None,
        instance=conversion,
    )

    formset = ConversionOutputFormSet(
        request.POST or None,
        instance=conversion,
        prefix="outputs",
    )

    if request.method == "POST":
        form_is_valid = form.is_valid()

        if form_is_valid:
            conversion = form.save(
                commit=False
            )

            conversion.created_by = request.user
            conversion.status = (
                WoodConversion.Status.DRAFT
            )

            # Allows the output formset to compare
            # outputs against the selected source.
            formset.instance = conversion

        formset_is_valid = formset.is_valid()

        if form_is_valid and formset_is_valid:
            with transaction.atomic():
                conversion.save()

                formset.instance = conversion
                formset.save()

            if "save_and_post" in request.POST:
                try:
                    post_wood_conversion(
                        conversion_id=conversion.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Wood conversion "
                            f"{conversion.conversion_number} "
                            f"posted successfully."
                        ),
                    )

                    return redirect(
                        "wood-conversion-detail",
                        pk=conversion.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "wood-conversion-edit",
                        pk=conversion.pk,
                    )

            messages.success(
                request,
                (
                    f"Wood conversion "
                    f"{conversion.conversion_number} "
                    f"saved as draft."
                ),
            )

            return redirect(
                "wood-conversion-detail",
                pk=conversion.pk,
            )

    context = {
        "page_title": "New Wood Conversion",
        "form": form,
        "formset": formset,
        "conversion": conversion,
        "is_editing": False,
    }

    return render(
        request,
        "inventory/conversion_form.html",
        context,
    )


@manager_required
def wood_conversion_edit(request, pk):
    conversion = get_object_or_404(
        WoodConversion.objects.prefetch_related(
            "outputs"
        ),
        pk=pk,
    )

    if conversion.status != WoodConversion.Status.DRAFT:
        messages.error(
            request,
            "Only draft wood conversions can be edited.",
        )

        return redirect(
            "wood-conversion-detail",
            pk=conversion.pk,
        )

    form = WoodConversionForm(
        request.POST or None,
        instance=conversion,
    )

    formset = ConversionOutputFormSet(
        request.POST or None,
        instance=conversion,
        prefix="outputs",
    )

    if request.method == "POST":
        form_is_valid = form.is_valid()

        if form_is_valid:
            conversion = form.save(
                commit=False
            )

            formset.instance = conversion

        formset_is_valid = formset.is_valid()

        if form_is_valid and formset_is_valid:
            with transaction.atomic():
                conversion.save()
                formset.save()

            if "save_and_post" in request.POST:
                try:
                    post_wood_conversion(
                        conversion_id=conversion.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Wood conversion "
                            f"{conversion.conversion_number} "
                            f"posted successfully."
                        ),
                    )

                    return redirect(
                        "wood-conversion-detail",
                        pk=conversion.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "wood-conversion-edit",
                        pk=conversion.pk,
                    )

            messages.success(
                request,
                "Draft wood conversion updated.",
            )

            return redirect(
                "wood-conversion-detail",
                pk=conversion.pk,
            )

    context = {
        "page_title": "Edit Wood Conversion",
        "form": form,
        "formset": formset,
        "conversion": conversion,
        "is_editing": True,
    }

    return render(
        request,
        "inventory/conversion_form.html",
        context,
    )


@manager_required
def wood_conversion_detail(request, pk):
    conversion = get_object_or_404(
        WoodConversion.objects
        .select_related(
            "source_product",
            "source_product__category",
            "created_by",
            "posted_by",
        )
        .prefetch_related(
            "outputs",
            "outputs__product",
            "outputs__output_batch",
            "batch_usages",
            "batch_usages__batch",
            "batch_usages__batch__supplier",
        ),
        pk=pk,
    )

    context = {
        "page_title": conversion.conversion_number,
        "conversion": conversion,
    }

    return render(
        request,
        "inventory/conversion_detail.html",
        context,
    )


@manager_required
@require_POST
def wood_conversion_post(request, pk):
    conversion = get_object_or_404(
        WoodConversion,
        pk=pk,
    )

    try:
        post_wood_conversion(
            conversion_id=conversion.id,
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Wood conversion "
                f"{conversion.conversion_number} "
                f"posted successfully."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "wood-conversion-detail",
        pk=conversion.pk,
    )


@manager_required
@require_POST
def wood_conversion_cancel(request, pk):
    conversion = get_object_or_404(
        WoodConversion,
        pk=pk,
    )

    if conversion.status != WoodConversion.Status.DRAFT:
        messages.error(
            request,
            "Only draft wood conversions can be cancelled.",
        )

        return redirect(
            "wood-conversion-detail",
            pk=conversion.pk,
        )

    conversion.status = WoodConversion.Status.CANCELLED

    conversion.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"Wood conversion "
            f"{conversion.conversion_number} "
            f"cancelled."
        ),
    )

    return redirect(
        "wood-conversion-detail",
        pk=conversion.pk,
    )