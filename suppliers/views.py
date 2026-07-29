from decimal import Decimal

from django.contrib import messages
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accounts.decorators import manager_required

from .forms import SupplierForm
from .models import Supplier


@manager_required
def supplier_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    suppliers = Supplier.objects.all().order_by("name")

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
                (
                    f'Supplier "{supplier.name}" '
                    f"saved successfully."
                ),
            )

            return redirect("supplier-list")

    supplier_summary = Supplier.objects.aggregate(
        total_opening_balance=Coalesce(
            Sum("opening_balance"),
            Decimal("0.00"),
        )
    )

    supplier_count = Supplier.objects.count()

    active_supplier_count = Supplier.objects.filter(
        is_active=True
    ).count()

    inactive_supplier_count = Supplier.objects.filter(
        is_active=False
    ).count()

    context = {
        "page_title": "Suppliers",
        "suppliers": suppliers,
        "form": form,
        "editing_supplier": supplier_instance,
        "modal_open": modal_open,
        "search_query": search_query,
        "supplier_count": supplier_count,
        "active_supplier_count": active_supplier_count,
        "inactive_supplier_count": inactive_supplier_count,
        "total_opening_balance": supplier_summary[
            "total_opening_balance"
        ],
    }

    return render(
        request,
        "suppliers/supplier_list.html",
        context,
    )