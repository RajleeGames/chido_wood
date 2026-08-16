from decimal import Decimal

from django import forms

from .models import Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier

        fields = [
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "tin",
            "opening_balance",
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

        for field_name, field in self.fields.items():
            widget = field.widget

            if isinstance(
                widget,
                forms.CheckboxInput,
            ):
                widget.attrs["class"] = (
                    "form-check-input"
                )

            else:
                existing_class = widget.attrs.get(
                    "class",
                    "",
                )

                widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()

            # ------------------------------------------
            # SAFE NUMBER / DECIMAL INPUTS
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
                # Prevent browser spinner and
                # accidental mouse-wheel changes.
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

            widget.attrs.setdefault(
                "id",
                f"id_{field_name}"
            )

        self.fields["name"].widget.attrs[
            "placeholder"
        ] = "Example: Kilimanjaro Timber Supplies"

        self.fields["contact_person"].widget.attrs[
            "placeholder"
        ] = "Supplier contact person"

        self.fields["phone"].widget.attrs[
            "placeholder"
        ] = "Example: 0754 000 000"

        self.fields["email"].widget.attrs[
            "placeholder"
        ] = "Optional email address"

        self.fields["tin"].widget.attrs[
            "placeholder"
        ] = "Optional TIN"

        self.fields["opening_balance"].required = False

        self.fields["opening_balance"].widget.attrs[
            "placeholder"
        ] = "0"

        self.fields["opening_balance"].widget.attrs[
            "step"
        ] = "0.01"

    def clean_opening_balance(self):
        opening_balance = self.cleaned_data.get(
            "opening_balance"
        )

        if opening_balance in (None, ""):
            return Decimal("0.00")

        if opening_balance < Decimal("0.00"):
            raise forms.ValidationError(
                "Opening balance cannot be negative."
            )

        return opening_balance