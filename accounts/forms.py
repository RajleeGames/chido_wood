from django import forms
from django.contrib.auth.forms import (
    PasswordChangeForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User


class StyledFormMixin:
    def apply_styles(self):
        for field_name, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault(
                    "class",
                    "form-check-input"
                )

            elif isinstance(
                widget,
                forms.CheckboxSelectMultiple
            ):
                widget.attrs.setdefault(
                    "class",
                    "checkbox-list"
                )

            elif isinstance(
                widget,
                forms.SelectMultiple
            ):
                widget.attrs.setdefault(
                    "class",
                    "form-select form-select-multiple"
                )

            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault(
                    "class",
                    "form-select"
                )

            else:
                widget.attrs.setdefault(
                    "class",
                    "form-control"
                )

            widget.attrs.setdefault(
                "id",
                f"id_{field_name}"
            )

            # --------------------------------------
            # SAFE NUMBER / DECIMAL INPUTS
            # --------------------------------------
            if (
                isinstance(
                    widget,
                    forms.NumberInput
                )
                and isinstance(
                    field,
                    (
                        forms.DecimalField,
                        forms.IntegerField,
                    )
                )
            ):
                # Avoid browser spinner/wheel changing values.
                widget.input_type = "text"

                if isinstance(
                    field,
                    forms.DecimalField
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

class UserCreateForm(
    StyledFormMixin,
    UserCreationForm,
):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Example: cashier01",
                "autocomplete": "off",
            }
        )

        self.fields["first_name"].widget.attrs[
            "placeholder"
        ] = "First name"

        self.fields["last_name"].widget.attrs[
            "placeholder"
        ] = "Last name"

        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "Optional email address",
                "autocomplete": "off",
            }
        )

        self.fields["phone"].widget.attrs[
            "placeholder"
        ] = "Example: 0754 000 000"

        self.fields["password1"].widget.attrs.update(
            {
                "placeholder": "Create a strong password",
                "autocomplete": "new-password",
                "data-generated-password-target": "primary",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "placeholder": "Repeat the password",
                "autocomplete": "new-password",
                "data-generated-password-target": "confirmation",
            }
        )

        self.fields["is_active"].initial = True

    def clean_email(self):
        email = self.cleaned_data.get(
            "email",
            "",
        ).strip()

        if (
            email
            and User.objects.filter(
                email__iexact=email
            ).exists()
        ):
            raise forms.ValidationError(
                "A user with this email address already exists."
            )

        return email


class UserUpdateForm(
    StyledFormMixin,
    forms.ModelForm,
):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

        self.fields["username"].widget.attrs[
            "placeholder"
        ] = "Username"

        self.fields["first_name"].widget.attrs[
            "placeholder"
        ] = "First name"

        self.fields["last_name"].widget.attrs[
            "placeholder"
        ] = "Last name"

        self.fields["email"].widget.attrs[
            "placeholder"
        ] = "Optional email address"

        self.fields["phone"].widget.attrs[
            "placeholder"
        ] = "Phone number"

    def clean_email(self):
        email = self.cleaned_data.get(
            "email",
            "",
        ).strip()

        duplicate_users = User.objects.filter(
            email__iexact=email
        )

        if self.instance.pk:
            duplicate_users = duplicate_users.exclude(
                pk=self.instance.pk
            )

        if email and duplicate_users.exists():
            raise forms.ValidationError(
                "A user with this email address already exists."
            )

        return email


class ProfileForm(
    StyledFormMixin,
    forms.ModelForm,
):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

        self.fields["first_name"].widget.attrs[
            "placeholder"
        ] = "First name"

        self.fields["last_name"].widget.attrs[
            "placeholder"
        ] = "Last name"

        self.fields["email"].widget.attrs[
            "placeholder"
        ] = "Email address"

        self.fields["phone"].widget.attrs[
            "placeholder"
        ] = "Phone number"

    def clean_email(self):
        email = self.cleaned_data.get(
            "email",
            "",
        ).strip()

        duplicate_users = User.objects.filter(
            email__iexact=email
        ).exclude(
            pk=self.instance.pk
        )

        if email and duplicate_users.exists():
            raise forms.ValidationError(
                "A user with this email address already exists."
            )

        return email


class AdminSetPasswordForm(
    StyledFormMixin,
    SetPasswordForm,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

        self.fields["new_password1"].widget.attrs.update(
            {
                "placeholder": "Enter a new strong password",
                "autocomplete": "new-password",
                "data-generated-password-target": "primary",
            }
        )

        self.fields["new_password2"].widget.attrs.update(
            {
                "placeholder": "Repeat the new password",
                "autocomplete": "new-password",
                "data-generated-password-target": "confirmation",
            }
        )


class OwnPasswordChangeForm(
    StyledFormMixin,
    PasswordChangeForm,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

        self.fields["old_password"].widget.attrs.update(
            {
                "placeholder": "Current password",
                "autocomplete": "current-password",
            }
        )

        self.fields["new_password1"].widget.attrs.update(
            {
                "placeholder": "New strong password",
                "autocomplete": "new-password",
                "data-generated-password-target": "primary",
            }
        )

        self.fields["new_password2"].widget.attrs.update(
            {
                "placeholder": "Repeat the new password",
                "autocomplete": "new-password",
                "data-generated-password-target": "confirmation",
            }
        )
