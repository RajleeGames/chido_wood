from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from accounts.decorators import manager_required

from .forms import PurchaseForm, PurchaseItemFormSet
from .models import Purchase
from .services import post_purchase


@manager_required
def purchase_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    purchases = (
        Purchase.objects
        .select_related(
            "supplier",
            "created_by",
            "posted_by",
        )
        .prefetch_related(
            "items",
            "items__product",
        )
    )

    if search_query:
        purchases = purchases.filter(
            Q(purchase_number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(
                supplier_invoice_number__icontains=search_query
            )
        )

    if status_filter in {
        Purchase.Status.DRAFT,
        Purchase.Status.POSTED,
        Purchase.Status.CANCELLED,
    }:
        purchases = purchases.filter(
            status=status_filter
        )

    all_purchases = (
        Purchase.objects
        .prefetch_related("items")
    )

    posted_purchases = all_purchases.filter(
        status=Purchase.Status.POSTED
    )

    total_posted_amount = sum(
        (
            purchase.total_amount
            for purchase in posted_purchases
        ),
        Decimal("0.00"),
    )

    total_supplier_balance = sum(
        (
            purchase.balance_due
            for purchase in posted_purchases
        ),
        Decimal("0.00"),
    )

    context = {
        "page_title": "Purchases",
        "purchases": purchases,
        "search_query": search_query,
        "status_filter": status_filter,
        "purchase_count": all_purchases.count(),
        "draft_count": all_purchases.filter(
            status=Purchase.Status.DRAFT
        ).count(),
        "posted_count": posted_purchases.count(),
        "total_posted_amount": total_posted_amount,
        "total_supplier_balance": total_supplier_balance,
    }

    return render(
        request,
        "purchases/purchase_list.html",
        context,
    )


@manager_required
def purchase_create(request):
    purchase = Purchase(
        created_by=request.user,
    )

    form = PurchaseForm(
        request.POST or None,
        instance=purchase,
    )

    formset = PurchaseItemFormSet(
        request.POST or None,
        instance=purchase,
        prefix="items",
    )

    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase = form.save(
                    commit=False
                )

                purchase.created_by = request.user
                purchase.status = Purchase.Status.DRAFT
                purchase.save()

                formset.instance = purchase
                formset.save()

            if "save_and_post" in request.POST:
                try:
                    post_purchase(
                        purchase_id=purchase.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Purchase "
                            f"{purchase.purchase_number} "
                            f"posted successfully."
                        ),
                    )

                    return redirect(
                        "purchase-detail",
                        pk=purchase.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "purchase-edit",
                        pk=purchase.pk,
                    )

            messages.success(
                request,
                (
                    f"Purchase "
                    f"{purchase.purchase_number} "
                    f"saved as draft."
                ),
            )

            return redirect(
                "purchase-detail",
                pk=purchase.pk,
            )

    context = {
        "page_title": "New Purchase",
        "form": form,
        "formset": formset,
        "purchase": purchase,
        "is_editing": False,
    }

    return render(
        request,
        "purchases/purchase_form.html",
        context,
    )


@manager_required
def purchase_edit(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.prefetch_related(
            "items"
        ),
        pk=pk,
    )

    if purchase.status != Purchase.Status.DRAFT:
        messages.error(
            request,
            "Only draft purchases can be edited.",
        )

        return redirect(
            "purchase-detail",
            pk=purchase.pk,
        )

    form = PurchaseForm(
        request.POST or None,
        instance=purchase,
    )

    formset = PurchaseItemFormSet(
        request.POST or None,
        instance=purchase,
        prefix="items",
    )

    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase = form.save()
                formset.save()

            if "save_and_post" in request.POST:
                try:
                    post_purchase(
                        purchase_id=purchase.id,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f"Purchase "
                            f"{purchase.purchase_number} "
                            f"posted successfully."
                        ),
                    )

                    return redirect(
                        "purchase-detail",
                        pk=purchase.pk,
                    )

                except ValidationError as error:
                    messages.error(
                        request,
                        error.messages[0],
                    )

                    return redirect(
                        "purchase-edit",
                        pk=purchase.pk,
                    )

            messages.success(
                request,
                "Draft purchase updated successfully.",
            )

            return redirect(
                "purchase-detail",
                pk=purchase.pk,
            )

    context = {
        "page_title": "Edit Purchase",
        "form": form,
        "formset": formset,
        "purchase": purchase,
        "is_editing": True,
    }

    return render(
        request,
        "purchases/purchase_form.html",
        context,
    )


@manager_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects
        .select_related(
            "supplier",
            "created_by",
            "posted_by",
        )
        .prefetch_related(
            "items",
            "items__product",
            "items__stock_batch",
        ),
        pk=pk,
    )

    context = {
        "page_title": purchase.purchase_number,
        "purchase": purchase,
    }

    return render(
        request,
        "purchases/purchase_detail.html",
        context,
    )


@require_POST
@manager_required
def purchase_post(request, pk):
    purchase = get_object_or_404(
        Purchase,
        pk=pk,
    )

    try:
        post_purchase(
            purchase_id=purchase.id,
            user=request.user,
        )

        messages.success(
            request,
            (
                f"Purchase "
                f"{purchase.purchase_number} "
                f"posted into stock."
            ),
        )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

    return redirect(
        "purchase-detail",
        pk=purchase.pk,
    )