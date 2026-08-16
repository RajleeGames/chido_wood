from decimal import Decimal

from django import forms

from .models import (
    Customer,
    CustomerPayment,
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


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer

        fields = [
            "name",
            "phone",
            "email",
            "address",
            "opening_balance",
            "credit_limit",
            "notes",
            "is_active",
        ]

        widgets = {
            "address": forms.Textarea(
                attrs={
                    "rows": 3,
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

        self.fields["name"].widget.attrs.update(
            {
                "placeholder": "Customer full name",
                "autocomplete": "name",
            }
        )

        self.fields["phone"].widget.attrs.update(
            {
                "placeholder": "Example: 0754 000 000",
                "autocomplete": "tel",
            }
        )

        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Optional email address",
                "autocomplete": "email",
            }
        )

        self.fields["address"].widget.attrs[
            "placeholder"
        ] = "Optional customer address"

        self.fields["opening_balance"].required = False

        self.fields["opening_balance"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["credit_limit"].required = False

        self.fields["credit_limit"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0",
                "placeholder": "0",
            }
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = "Optional information about this customer"

    def clean_name(self):
        name = self.cleaned_data.get(
            "name",
            "",
        ).strip()

        if len(name) < 2:
            raise forms.ValidationError(
                "Enter a valid customer name."
            )

        return name

    def clean_phone(self):
        phone = self.cleaned_data.get(
            "phone",
            "",
        ).strip()

        if not phone:
            return ""

        duplicates = Customer.objects.filter(
            phone__iexact=phone
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(
                pk=self.instance.pk
            )

        if duplicates.exists():
            raise forms.ValidationError(
                (
                    "Another customer is already "
                    "registered with this phone number."
                )
            )

        return phone

    def clean_opening_balance(self):
        opening_balance = self.cleaned_data.get(
            "opening_balance"
        )

        if opening_balance in (None, ""):
            opening_balance = Decimal("0.00")

        if opening_balance < Decimal("0.00"):
            raise forms.ValidationError(
                "Opening balance cannot be negative."
            )

        if (
            self.instance.pk
            and opening_balance
            < self.instance.opening_balance_paid
        ):
            raise forms.ValidationError(
                (
                    "Opening balance cannot be lower "
                    "than the amount already paid toward it."
                )
            )

        return opening_balance

    def clean_credit_limit(self):
        credit_limit = self.cleaned_data.get(
            "credit_limit"
        )

        if credit_limit in (None, ""):
            return Decimal("0.00")

        if credit_limit < Decimal("0.00"):
            raise forms.ValidationError(
                "Credit limit cannot be negative."
            )

        return credit_limit


class CustomerPaymentForm(StyledModelForm):
    class Meta:
        model = CustomerPayment

        fields = [
            "payment_date",
            "amount",
            "payment_method",
            "reference",
            "notes",
        ]

        widgets = {
            "payment_date": forms.DateTimeInput(
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
        maximum_amount=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.maximum_amount = maximum_amount

        self.apply_styles()

        self.fields[
            "payment_date"
        ].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

        self.fields["amount"].widget.attrs.update(
            {
                "step": "0.01",
                "min": "0.01",
                "placeholder": "0",
            }
        )

        if maximum_amount is not None:
            self.fields["amount"].widget.attrs[
                "max"
            ] = str(maximum_amount)

        self.fields["reference"].widget.attrs[
            "placeholder"
        ] = (
            "Mobile transaction, bank or cheque reference"
        )

        self.fields["notes"].widget.attrs[
            "placeholder"
        ] = "Optional payment notes"

    def clean_amount(self):
        amount = self.cleaned_data.get(
            "amount"
        )

        if amount is None or amount <= Decimal("0.00"):
            raise forms.ValidationError(
                "Payment amount must be greater than zero."
            )

        if (
            self.maximum_amount is not None
            and amount > self.maximum_amount
        ):
            raise forms.ValidationError(
                (
                    "Payment cannot exceed the customer's "
                    "current outstanding balance."
                )
            )

        return amount