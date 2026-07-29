import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
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
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import manager_required
from customers.models import (
    Customer,
    CustomerPayment,
)
from expenses.models import Expense
from inventory.models import StockBatch
from products.models import Product
from purchases.models import Purchase
from sales.models import (
    CustomerCuttingService,
    Sale,
)


ZERO_MONEY = Decimal("0.00")
ZERO_QUANTITY = Decimal("0.000")
MONEY_PLACES = Decimal("0.01")
PERCENT_PLACES = Decimal("0.1")


def round_money(value):
    return Decimal(
        str(value or 0)
    ).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def round_percent(value):
    return Decimal(
        str(value or 0)
    ).quantize(
        PERCENT_PLACES,
        rounding=ROUND_HALF_UP,
    )


def object_local_date(value):
    if isinstance(value, date) and not hasattr(
        value,
        "hour",
    ):
        return value

    if timezone.is_aware(value):
        return timezone.localtime(
            value
        ).date()

    return value.date()


def parse_report_date(
    raw_value,
    fallback,
):
    try:
        return date.fromisoformat(
            str(raw_value or "")
        )
    except (TypeError, ValueError):
        return fallback


def get_report_dates(request):
    today = timezone.localdate()

    default_start = today.replace(
        day=1
    )

    start_date = parse_report_date(
        request.GET.get("date_from"),
        default_start,
    )

    end_date = parse_report_date(
        request.GET.get("date_to"),
        today,
    )

    dates_swapped = False

    if start_date > end_date:
        start_date, end_date = (
            end_date,
            start_date,
        )

        dates_swapped = True

    return (
        start_date,
        end_date,
        dates_swapped,
    )


def customer_accounts_queryset():
    money_field = DecimalField(
        max_digits=20,
        decimal_places=2,
    )

    sale_balance_expression = (
        ExpressionWrapper(
            F("total_amount")
            - F("amount_paid"),
            output_field=money_field,
        )
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
            F("total_fee")
            - F("amount_paid"),
            output_field=money_field,
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

    return (
        Customer.objects
        .annotate(
            remaining_opening_debt=(
                ExpressionWrapper(
                    F("opening_balance")
                    - F(
                        "opening_balance_paid"
                    ),
                    output_field=money_field,
                )
            ),
            report_sale_debt=Coalesce(
                Subquery(
                    sale_debt_subquery,
                    output_field=money_field,
                ),
                Value(ZERO_MONEY),
                output_field=money_field,
            ),
            report_cutting_debt=Coalesce(
                Subquery(
                    cutting_debt_subquery,
                    output_field=money_field,
                ),
                Value(ZERO_MONEY),
                output_field=money_field,
            ),
        )
        .annotate(
            account_balance=(
                ExpressionWrapper(
                    F(
                        "remaining_opening_debt"
                    )
                    + F("report_sale_debt")
                    + F(
                        "report_cutting_debt"
                    ),
                    output_field=money_field,
                )
            )
        )
    )


def build_business_report(
    *,
    start_date,
    end_date,
):
    completed_sales = list(
        Sale.objects
        .filter(
            status=Sale.Status.COMPLETED,
            sale_date__date__gte=start_date,
            sale_date__date__lte=end_date,
        )
        .select_related(
            "customer",
            "completed_by",
        )
        .prefetch_related(
            "items",
            "items__product",
            "items__product__category",
        )
        .order_by(
            "sale_date",
            "id",
        )
    )

    cutting_services = list(
        CustomerCuttingService.objects
        .filter(
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
            service_date__date__gte=(
                start_date
            ),
            service_date__date__lte=(
                end_date
            ),
        )
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
        )
        .order_by(
            "service_date",
            "id",
        )
    )

    posted_expenses = list(
        Expense.objects
        .filter(
            status=Expense.Status.POSTED,
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        )
        .select_related("category")
        .order_by(
            "expense_date",
            "id",
        )
    )

    posted_purchases = list(
        Purchase.objects
        .filter(
            status=Purchase.Status.POSTED,
            purchase_date__gte=start_date,
            purchase_date__lte=end_date,
        )
        .select_related("supplier")
        .order_by(
            "purchase_date",
            "id",
        )
    )

    account_payments = list(
        CustomerPayment.objects
        .filter(
            status=CustomerPayment.Status.POSTED,
            payment_date__date__gte=start_date,
            payment_date__date__lte=end_date,
        )
        .select_related("customer")
        .order_by(
            "payment_date",
            "id",
        )
    )

    daily_data = defaultdict(
        lambda: {
            "sales_revenue": ZERO_MONEY,
            "cost_of_goods": ZERO_MONEY,
            "cutting_income": ZERO_MONEY,
            "expenses": ZERO_MONEY,
        }
    )

    product_performance = {}

    payment_method_performance = {}

    sales_revenue = ZERO_MONEY
    cost_of_goods = ZERO_MONEY
    sale_discounts = ZERO_MONEY
    initial_sale_payments = ZERO_MONEY
    total_units_sold = ZERO_QUANTITY

    for sale in completed_sales:
        sale_day = object_local_date(
            sale.sale_date
        )

        sales_revenue = round_money(
            sales_revenue
            + sale.total_amount
        )

        sale_discounts = round_money(
            sale_discounts
            + sale.discount
        )

        initial_paid = min(
            sale.amount_tendered,
            sale.total_amount,
        )

        initial_sale_payments = round_money(
            initial_sale_payments
            + initial_paid
        )

        daily_data[sale_day][
            "sales_revenue"
        ] = round_money(
            daily_data[sale_day][
                "sales_revenue"
            ]
            + sale.total_amount
        )

        payment_key = sale.payment_method

        if (
            payment_key
            not in payment_method_performance
        ):
            payment_method_performance[
                payment_key
            ] = {
                "label": (
                    sale.get_payment_method_display()
                ),
                "sale_count": 0,
                "revenue": ZERO_MONEY,
            }

        payment_method_performance[
            payment_key
        ]["sale_count"] += 1

        payment_method_performance[
            payment_key
        ]["revenue"] = round_money(
            payment_method_performance[
                payment_key
            ]["revenue"]
            + sale.total_amount
        )

        sale_items = list(
            sale.items.all()
        )

        sale_subtotal = sum(
            (
                item.line_total
                for item in sale_items
            ),
            ZERO_MONEY,
        )

        remaining_sale_discount = (
            sale.discount
        )

        for index, item in enumerate(
            sale_items
        ):
            item_cost = round_money(
                item.cost_total
            )

            cost_of_goods = round_money(
                cost_of_goods
                + item_cost
            )

            total_units_sold += (
                item.quantity
            )

            daily_data[sale_day][
                "cost_of_goods"
            ] = round_money(
                daily_data[sale_day][
                    "cost_of_goods"
                ]
                + item_cost
            )

            is_last_item = (
                index
                == len(sale_items) - 1
            )

            if is_last_item:
                allocated_discount = (
                    remaining_sale_discount
                )

            elif sale_subtotal > ZERO_MONEY:
                allocated_discount = (
                    round_money(
                        sale.discount
                        * item.line_total
                        / sale_subtotal
                    )
                )

                remaining_sale_discount = (
                    round_money(
                        remaining_sale_discount
                        - allocated_discount
                    )
                )

            else:
                allocated_discount = (
                    ZERO_MONEY
                )

            adjusted_revenue = round_money(
                item.line_total
                - allocated_discount
            )

            adjusted_profit = round_money(
                adjusted_revenue
                - item_cost
            )

            product_key = item.product_id

            if (
                product_key
                not in product_performance
            ):
                product_performance[
                    product_key
                ] = {
                    "product_id": item.product_id,
                    "name": item.product.name,
                    "code": item.product.code,
                    "category": (
                        item.product.category.name
                    ),
                    "quantity": ZERO_QUANTITY,
                    "revenue": ZERO_MONEY,
                    "cost": ZERO_MONEY,
                    "profit": ZERO_MONEY,
                }

            product_row = product_performance[
                product_key
            ]

            product_row["quantity"] += (
                item.quantity
            )

            product_row["revenue"] = (
                round_money(
                    product_row["revenue"]
                    + adjusted_revenue
                )
            )

            product_row["cost"] = (
                round_money(
                    product_row["cost"]
                    + item_cost
                )
            )

            product_row["profit"] = (
                round_money(
                    product_row["profit"]
                    + adjusted_profit
                )
            )

    gross_profit = round_money(
        sales_revenue
        - cost_of_goods
    )

    cutting_income = ZERO_MONEY
    initial_cutting_payments = ZERO_MONEY
    total_machine_cuts = 0

    for service in cutting_services:
        service_day = object_local_date(
            service.service_date
        )

        cutting_income = round_money(
            cutting_income
            + service.total_fee
        )

        initial_paid = min(
            service.amount_tendered,
            service.total_fee,
        )

        initial_cutting_payments = (
            round_money(
                initial_cutting_payments
                + initial_paid
            )
        )

        total_machine_cuts += (
            service.number_of_cuts
        )

        daily_data[service_day][
            "cutting_income"
        ] = round_money(
            daily_data[service_day][
                "cutting_income"
            ]
            + service.total_fee
        )

    expense_total = ZERO_MONEY
    expense_category_performance = {}

    for expense in posted_expenses:
        expense_total = round_money(
            expense_total
            + expense.amount
        )

        daily_data[expense.expense_date][
            "expenses"
        ] = round_money(
            daily_data[
                expense.expense_date
            ]["expenses"]
            + expense.amount
        )

        category_key = expense.category_id

        if (
            category_key
            not in expense_category_performance
        ):
            expense_category_performance[
                category_key
            ] = {
                "name": expense.category.name,
                "count": 0,
                "amount": ZERO_MONEY,
            }

        category_row = (
            expense_category_performance[
                category_key
            ]
        )

        category_row["count"] += 1

        category_row["amount"] = (
            round_money(
                category_row["amount"]
                + expense.amount
            )
        )

    operating_income = round_money(
        gross_profit
        + cutting_income
    )

    net_profit = round_money(
        operating_income
        - expense_total
    )

    purchase_total = ZERO_MONEY
    purchase_paid = ZERO_MONEY

    for purchase in posted_purchases:
        purchase_total = round_money(
            purchase_total
            + purchase.total_amount
        )

        purchase_paid = round_money(
            purchase_paid
            + min(
                purchase.amount_paid,
                purchase.total_amount,
            )
        )

    purchase_payable = round_money(
        purchase_total
        - purchase_paid
    )

    later_customer_payments = sum(
        (
            payment.amount
            for payment in account_payments
        ),
        ZERO_MONEY,
    )

    later_customer_payments = round_money(
        later_customer_payments
    )

    payments_collected = round_money(
        initial_sale_payments
        + initial_cutting_payments
        + later_customer_payments
    )

    inventory_value_expression = (
        ExpressionWrapper(
            F("remaining_quantity")
            * F("unit_cost"),
            output_field=DecimalField(
                max_digits=22,
                decimal_places=4,
            ),
        )
    )

    inventory_totals = (
        StockBatch.objects
        .filter(
            is_active=True,
            remaining_quantity__gt=0,
        )
        .aggregate(
            stock_quantity=Coalesce(
                Sum("remaining_quantity"),
                Value(ZERO_QUANTITY),
                output_field=DecimalField(
                    max_digits=20,
                    decimal_places=3,
                ),
            ),
            stock_value=Coalesce(
                Sum(
                    inventory_value_expression
                ),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=22,
                    decimal_places=4,
                ),
            ),
        )
    )

    stock_quantity = (
        inventory_totals[
            "stock_quantity"
        ]
    )

    stock_value = round_money(
        inventory_totals["stock_value"]
    )

    inventory_products = (
        Product.objects
        .filter(
            is_active=True,
            track_stock=True,
        )
        .annotate(
            current_stock=Coalesce(
                Sum(
                    "stock_batches__remaining_quantity",
                    filter=Q(
                        stock_batches__is_active=True,
                        stock_batches__remaining_quantity__gt=0,
                    ),
                ),
                Value(ZERO_QUANTITY),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=3,
                ),
            )
        )
    )

    out_of_stock_count = (
        inventory_products
        .filter(
            current_stock__lte=ZERO_QUANTITY
        )
        .count()
    )

    low_stock_count = (
        inventory_products
        .filter(
            current_stock__gt=ZERO_QUANTITY,
            current_stock__lte=F(
                "low_stock_level"
            ),
        )
        .count()
    )

    customer_accounts = (
        customer_accounts_queryset()
    )

    customer_debt_total = (
        customer_accounts
        .filter(
            account_balance__gt=ZERO_MONEY
        )
        .aggregate(
            total=Coalesce(
                Sum("account_balance"),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=22,
                    decimal_places=2,
                ),
            )
        )["total"]
    )

    customer_debt_total = round_money(
        customer_debt_total
    )

    debtor_count = (
        customer_accounts
        .filter(
            account_balance__gt=ZERO_MONEY
        )
        .count()
    )

    daily_rows = []

    for report_day in sorted(
        daily_data.keys()
    ):
        day_values = daily_data[
            report_day
        ]

        day_gross_profit = round_money(
            day_values["sales_revenue"]
            - day_values["cost_of_goods"]
        )

        day_net_profit = round_money(
            day_gross_profit
            + day_values[
                "cutting_income"
            ]
            - day_values["expenses"]
        )

        daily_rows.append(
            {
                "date": report_day,
                "sales_revenue": (
                    day_values[
                        "sales_revenue"
                    ]
                ),
                "cost_of_goods": (
                    day_values[
                        "cost_of_goods"
                    ]
                ),
                "gross_profit": (
                    day_gross_profit
                ),
                "cutting_income": (
                    day_values[
                        "cutting_income"
                    ]
                ),
                "expenses": (
                    day_values[
                        "expenses"
                    ]
                ),
                "net_profit": (
                    day_net_profit
                ),
            }
        )

    top_products = sorted(
        product_performance.values(),
        key=lambda row: (
            row["revenue"],
            row["quantity"],
        ),
        reverse=True,
    )[:10]

    maximum_product_revenue = max(
        (
            row["revenue"]
            for row in top_products
        ),
        default=ZERO_MONEY,
    )

    for row in top_products:
        if maximum_product_revenue > 0:
            row["percentage"] = (
                round_percent(
                    row["revenue"]
                    * Decimal("100")
                    / maximum_product_revenue
                )
            )
        else:
            row["percentage"] = (
                Decimal("0.0")
            )

    payment_methods = sorted(
        payment_method_performance.values(),
        key=lambda row: row["revenue"],
        reverse=True,
    )

    for row in payment_methods:
        if sales_revenue > ZERO_MONEY:
            row["percentage"] = (
                round_percent(
                    row["revenue"]
                    * Decimal("100")
                    / sales_revenue
                )
            )
        else:
            row["percentage"] = (
                Decimal("0.0")
            )

    expense_categories = sorted(
        expense_category_performance.values(),
        key=lambda row: row["amount"],
        reverse=True,
    )

    for row in expense_categories:
        if expense_total > ZERO_MONEY:
            row["percentage"] = (
                round_percent(
                    row["amount"]
                    * Decimal("100")
                    / expense_total
                )
            )
        else:
            row["percentage"] = (
                Decimal("0.0")
            )

    income_total = round_money(
        sales_revenue
        + cutting_income
    )

    if income_total > ZERO_MONEY:
        net_profit_margin = round_percent(
            net_profit
            * Decimal("100")
            / income_total
        )
    else:
        net_profit_margin = (
            Decimal("0.0")
        )

    if sales_revenue > ZERO_MONEY:
        gross_profit_margin = (
            round_percent(
                gross_profit
                * Decimal("100")
                / sales_revenue
            )
        )
    else:
        gross_profit_margin = (
            Decimal("0.0")
        )

    if completed_sales:
        average_sale_value = round_money(
            sales_revenue
            / Decimal(
                len(completed_sales)
            )
        )
    else:
        average_sale_value = ZERO_MONEY

    return {
        "start_date": start_date,
        "end_date": end_date,
        "report_days": (
            end_date - start_date
        ).days + 1,

        "sales_count": len(
            completed_sales
        ),
        "sales_revenue": sales_revenue,
        "sale_discounts": sale_discounts,
        "cost_of_goods": cost_of_goods,
        "gross_profit": gross_profit,
        "gross_profit_margin": (
            gross_profit_margin
        ),
        "average_sale_value": (
            average_sale_value
        ),
        "total_units_sold": (
            total_units_sold
        ),

        "cutting_service_count": len(
            cutting_services
        ),
        "cutting_income": cutting_income,
        "total_machine_cuts": (
            total_machine_cuts
        ),

        "operating_income": (
            operating_income
        ),
        "expense_count": len(
            posted_expenses
        ),
        "expense_total": expense_total,
        "net_profit": net_profit,
        "net_profit_margin": (
            net_profit_margin
        ),

        "payments_collected": (
            payments_collected
        ),
        "initial_sale_payments": (
            initial_sale_payments
        ),
        "initial_cutting_payments": (
            initial_cutting_payments
        ),
        "account_payments_total": (
            later_customer_payments
        ),

        "purchase_count": len(
            posted_purchases
        ),
        "purchase_total": (
            purchase_total
        ),
        "purchase_paid": purchase_paid,
        "purchase_payable": (
            purchase_payable
        ),

        "stock_quantity": (
            stock_quantity
        ),
        "stock_value": stock_value,
        "low_stock_count": (
            low_stock_count
        ),
        "out_of_stock_count": (
            out_of_stock_count
        ),

        "customer_debt_total": (
            customer_debt_total
        ),
        "debtor_count": debtor_count,

        "daily_rows": daily_rows,
        "top_products": top_products,
        "payment_methods": (
            payment_methods
        ),
        "expense_categories": (
            expense_categories
        ),
    }


@manager_required
def business_report(request):
    (
        start_date,
        end_date,
        dates_swapped,
    ) = get_report_dates(request)

    if dates_swapped:
        messages.warning(
            request,
            (
                "The report dates were reversed, "
                "so the system corrected their order."
            ),
        )

    report = build_business_report(
        start_date=start_date,
        end_date=end_date,
    )

    context = {
        "page_title": "Business Reports",
        "date_from": (
            start_date.isoformat()
        ),
        "date_to": end_date.isoformat(),
        **report,
    }

    return render(
        request,
        "reports/business_report.html",
        context,
    )


@manager_required
def business_report_csv(request):
    (
        start_date,
        end_date,
        _,
    ) = get_report_dates(request)

    report = build_business_report(
        start_date=start_date,
        end_date=end_date,
    )

    response = HttpResponse(
        content_type=(
            "text/csv; charset=utf-8"
        )
    )

    response[
        "Content-Disposition"
    ] = (
        "attachment; "
        f'filename="business-report-'
        f'{start_date.isoformat()}-'
        f'{end_date.isoformat()}.csv"'
    )

    writer = csv.writer(response)

    writer.writerow(
        [
            "CHIDO Wood ERP Business Report",
        ]
    )

    writer.writerow(
        [
            "Date from",
            start_date.isoformat(),
        ]
    )

    writer.writerow(
        [
            "Date to",
            end_date.isoformat(),
        ]
    )

    writer.writerow([])

    writer.writerow(
        [
            "Profit and Loss",
            "Amount (TZS)",
        ]
    )

    writer.writerow(
        [
            "Sales revenue",
            report["sales_revenue"],
        ]
    )

    writer.writerow(
        [
            "Cost of goods sold",
            report["cost_of_goods"],
        ]
    )

    writer.writerow(
        [
            "Gross profit",
            report["gross_profit"],
        ]
    )

    writer.writerow(
        [
            "Customer cutting income",
            report["cutting_income"],
        ]
    )

    writer.writerow(
        [
            "Operating expenses",
            report["expense_total"],
        ]
    )

    writer.writerow(
        [
            "Net profit",
            report["net_profit"],
        ]
    )

    writer.writerow([])

    writer.writerow(
        [
            "Business Position",
            "Amount (TZS)",
        ]
    )

    writer.writerow(
        [
            "Payments collected",
            report["payments_collected"],
        ]
    )

    writer.writerow(
        [
            "Purchases",
            report["purchase_total"],
        ]
    )

    writer.writerow(
        [
            "Purchase payable",
            report["purchase_payable"],
        ]
    )

    writer.writerow(
        [
            "Current inventory value",
            report["stock_value"],
        ]
    )

    writer.writerow(
        [
            "Current customer debt",
            report["customer_debt_total"],
        ]
    )

    writer.writerow([])

    writer.writerow(
        [
            "Daily Performance",
        ]
    )

    writer.writerow(
        [
            "Date",
            "Sales revenue",
            "COGS",
            "Gross profit",
            "Cutting income",
            "Expenses",
            "Net profit",
        ]
    )

    for row in report["daily_rows"]:
        writer.writerow(
            [
                row["date"].isoformat(),
                row["sales_revenue"],
                row["cost_of_goods"],
                row["gross_profit"],
                row["cutting_income"],
                row["expenses"],
                row["net_profit"],
            ]
        )

    writer.writerow([])

    writer.writerow(
        [
            "Top Products",
        ]
    )

    writer.writerow(
        [
            "Product",
            "Code",
            "Category",
            "Quantity",
            "Revenue",
            "Cost",
            "Profit",
        ]
    )

    for row in report["top_products"]:
        writer.writerow(
            [
                row["name"],
                row["code"],
                row["category"],
                row["quantity"],
                row["revenue"],
                row["cost"],
                row["profit"],
            ]
        )

    return response