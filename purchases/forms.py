from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from products.models import Product
from suppliers.models import Supplier

from .models import Purchase, PurchaseItem


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
            # SAFE NUMBER / MONEY INPUTS
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
                # Prevent browser mouse-wheel number changes
                # by using a text field with numeric keyboard.
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


class PurchaseForm(StyledModelForm):
    class Meta:
        model = Purchase

        fields = [
            "supplier",
            "supplier_invoice_number",
            "purchase_date",
            "payment_method",
            "amount_paid",
            "transport_cost",
            "loading_cost",
            "other_cost",
            "discount",
            "notes",
        ]

        widgets = {
            "purchase_date": forms.DateInput(
                attrs={
                    "type": "date",
                }
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

        self.fields["supplier"].queryset = (
            Supplier.objects
            .filter(is_active=True)
            .order_by("name")
        )

        self.fields["supplier_invoice_number"].widget.attrs[
            "placeholder"
        ] = "Optional supplier invoice number"

        money_fields = [
            "amount_paid",
            "transport_cost",
            "loading_cost",
            "other_cost",
            "discount",
        ]

        for field_name in money_fields:
            self.fields[field_name].required = False

            self.fields[field_name].widget.attrs[
                "step"
            ] = "0.01"

            self.fields[field_name].widget.attrs[
                "min"
            ] = "0"

    def clean(self):
        cleaned_data = super().clean()

        money_fields = [
            "amount_paid",
            "transport_cost",
            "loading_cost",
            "other_cost",
            "discount",
        ]

        for field_name in money_fields:
            if cleaned_data.get(field_name) in (None, ""):
                cleaned_data[field_name] = Decimal("0.00")

        return cleaned_data


class PurchaseItemForm(StyledModelForm):
    class Meta:
        model = PurchaseItem

        fields = [
            "product",
            "quantity",
            "unit_cost",
            "notes",
        ]

        widgets = {
            "notes": forms.TextInput(
                attrs={
                    "placeholder": "Optional item note",
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
            .order_by("name")
        )

        self.fields["quantity"].widget.attrs.update(
            {
                "step": "0.001",
                "min": "0.001",
                "placeholder": "0",
            }
        )

        self.fields["unit_cost"].widget.attrs.update(
            {
                "step": "0.0001",
                "min": "0",
                "placeholder": "0",
            }
        )


class BasePurchaseItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_items = 0

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity")

            if product and quantity:
                active_items += 1

        if active_items == 0:
            raise forms.ValidationError(
                "Add at least one purchase product."
            )


PurchaseItemFormSet = inlineformset_factory(
    Purchase,
    PurchaseItem,
    form=PurchaseItemForm,
    formset=BasePurchaseItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)