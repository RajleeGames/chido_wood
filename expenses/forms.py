from decimal import Decimal

from django import forms
from django.db.models import Q

from .models import (
    Expense,
    ExpenseCategory,
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


class ExpenseCategoryForm(StyledModelForm):
    class Meta:
        model = ExpenseCategory

        fields = [
            "name",
            "code",
            "description",
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

        self.fields["name"].widget.attrs.update(
            {
                "placeholder": (
                    "Example: Electricity"
                ),
            }
        )

        self.fields["code"].widget.attrs.update(
            {
                "placeholder": (
                    "Example: ELECTRICITY"
                ),
            }
        )

        self.fields["description"].widget.attrs[
            "placeholder"
        ] = "Optional category description"

    def clean_name(self):
        name = self.cleaned_data.get(
            "name",
            "",
        ).strip()

        if len(name) < 2:
            raise forms.ValidationError(
                "Enter a valid category name."
            )

        duplicate = (
            ExpenseCategory.objects
            .filter(name__iexact=name)
        )

        if self.instance.pk:
            duplicate = duplicate.exclude(
                pk=self.instance.pk
            )

        if duplicate.exists():
            raise forms.ValidationError(
                (
                    "An expense category with this "
                    "name already exists."
                )
            )

        return name

    def clean_code(self):
        code = (
            self.cleaned_data.get(
                "code",
                "",
            )
            .strip()
            .upper()
            .replace(" ", "_")
        )

        if len(code) < 2:
            raise forms.ValidationError(
                "Enter a valid category code."
            )

        duplicate = (
            ExpenseCategory.objects
            .filter(code__iexact=code)
        )

        if self.instance.pk:
            duplicate = duplicate.exclude(
                pk=self.instance.pk
            )

        if duplicate.exists():
            raise forms.ValidationError(
                (
                    "An expense category with this "
                    "code already exists."
                )
            )

        return code


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense

        fields = [
            "category",
            "expense_date",
            "description",
            "amount",
            "payment_method",
            "payee",
            "reference",
            "notes",
        ]

        widgets = {
            "expense_date": forms.DateInput(
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

        categories = (
            ExpenseCategory.objects
            .filter(is_active=True)
        )

        if (
            self.instance.pk
            and self.instance.category_id
        ):
            categories = (
                ExpenseCategory.objects
                .filter(
                    Q(is_active=True)
                    | Q(
                        pk=self.instance.category_id
                    )
                )
            )

        self.fields["category"].queryset = (
            categories.order_by("name")
        )

        self.fields["description"].widget.attrs[
            "placeholder"
        ] = "Explain what the expense was for"

        self.fields["amount"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0.01",
                "placeholder": "0",
            }
        )

        self.fields["payee"].widget.attrs[
            "placeholder"
        ] = "Person or company paid"

        self.fields["reference"].widget.attrs[
            "placeholder"
        ] = (
            "Receipt or transaction reference"
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = "Optional additional information"

    def clean_description(self):
        description = self.cleaned_data.get(
            "description",
            "",
        ).strip()

        if len(description) < 3:
            raise forms.ValidationError(
                (
                    "Enter a clear description of "
                    "the expense."
                )
            )

        return description

    def clean_amount(self):
        amount = self.cleaned_data.get(
            "amount"
        )

        if (
            amount is None
            or amount <= Decimal("0.00")
        ):
            raise forms.ValidationError(
                (
                    "Expense amount must be "
                    "greater than zero."
                )
            )

        return amount