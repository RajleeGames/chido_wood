from decimal import Decimal

from django import forms

from .models import Category, Product


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

class CategoryForm(StyledModelForm):
    class Meta:
        model = Category

        fields = [
            "name",
            "code",
            "description",
            "allow_cutting",
            "default_cutting_fee",
            "is_active",
        ]

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        self.fields["code"].widget.attrs[
            "placeholder"
        ] = "Example: TIMBER"

        self.fields["default_cutting_fee"].widget.attrs[
            "step"
        ] = "0.01"


class ProductForm(StyledModelForm):
    class Meta:
        model = Product

        fields = [
            "category",
            "code",
            "name",
            "wood_type",
            "dimension_note",
            "measurement_unit",
            "selling_price",
            "wholesale_price",
            "minimum_selling_price",
            "allow_customer_cutting",
            "default_cutting_fee",
            "track_stock",
            "low_stock_level",
            "barcode",
            "notes",
            "is_active",
        ]

        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        self.fields["code"].widget.attrs[
            "placeholder"
        ] = "Example: MBAO-6X2"

        self.fields["name"].widget.attrs[
            "placeholder"
        ] = "Example: Mbao 6×2"

        self.fields["wood_type"].widget.attrs[
            "placeholder"
        ] = "Example: Pine, Mninga or Eucalyptus"

        self.fields["dimension_note"].widget.attrs[
            "placeholder"
        ] = "Example: 6×2 inches × 12 feet"

        self.fields["barcode"].widget.attrs[
            "placeholder"
        ] = "Optional barcode"

        money_fields = [
            "selling_price",
            "wholesale_price",
            "minimum_selling_price",
            "default_cutting_fee",
        ]

        for field_name in money_fields:
            self.fields[field_name].widget.attrs[
                "step"
            ] = "0.01"

        self.fields["low_stock_level"].widget.attrs[
            "step"
        ] = "0.001"

        # Product cutting fee is optional.
        # When empty, the category cutting fee is used.
        self.fields["default_cutting_fee"].required = False

        self.fields["default_cutting_fee"].widget.attrs[
            "placeholder"
        ] = "Leave empty to use category fee"

        self.fields["default_cutting_fee"].help_text = (
            "Leave empty to use the category cutting fee."
        )

    def clean_default_cutting_fee(self):
        cutting_fee = self.cleaned_data.get(
            "default_cutting_fee"
        )

        if cutting_fee in (None, ""):
            return Decimal("0.00")

        if cutting_fee < Decimal("0.00"):
            raise forms.ValidationError(
                "Cutting fee cannot be negative."
            )

        return cutting_fee

    def clean(self):
        cleaned_data = super().clean()

        selling_price = cleaned_data.get(
            "selling_price"
        )

        wholesale_price = cleaned_data.get(
            "wholesale_price"
        )

        minimum_price = cleaned_data.get(
            "minimum_selling_price"
        )

        allow_customer_cutting = cleaned_data.get(
            "allow_customer_cutting"
        )

        if (
            selling_price is not None
            and minimum_price is not None
            and minimum_price > selling_price
        ):
            self.add_error(
                "minimum_selling_price",
                (
                    "Minimum selling price cannot be "
                    "higher than the normal selling price."
                ),
            )

        if (
            selling_price is not None
            and wholesale_price is not None
            and wholesale_price < Decimal("0.00")
        ):
            self.add_error(
                "wholesale_price",
                "Wholesale price cannot be negative.",
            )

        if not allow_customer_cutting:
            cleaned_data["default_cutting_fee"] = Decimal(
                "0.00"
            )

        return cleaned_data