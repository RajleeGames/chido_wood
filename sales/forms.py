from decimal import Decimal
from django.db.models import Sum
from django import forms
from django.forms import (
    BaseInlineFormSet,
    inlineformset_factory,
)

from customers.models import Customer
from products.models import Product

from .models import (
    CustomerCuttingService,
    Sale,
    SaleItem,
)


class StyledModelForm(forms.ModelForm):
    def apply_styles(self):
        for field in self.fields.values():
            widget = field.widget

            if isinstance(
                widget,
                forms.CheckboxInput,
            ):
                widget.attrs["class"] = (
                    "form-check-input"
                )
                continue

            existing_class = widget.attrs.get(
                "class",
                "",
            )

            widget.attrs["class"] = (
                f"{existing_class} form-control"
            ).strip()

            # ------------------------------------------
            # SAFE NUMBER INPUTS
            # ------------------------------------------
            if (
                isinstance(
                    widget,
                    forms.NumberInput,
                )
                and isinstance(
                    field,
                    (
                        forms.DecimalField,
                        forms.IntegerField,
                    ),
                )
            ):
                # Change HTML number input to text.
                # This removes browser +/- controls
                # and prevents mouse-wheel changing values.
                widget.input_type = "text"

                if isinstance(
                    field,
                    forms.DecimalField,
                ):
                    widget.attrs[
                        "inputmode"
                    ] = "decimal"

                    widget.attrs[
                        "data-decimal-places"
                    ] = str(
                        field.decimal_places or 0
                    )

                else:
                    widget.attrs[
                        "inputmode"
                    ] = "numeric"

                    widget.attrs[
                        "data-decimal-places"
                    ] = "0"

                widget.attrs[
                    "data-smart-number"
                ] = "1"

                widget.attrs[
                    "autocomplete"
                ] = "off"

class SaleForm(StyledModelForm):
    class Meta:
        model = Sale

        fields = [
            "customer",
            "sale_date",
            "payment_method",
            "amount_tendered",
            "discount",
            "notes",
        ]

        widgets = {
            "sale_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        self.fields["sale_date"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        self.fields["customer"].required = False

        self.fields["customer"].queryset = (
            Customer.objects
            .filter(is_active=True)
            .order_by("name")
        )

        self.fields["customer"].empty_label = (
            "Walk-in customer"
        )

        self.fields["amount_tendered"].required = False

        self.fields["amount_tendered"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["discount"].required = False

        self.fields["discount"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = "Optional sale notes"

    def clean_amount_tendered(self):
        amount = self.cleaned_data.get(
            "amount_tendered"
        )

        if amount in (None, ""):
            return Decimal("0.00")

        if amount < Decimal("0.00"):
            raise forms.ValidationError(
                "Amount received cannot be negative."
            )

        return amount

    def clean_discount(self):
        discount = self.cleaned_data.get(
            "discount"
        )

        if discount in (None, ""):
            return Decimal("0.00")

        if discount < Decimal("0.00"):
            raise forms.ValidationError(
                "Sale discount cannot be negative."
            )

        return discount


class SaleItemForm(StyledModelForm):
    class Meta:
        model = SaleItem

        fields = [
            "product",
            "quantity",
            "unit_price",
            "line_discount",
            "notes",
        ]

        widgets = {
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "Optional note",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        self.fields["product"].queryset = (
            Product.objects
            .filter(
                is_active=True,
                track_stock=True,
            )
            .select_related("category")
            .order_by(
                "category__name",
                "name",
            )
        )

        self.fields["quantity"].widget.attrs.update(
            {
                "step": "0.001",
                "min": "0.001",
                "placeholder": "0",
            }
        )

        self.fields["unit_price"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["line_discount"].required = False

        self.fields["line_discount"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

    def clean_line_discount(self):
        discount = self.cleaned_data.get(
            "line_discount"
        )

        if discount in (None, ""):
            return Decimal("0.00")

        return discount


class BaseSaleItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_items = 0
        selected_products = set()

        for form in self.forms:
            if not hasattr(
                form,
                "cleaned_data",
            ):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            product = form.cleaned_data.get(
                "product"
            )

            quantity = form.cleaned_data.get(
                "quantity"
            )

            if product is None and quantity is None:
                continue

            if product is None:
                form.add_error(
                    "product",
                    "Select a product.",
                )

                continue

            if quantity is None:
                form.add_error(
                    "quantity",
                    "Enter the quantity.",
                )

                continue

            active_items += 1

            if product.id in selected_products:
                form.add_error(
                    "product",
                    (
                        "This product is already in "
                        "the sale."
                    ),
                )

            selected_products.add(
                product.id
            )

        if active_items == 0:
            raise forms.ValidationError(
                "Add at least one product to the sale."
            )


SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    formset=BaseSaleItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
class CustomerCuttingServiceForm(
    StyledModelForm
):
    class Meta:
        model = CustomerCuttingService

        fields = [
            "sale_item",
            "quantity_cut",
            "number_of_cuts",
            "fee_per_cut",
            "service_date",
            "payment_method",
            "amount_tendered",
            "notes",
        ]

        widgets = {
            "service_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

    def __init__(
        self,
        *args,
        sale=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        self.sale = (
            sale
            or getattr(
                self.instance,
                "sale",
                None,
            )
        )

        self.fields[
            "service_date"
        ].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        # Only active products with
        # "Allow Customer Cutting" enabled
        # can be selected.
        sale_items = SaleItem.objects.none()

        if self.sale and self.sale.pk:
            sale_items = (
                SaleItem.objects
                .filter(
                    sale=self.sale,
                    product__allow_customer_cutting=True,
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

        self.fields[
            "sale_item"
        ].queryset = sale_items

        self.fields[
            "sale_item"
        ].label_from_instance = (
            lambda item: (
                f"{item.product.name} "
                f"— sold {item.quantity}"
            )
        )

        self.fields[
            "quantity_cut"
        ].widget.attrs.update(
            {
                "step": "0.001",
                "min": "0.001",
                "placeholder": "0",
            }
        )

        self.fields[
            "number_of_cuts"
        ].widget.attrs.update(
            {
                "min": "1",
                "step": "1",
                "placeholder": "0",
            }
        )

        self.fields[
            "fee_per_cut"
        ].required = False

        self.fields[
            "fee_per_cut"
        ].widget.attrs.update(
            {
                "min": "0",
                "step": "0.01",
                "placeholder": "0",
            }
        )

        self.fields[
            "amount_tendered"
        ].required = False

        self.fields[
            "amount_tendered"
        ].widget.attrs.update(
            {
                "min": "0",
                "step": "0.01",
                "placeholder": "0",
            }
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = (
            "Optional cutting measurements "
            "or instructions"
        )

    def clean_fee_per_cut(self):
        fee = self.cleaned_data.get(
            "fee_per_cut"
        )

        if fee in (None, ""):
            return Decimal("0.00")

        if fee < Decimal("0.00"):
            raise forms.ValidationError(
                "Cutting fee cannot be negative."
            )

        return fee

    def clean_amount_tendered(self):
        amount = self.cleaned_data.get(
            "amount_tendered"
        )

        if amount in (None, ""):
            return Decimal("0.00")

        if amount < Decimal("0.00"):
            raise forms.ValidationError(
                "Amount received cannot be negative."
            )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        sale_item = cleaned_data.get(
            "sale_item"
        )

        quantity_cut = cleaned_data.get(
            "quantity_cut"
        )

        number_of_cuts = cleaned_data.get(
            "number_of_cuts"
        )

        if not sale_item:
            return cleaned_data

        if (
            not self.sale
            or sale_item.sale_id != self.sale.id
        ):
            self.add_error(
                "sale_item",
                (
                    "The selected product does not "
                    "belong to this sale."
                ),
            )

            return cleaned_data

        # The product's Allow Customer Cutting
        # setting is the source of truth.
        allows_cutting = getattr(
            sale_item.product,
            "allow_customer_cutting",
            False,
        )

        if not allows_cutting:
            self.add_error(
                "sale_item",
                (
                    f"{sale_item.product.name} does "
                    "not allow customer cutting."
                ),
            )

        # Product must still be active.
        if not sale_item.product.is_active:
            self.add_error(
                "sale_item",
                (
                    f"{sale_item.product.name} is "
                    "currently inactive."
                ),
            )

        if (
            quantity_cut is not None
            and quantity_cut > sale_item.quantity
        ):
            self.add_error(
                "quantity_cut",
                (
                    f"Only {sale_item.quantity} pieces "
                    f"were sold on this sale line."
                ),
            )

        if number_of_cuts is not None:
            if number_of_cuts <= 0:
                self.add_error(
                    "number_of_cuts",
                    (
                        "Number of cuts must be "
                        "greater than zero."
                    ),
                )

        if (
            quantity_cut is not None
            and quantity_cut > 0
        ):
            existing_quantity = (
                CustomerCuttingService.objects
                .filter(
                    sale_item=sale_item,
                    status=(
                        CustomerCuttingService
                        .Status
                        .COMPLETED
                    ),
                )
                .exclude(
                    pk=self.instance.pk
                )
                .aggregate(
                    total=Sum(
                        "quantity_cut"
                    )
                )["total"]
                or Decimal("0.000")
            )

            projected_quantity = (
                existing_quantity
                + quantity_cut
            )

            if (
                projected_quantity
                > sale_item.quantity
            ):
                remaining_quantity = (
                    sale_item.quantity
                    - existing_quantity
                )

                self.add_error(
                    "quantity_cut",
                    (
                        f"Only {remaining_quantity} "
                        f"uncut sold pieces remain "
                        f"on this sale line."
                    ),
                )

        return cleaned_data