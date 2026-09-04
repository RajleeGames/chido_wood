from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import Document, DocumentItem


class DateInput(forms.DateInput):
    input_type = "date"


class CommaDecimalField(forms.DecimalField):
    """
    DecimalField that safely accepts display values such as:

        2,000
        45,000
        1,250.50

    The commas are removed before Django converts the value to Decimal.
    This means the browser can show grouped money values without causing
    DecimalField validation errors.
    """

    def to_python(self, value):
        if isinstance(value, str):
            value = (
                value
                .replace(",", "")
                .strip()
            )

        return super().to_python(value)


class DocumentForm(forms.ModelForm):
    # IMPORTANT:
    # Delivery Note does not use VAT.
    # Make VAT optional at FORM level so hiding it does not cause
    # "This field is required" before clean_vat_percent() runs.
    vat_percent = forms.DecimalField(
        required=False,
        min_value=Decimal("0.00"),
        max_digits=5,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "class": "js-vat-percent js-clear-zero",
                "placeholder": "0",
            }
        ),
    )

    class Meta:
        model = Document
        fields = [
            "document_type",
            "date",
            "customer_name",
            "customer_phone",
            "customer_address",
            "customer_reference",
            "subject",
            "vat_percent",
            "notes",
            "status",
        ]
        widgets = {
            "date": DateInput(),
            "customer_name": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                }
            ),
            "customer_phone": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                }
            ),
            "customer_address": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                }
            ),
            "customer_reference": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                }
            ),
            "subject": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                }
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
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        if (
            self.instance
            and self.instance.pk
        ):
            self.fields[
                "document_type"
            ].disabled = True

        if (
            not self.is_bound
            and not (
                self.instance
                and self.instance.pk
            )
        ):
            self.initial[
                "vat_percent"
            ] = ""

    def clean_vat_percent(self):
        document_type = (
            self.cleaned_data.get(
                "document_type"
            )
        )

        if (
            document_type
            == Document.DocumentType.DELIVERY_NOTE
        ):
            return Decimal("0.00")

        return (
            self.cleaned_data.get(
                "vat_percent"
            )
            or Decimal("0.00")
        )


class DocumentItemForm(forms.ModelForm):
    quantity = forms.DecimalField(
        required=True,
        min_value=Decimal("0.00"),
        max_digits=14,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "class": (
                    "js-item-qty "
                    "js-clear-zero"
                ),
                "placeholder": "Qty",
            }
        ),
    )

    # Optional because Delivery Notes do not use a selling price.
    unit_price = CommaDecimalField(
        required=False,
        min_value=Decimal("0.00"),
        max_digits=16,
        decimal_places=2,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "class": (
                    "js-item-price "
                    "js-money-input "
                    "js-clear-zero"
                ),
                "placeholder": "e.g. 45,000",
            }
        ),
    )

    class Meta:
        model = DocumentItem
        fields = [
            "description",
            "quantity",
            "unit",
            "unit_price",
            "sort_order",
        ]
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Item / goods name"
                    ),
                    "autocomplete": "off",
                    "class": (
                        "js-item-description"
                    ),
                }
            ),
            "unit": forms.TextInput(
                attrs={
                    "placeholder": (
                        "pcs / ft / m / set"
                    ),
                    "autocomplete": "off",
                }
            ),
            "sort_order": forms.HiddenInput(),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        if (
            not self.is_bound
            and not (
                self.instance
                and self.instance.pk
            )
        ):
            self.initial["quantity"] = ""
            self.initial["unit_price"] = ""

    def clean_unit_price(self):
        return (
            self.cleaned_data.get(
                "unit_price"
            )
            or Decimal("0.00")
        )


DocumentItemFormSet = inlineformset_factory(
    Document,
    DocumentItem,
    form=DocumentItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
