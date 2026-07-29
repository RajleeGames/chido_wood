from decimal import Decimal

from django.contrib import messages
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

from accounts.decorators import manager_required

from .forms import CategoryForm, ProductForm
from .models import Category, Product


@manager_required
def category_list(request):
    categories = Category.objects.all()

    category_id = (
        request.GET.get("edit")
        or request.POST.get("object_id")
    )

    category_instance = None

    if category_id:
        category_instance = get_object_or_404(
            Category,
            pk=category_id,
        )

    form = CategoryForm(
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
                    f'Category "{category.name}" '
                    f"saved successfully."
                ),
            )

            return redirect("category-list")

    context = {
        "page_title": "Product Categories",
        "categories": categories,
        "form": form,
        "editing_category": category_instance,
        "modal_open": modal_open,
    }

    return render(
        request,
        "products/category_list.html",
        context,
    )


@manager_required
def product_list(request):
    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    products = (
        Product.objects
        .select_related("category")
        .annotate(
            current_stock=Coalesce(
                Sum(
                    "stock_batches__remaining_quantity",
                    filter=Q(
                        stock_batches__is_active=True
                    ),
                ),
                Value(Decimal("0.000")),
                output_field=DecimalField(
                    max_digits=14,
                    decimal_places=3,
                ),
            )
        )
    )

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(barcode__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    product_id = (
        request.GET.get("edit")
        or request.POST.get("object_id")
    )

    product_instance = None

    if product_id:
        product_instance = get_object_or_404(
            Product,
            pk=product_id,
        )

    form = ProductForm(
        request.POST or None,
        instance=product_instance,
    )

    modal_open = bool(product_instance)

    if request.method == "POST":
        modal_open = True

        if form.is_valid():
            product = form.save()

            messages.success(
                request,
                (
                    f'Product "{product.name}" '
                    f"saved successfully."
                ),
            )

            return redirect("product-list")

    context = {
        "page_title": "Products",
        "products": products,
        "form": form,
        "editing_product": product_instance,
        "modal_open": modal_open,
        "search_query": search_query,
    }

    return render(
        request,
        "products/product_list.html",
        context,
    )