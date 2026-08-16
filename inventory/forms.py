from decimal import Decimal

from django import forms
from django.forms import (
    BaseInlineFormSet,
    inlineformset_factory,
)

from products.models import Product

from .models import (
    ConversionOutput,
    StockAdjustment,
    WoodConversion,
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


class StockAdjustmentForm(StyledModelForm):
    class Meta:
        model = StockAdjustment

        fields = [
            "product",
            "adjustment_type",
            "adjustment_date",
            "quantity",
            "unit_cost",
            "reason",
            "notes",
        ]

        widgets = {
            "adjustment_date": forms.DateInput(
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

        self.fields["unit_cost"].required = False

        self.fields["unit_cost"].widget.attrs.update(
            {
                "step": "0.0001",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["reason"].widget.attrs[
            "placeholder"
        ] = "Explain why the stock is being adjusted"

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = "Optional additional information"

    def clean(self):
        cleaned_data = super().clean()

        adjustment_type = cleaned_data.get(
            "adjustment_type"
        )

        unit_cost = cleaned_data.get(
            "unit_cost"
        )

        positive_types = {
            StockAdjustment.AdjustmentType.OPENING,
            StockAdjustment.AdjustmentType.INCREASE,
        }

        if adjustment_type in positive_types:
            if (
                unit_cost is None
                or unit_cost <= Decimal("0.0000")
            ):
                self.add_error(
                    "unit_cost",
                    (
                        "Enter a unit cost greater than zero "
                        "for stock being added."
                    ),
                )
        else:
            cleaned_data["unit_cost"] = Decimal(
                "0.0000"
            )

        return cleaned_data


class WoodConversionForm(StyledModelForm):
    class Meta:
        model = WoodConversion

        fields = [
            "source_product",
            "source_quantity",
            "additional_cutting_cost",
            "conversion_date",
            "notes",
        ]

        widgets = {
            "conversion_date": forms.DateInput(
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

        # Only Timber products may be converted.
        self.fields["source_product"].queryset = (
            Product.objects
            .filter(
                is_active=True,
                track_stock=True,
                category__code="TIMBER",
            )
            .select_related("category")
            .order_by("name")
        )

        self.fields["source_quantity"].widget.attrs.update(
            {
                "step": "0.001",
                "min": "0.001",
                "placeholder": "0",
            }
        )

        self.fields[
            "additional_cutting_cost"
        ].required = False

        self.fields[
            "additional_cutting_cost"
        ].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = (
            "Optional notes about the cutting "
            "or conversion process"
        )

    def clean_additional_cutting_cost(self):
        cutting_cost = self.cleaned_data.get(
            "additional_cutting_cost"
        )

        if cutting_cost in (None, ""):
            return Decimal("0.00")

        if cutting_cost < Decimal("0.00"):
            raise forms.ValidationError(
                "Additional cutting cost cannot be negative."
            )

        return cutting_cost

    def clean_source_product(self):
        product = self.cleaned_data.get(
            "source_product"
        )

        if (
            product
            and product.category.code != "TIMBER"
        ):
            raise forms.ValidationError(
                "Only Timber products can be converted."
            )

        return product


class ConversionOutputForm(StyledModelForm):
    class Meta:
        model = ConversionOutput

        fields = [
            "product",
            "quantity",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_styles()

        # Conversion outputs must also be Timber products.
        self.fields["product"].queryset = (
            Product.objects
            .filter(
                is_active=True,
                track_stock=True,
                category__code="TIMBER",
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


class BaseConversionOutputFormSet(
    BaseInlineFormSet
):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_outputs = 0
        selected_products = set()

        source_product_id = (
            self.instance.source_product_id
        )

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
                    "Select an output product.",
                )

                continue

            if quantity is None:
                form.add_error(
                    "quantity",
                    "Enter the output quantity.",
                )

                continue

            active_outputs += 1

            if product.category.code != "TIMBER":
                form.add_error(
                    "product",
                    (
                        "Only Timber products can be "
                        "conversion outputs."
                    ),
                )

            if (
                source_product_id
                and product.id == source_product_id
            ):
                form.add_error(
                    "product",
                    (
                        "The output product cannot be "
                        "the same as the source product."
                    ),
                )

            if product.id in selected_products:
                form.add_error(
                    "product",
                    (
                        "This output product has already "
                        "been added."
                    ),
                )

            selected_products.add(product.id)

        if active_outputs == 0:
            raise forms.ValidationError(
                "Add at least one output Timber product."
            )


ConversionOutputFormSet = inlineformset_factory(
    WoodConversion,
    ConversionOutput,
    form=ConversionOutputForm,
    formset=BaseConversionOutputFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)