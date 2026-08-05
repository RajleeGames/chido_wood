from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from accounts.decorators import management_required
from expenses.models import Expense
from inventory.models import StockBatch
from purchases.models import Purchase
from reports.views import build_business_report
from sales.models import CustomerCuttingService, Sale


ZERO_MONEY = Decimal("0.00")
MONEY_PLACES = Decimal("0.01")


def round_money(value):
    return Decimal(
        str(value or 0)
    ).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def get_dashboard_period(request):
    today = timezone.localdate()

    period = request.GET.get(
        "period",
        "month",
    ).strip().lower()

    period_options = {
        "today": {
            "start_date": today,
            "end_date": today,
            "label": "Today",
        },
        "7d": {
            "start_date": today - timedelta(days=6),
            "end_date": today,
            "label": "Last 7 days",
        },
        "30d": {
            "start_date": today - timedelta(days=29),
            "end_date": today,
            "label": "Last 30 days",
        },
        "month": {
            "start_date": today.replace(day=1),
            "end_date": today,
            "label": "This month",
        },
    }

    if period not in period_options:
        period = "month"

    selected = period_options[period]

    return (
        period,
        selected["start_date"],
        selected["end_date"],
        selected["label"],
    )


def calculate_stock_sales_position():
    stock_cost_expression = ExpressionWrapper(
        F("remaining_quantity")
        * F("unit_cost"),
        output_field=DecimalField(
            max_digits=22,
            decimal_places=4,
        ),
    )

    stock_selling_expression = ExpressionWrapper(
        F("remaining_quantity")
        * F("product__selling_price"),
        output_field=DecimalField(
            max_digits=22,
            decimal_places=4,
        ),
    )

    totals = (
        StockBatch.objects
        .filter(
            is_active=True,
            remaining_quantity__gt=0,
        )
        .aggregate(
            stock_cost_value=Coalesce(
                Sum(stock_cost_expression),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=22,
                    decimal_places=4,
                ),
            ),
            expected_selling_value=Coalesce(
                Sum(stock_selling_expression),
                Value(ZERO_MONEY),
                output_field=DecimalField(
                    max_digits=22,
                    decimal_places=4,
                ),
            ),
        )
    )

    stock_cost_value = round_money(
        totals["stock_cost_value"]
    )

    expected_selling_value = round_money(
        totals["expected_selling_value"]
    )

    expected_stock_profit = round_money(
        expected_selling_value
        - stock_cost_value
    )

    return {
        "stock_cost_value": stock_cost_value,
        "expected_selling_value": expected_selling_value,
        "expected_stock_profit": expected_stock_profit,
    }


def as_activity_datetime(value):
    """
    Convert dates and datetimes into timezone-aware datetimes.

    This value is used only for sorting the mixed activity list.
    """
    if value is None:
        return timezone.now()

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return value

        return timezone.make_aware(value)

    if isinstance(value, date):
        return timezone.make_aware(
            datetime.combine(
                value,
                time.min,
            )
        )

    return timezone.now()


def format_activity_date(value):
    """
    Safely prepare a date for display in the template.

    Datetime values show the date and time.
    Plain date values show the date only.
    """
    if value is None:
        return ""

    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)

        return value.strftime(
            "%d %b %Y, %H:%M"
        )

    if isinstance(value, date):
        return value.strftime(
            "%d %b %Y"
        )

    return str(value)


def safe_reverse(url_name, **kwargs):
    try:
        return reverse(
            url_name,
            kwargs=kwargs,
        )
    except NoReverseMatch:
        return ""


def first_available_value(
    instance,
    field_names,
    default="",
):
    for field_name in field_names:
        value = getattr(
            instance,
            field_name,
            None,
        )

        if value not in (
            None,
            "",
        ):
            return value

    return default


def build_recent_activities(limit=10):
    activities = []

    # -----------------------------------------------------
    # Recent completed sales
    # -----------------------------------------------------
    recent_sales = (
        Sale.objects
        .filter(
            status=Sale.Status.COMPLETED,
        )
        .select_related(
            "customer",
            "completed_by",
        )
        .order_by(
            "-sale_date",
            "-id",
        )[:5]
    )

    for sale in recent_sales:
        customer_name = (
            str(sale.customer)
            if sale.customer_id
            else "Walk-in customer"
        )

        reference = first_available_value(
            sale,
            [
                "sale_number",
                "invoice_number",
                "reference_number",
            ],
            default=f"Sale #{sale.pk}",
        )

        activities.append(
            {
                "kind": "Sale",
                "reference": reference,
                "description": customer_name,
                "amount": round_money(
                    sale.total_amount
                ),
                "occurred_at": sale.sale_date,
                "occurred_at_display": (
                    format_activity_date(
                        sale.sale_date
                    )
                ),
                "sort_at": as_activity_datetime(
                    sale.sale_date
                ),
                "tone": "income",
                "url": safe_reverse(
                    "sale-detail",
                    pk=sale.pk,
                ),
            }
        )

    # -----------------------------------------------------
    # Recent completed customer cutting services
    # -----------------------------------------------------
    recent_cutting_services = (
        CustomerCuttingService.objects
        .filter(
            status=(
                CustomerCuttingService
                .Status
                .COMPLETED
            ),
        )
        .select_related(
            "sale",
            "sale__customer",
            "sale_item",
            "sale_item__product",
        )
        .order_by(
            "-service_date",
            "-id",
        )[:4]
    )

    for service in recent_cutting_services:
        customer = getattr(
            service.sale,
            "customer",
            None,
        )

        customer_name = (
            str(customer)
            if customer
            else "Walk-in customer"
        )

        product = getattr(
            service.sale_item,
            "product",
            None,
        )

        description = customer_name

        if product:
            description = (
                f"{customer_name} · "
                f"{product.name}"
            )

        reference = first_available_value(
            service,
            [
                "service_number",
                "cutting_number",
                "reference_number",
            ],
            default=f"Cutting #{service.pk}",
        )

        activities.append(
            {
                "kind": "Cutting",
                "reference": reference,
                "description": description,
                "amount": round_money(
                    service.total_fee
                ),
                "occurred_at": (
                    service.service_date
                ),
                "occurred_at_display": (
                    format_activity_date(
                        service.service_date
                    )
                ),
                "sort_at": as_activity_datetime(
                    service.service_date
                ),
                "tone": "cutting",
                "url": safe_reverse(
                    "cutting-service-detail",
                    pk=service.pk,
                ),
            }
        )

    # -----------------------------------------------------
    # Recent posted expenses
    # -----------------------------------------------------
    recent_expenses = (
        Expense.objects
        .filter(
            status=Expense.Status.POSTED,
        )
        .select_related(
            "category",
        )
        .order_by(
            "-expense_date",
            "-id",
        )[:4]
    )

    for expense in recent_expenses:
        reference = first_available_value(
            expense,
            [
                "expense_number",
                "reference_number",
            ],
            default=f"Expense #{expense.pk}",
        )

        activities.append(
            {
                "kind": "Expense",
                "reference": reference,
                "description": (
                    expense.category.name
                ),
                "amount": round_money(
                    expense.amount
                ),
                "occurred_at": (
                    expense.expense_date
                ),
                "occurred_at_display": (
                    format_activity_date(
                        expense.expense_date
                    )
                ),
                "sort_at": as_activity_datetime(
                    expense.expense_date
                ),
                "tone": "expense",
                "url": safe_reverse(
                    "expense-detail",
                    pk=expense.pk,
                ),
            }
        )

    # -----------------------------------------------------
    # Recent posted purchases
    # -----------------------------------------------------
    recent_purchases = (
        Purchase.objects
        .filter(
            status=Purchase.Status.POSTED,
        )
        .select_related(
            "supplier",
        )
        .order_by(
            "-purchase_date",
            "-id",
        )[:4]
    )

    for purchase in recent_purchases:
        reference = first_available_value(
            purchase,
            [
                "purchase_number",
                "reference_number",
                "invoice_number",
            ],
            default=f"Purchase #{purchase.pk}",
        )

        supplier = getattr(
            purchase,
            "supplier",
            None,
        )

        activities.append(
            {
                "kind": "Purchase",
                "reference": reference,
                "description": (
                    str(supplier)
                    if supplier
                    else "Stock purchase"
                ),
                "amount": round_money(
                    purchase.total_amount
                ),
                "occurred_at": (
                    purchase.purchase_date
                ),
                "occurred_at_display": (
                    format_activity_date(
                        purchase.purchase_date
                    )
                ),
                "sort_at": as_activity_datetime(
                    purchase.purchase_date
                ),
                "tone": "purchase",
                "url": safe_reverse(
                    "purchase-detail",
                    pk=purchase.pk,
                ),
            }
        )

    activities.sort(
        key=lambda activity: activity[
            "sort_at"
        ],
        reverse=True,
    )

    return activities[:limit]


def build_chart_data(
    report,
    start_date,
    end_date,
):
    daily_by_date = {
        row["date"]: row
        for row in report["daily_rows"]
    }

    labels = []
    sales = []
    gross_profit = []
    expenses = []
    net_profit = []

    current_day = start_date

    while current_day <= end_date:
        row = daily_by_date.get(
            current_day,
            {},
        )

        labels.append(
            current_day.strftime(
                "%d %b"
            )
        )

        sales.append(
            float(
                row.get(
                    "sales_revenue",
                    ZERO_MONEY,
                )
            )
        )

        gross_profit.append(
            float(
                row.get(
                    "gross_profit",
                    ZERO_MONEY,
                )
            )
        )

        expenses.append(
            float(
                row.get(
                    "expenses",
                    ZERO_MONEY,
                )
            )
        )

        net_profit.append(
            float(
                row.get(
                    "net_profit",
                    ZERO_MONEY,
                )
            )
        )

        current_day += timedelta(
            days=1
        )

    top_products = report[
        "top_products"
    ][:6]

    return {
        "trend": {
            "labels": labels,
            "sales": sales,
            "gross_profit": gross_profit,
            "expenses": expenses,
            "net_profit": net_profit,
        },
        "income_mix": {
            "sales": float(
                report["sales_revenue"]
            ),
            "cutting": float(
                report["cutting_income"]
            ),
        },
        "top_products": {
            "labels": [
                row["name"]
                for row in top_products
            ],
            "revenue": [
                float(row["revenue"])
                for row in top_products
            ],
            "profit": [
                float(row["profit"])
                for row in top_products
            ],
        },
    }

@management_required
def dashboard(request):
    today = timezone.localdate()

    # =====================================================
    # CUSTOM DATE RANGE
    # =====================================================

    date_from_value = (
        request.GET.get("date_from")
        or ""
    ).strip()

    date_to_value = (
        request.GET.get("date_to")
        or ""
    ).strip()

    custom_start_date = None
    custom_end_date = None

    try:
        if date_from_value:
            custom_start_date = datetime.strptime(
                date_from_value,
                "%Y-%m-%d",
            ).date()
    except ValueError:
        custom_start_date = None

    try:
        if date_to_value:
            custom_end_date = datetime.strptime(
                date_to_value,
                "%Y-%m-%d",
            ).date()
    except ValueError:
        custom_end_date = None

    # Use custom dates when either date field is supplied.
    if custom_start_date or custom_end_date:
        start_date = (
            custom_start_date
            or custom_end_date
            or today
        )

        end_date = (
            custom_end_date
            or custom_start_date
            or today
        )

        # Prevent an invalid reversed date range.
        if start_date > end_date:
            start_date, end_date = (
                end_date,
                start_date,
            )

        selected_period = "custom"
        period_label = "Custom date range"

    else:
        # =================================================
        # QUICK PERIOD FILTERS
        # =================================================

        selected_period = (
            request.GET.get("period")
            or "today"
        ).strip().lower()

        period_options = {
            "today": {
                "start_date": today,
                "end_date": today,
                "label": "Today",
            },
            "7d": {
                "start_date": (
                    today - timedelta(days=6)
                ),
                "end_date": today,
                "label": "Last 7 days",
            },
            "30d": {
                "start_date": (
                    today - timedelta(days=29)
                ),
                "end_date": today,
                "label": "Last 30 days",
            },
            "month": {
                "start_date": today.replace(
                    day=1,
                ),
                "end_date": today,
                "label": "This month",
            },
        }

        # Default to today's sales when the value is unknown.
        if selected_period not in period_options:
            selected_period = "today"

        selected_option = period_options[
            selected_period
        ]

        start_date = selected_option[
            "start_date"
        ]

        end_date = selected_option[
            "end_date"
        ]

        period_label = selected_option[
            "label"
        ]

    # =====================================================
    # USER ACCESS
    # =====================================================

    can_view_financials = (
        request.user.is_superuser
        or request.user.role
        in {
            request.user.Role.ADMIN,
            request.user.Role.MANAGER,
        }
    )

    # =====================================================
    # BUSINESS REPORT
    # =====================================================

    report = build_business_report(
        start_date=start_date,
        end_date=end_date,
    )

    stock_position = (
        calculate_stock_sales_position()
    )

    report.update(
        stock_position
    )

    report["income_total"] = round_money(
        report["sales_revenue"]
        + report["cutting_income"]
    )

    report["net_result_label"] = (
        "Net loss"
        if report["net_profit"] < ZERO_MONEY
        else "Net profit"
    )

    report["net_result_amount"] = abs(
        report["net_profit"]
    )

    # =====================================================
    # CHART DATA
    # =====================================================

    chart_data = build_chart_data(
        report,
        start_date,
        end_date,
    )

    # =====================================================
    # TEMPLATE CONTEXT
    # =====================================================

    context = {
        "page_title": "Dashboard",
        "today": today,

        "selected_period": selected_period,
        "period_label": period_label,

        "date_from": start_date,
        "date_to": end_date,

        # Values used directly inside date input fields.
        "date_from_value": (
            start_date.strftime("%Y-%m-%d")
        ),
        "date_to_value": (
            end_date.strftime("%Y-%m-%d")
        ),

        "can_view_financials": (
            can_view_financials
        ),

        "report": report,
        "chart_data": chart_data,

        "recent_activities": (
            build_recent_activities(
                limit=10,
            )
        ),
    }

    return render(
        request,
        "core/dashboard.html",
        context,
    )