from __future__ import annotations

from django import forms

from .models import (
    SMSCampaign,
    SMSContact,
    SMSContactGroup,
    SMSSetting,
    SMSTemplate,
    SenderID,
)
from .services.personalization import calculate_sms_parts
from .services.phones import is_valid_tz_phone, normalize_phone, split_phone_values


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


class SenderIDForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SenderID
        fields = [
            "name",
            "status",
            "is_active",
            "is_default",
            "provider_reference",
            "rejection_reason",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "rejection_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, can_approve=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_approve = can_approve
        self.apply_styles()

        self.fields["name"].widget.attrs.update(
            {
                "placeholder": "CHIDOWOOD",
                "maxlength": 11,
                "autocomplete": "off",
            }
        )

        if not can_approve:
            for field_name in (
                "status",
                "is_active",
                "is_default",
                "provider_reference",
                "rejection_reason",
            ):
                self.fields.pop(field_name, None)

    def clean_name(self):
        return str(self.cleaned_data.get("name") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status", getattr(self.instance, "status", SenderID.Status.PENDING))
        is_active = cleaned.get("is_active", getattr(self.instance, "is_active", False))
        is_default = cleaned.get("is_default", getattr(self.instance, "is_default", False))

        if (is_active or is_default) and status != SenderID.Status.APPROVED:
            raise forms.ValidationError(
                "Only an approved Sender ID can be active or selected as default."
            )

        return cleaned


class SMSSettingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SMSSetting
        fields = [
            "provider",
            "business_name",
            "default_language",
            "default_sender",
            "automatic_sale_template",
            "transaction_sms_enabled",
            "promotional_sms_enabled",
            "automatic_sale_sms_enabled",
            "send_limit",
            "low_balance_threshold",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_sender"].queryset = SenderID.objects.filter(
            status=SenderID.Status.APPROVED,
            is_active=True,
        )
        self.fields["automatic_sale_template"].queryset = SMSTemplate.objects.filter(
            is_active=True,
            category=SMSTemplate.Category.THANK_YOU,
        )
        self.apply_styles()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("automatic_sale_sms_enabled"):
            if not cleaned.get("default_sender"):
                self.add_error(
                    "default_sender",
                    "Select a default sender before enabling automatic sale messages.",
                )
            if not cleaned.get("automatic_sale_template"):
                self.add_error(
                    "automatic_sale_template",
                    "Select a thank-you template before enabling automatic sale messages.",
                )
        return cleaned


class SMSContactGroupForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SMSContactGroup
        fields = ["name", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class SMSContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SMSContact
        fields = [
            "customer",
            "name",
            "phone",
            "email",
            "groups",
            "source",
            "is_active",
            "allow_transaction_sms",
            "allow_promotional_sms",
            "opted_out",
            "notes",
        ]
        widgets = {
            "groups": forms.SelectMultiple(attrs={"size": 6}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["groups"].queryset = SMSContactGroup.objects.all()
        self.apply_styles()
        self.fields["phone"].widget.attrs.update(
            {"placeholder": "0712345678 or 255712345678", "inputmode": "tel"}
        )
        self.fields["customer"].required = False

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone"))
        if not is_valid_tz_phone(phone):
            raise forms.ValidationError(
                "Enter a valid Tanzanian mobile number, for example 0712345678."
            )
        return phone

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("opted_out"):
            cleaned["allow_transaction_sms"] = False
            cleaned["allow_promotional_sms"] = False
        return cleaned


class SMSTemplateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SMSTemplate
        fields = ["title", "category", "language", "message", "is_active"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 7,
                    "data-sms-message-input": "true",
                    "placeholder": "Ndugu {first_name}, asante kwa kufanya biashara na CHIDO Wood.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()

    def clean_message(self):
        message = str(self.cleaned_data.get("message") or "").strip()
        if not message:
            raise forms.ValidationError("Enter the SMS message.")
        if calculate_sms_parts(message)["parts"] > 6:
            raise forms.ValidationError("Keep the template within 6 SMS parts.")
        return message


class SMSImportForm(StyledFormMixin, forms.Form):
    csv_file = forms.FileField(
        required=False,
        help_text="CSV headings may include name, phone and email.",
    )
    pasted_contacts = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "placeholder": "Asha,0712345678\nJuma,0755555555\n0766666666",
            }
        ),
        help_text="Use one contact per line: Name,Phone or Phone only.",
    )
    group = forms.ModelChoiceField(
        queryset=SMSContactGroup.objects.none(),
        required=False,
        empty_label="Do not add to a group",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = SMSContactGroup.objects.all()
        self.apply_styles()

    def clean_csv_file(self):
        uploaded = self.cleaned_data.get("csv_file")
        if uploaded and not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        if uploaded and uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV file must be 2 MB or smaller.")
        return uploaded

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("csv_file") and not str(cleaned.get("pasted_contacts") or "").strip():
            raise forms.ValidationError("Upload a CSV file or paste contacts.")
        return cleaned


class SMSSendForm(StyledFormMixin, forms.Form):
    AUDIENCE_SELECTED = "selected"
    AUDIENCE_GROUPS = "groups"
    AUDIENCE_ALL_TRANSACTION = "all_transaction"
    AUDIENCE_ALL_PROMOTIONAL = "all_promotional"
    AUDIENCE_MANUAL = "manual"

    AUDIENCE_CHOICES = [
        (AUDIENCE_SELECTED, "Selected contacts"),
        (AUDIENCE_GROUPS, "Selected groups"),
        (AUDIENCE_ALL_TRANSACTION, "All transaction-enabled contacts"),
        (AUDIENCE_ALL_PROMOTIONAL, "All promotional opt-in contacts"),
        (AUDIENCE_MANUAL, "Manual phone numbers"),
    ]

    campaign_title = forms.CharField(
        required=False,
        max_length=150,
        help_text="Optional. A campaign is still created for multi-recipient sends.",
    )
    sender = forms.ModelChoiceField(queryset=SenderID.objects.none())
    message_type = forms.ChoiceField(choices=SMSCampaign.MessageType.choices)
    language = forms.ChoiceField(choices=SMSTemplate.Language.choices, initial="sw")
    template = forms.ModelChoiceField(
        queryset=SMSTemplate.objects.none(),
        required=False,
        empty_label="Write a custom message",
    )
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, initial=AUDIENCE_SELECTED)
    groups = forms.ModelMultipleChoiceField(
        queryset=SMSContactGroup.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 7}),
    )
    contacts = forms.ModelMultipleChoiceField(
        queryset=SMSContact.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 10}),
    )
    manual_numbers = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "0712345678\n0755555555",
            }
        ),
        help_text="Separate numbers using a new line, comma or semicolon.",
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "data-sms-message-input": "true",
                "placeholder": "Write the SMS message here.",
            }
        )
    )

    def __init__(self, *args, allow_promotional=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_promotional = allow_promotional
        self.fields["sender"].queryset = SenderID.objects.filter(
            status=SenderID.Status.APPROVED,
            is_active=True,
        )
        self.fields["template"].queryset = SMSTemplate.objects.filter(is_active=True)
        self.fields["groups"].queryset = SMSContactGroup.objects.all()
        self.fields["contacts"].queryset = SMSContact.objects.filter(is_active=True).order_by(
            "name", "phone"
        )

        setting = SMSSetting.load()
        if setting.default_sender_id:
            self.fields["sender"].initial = setting.default_sender_id
        self.fields["language"].initial = setting.default_language

        if not allow_promotional:
            self.fields["message_type"].choices = [
                (
                    SMSCampaign.MessageType.TRANSACTION,
                    SMSCampaign.MessageType.TRANSACTION.label,
                )
            ]
            self.fields["audience"].choices = [
                item
                for item in self.AUDIENCE_CHOICES
                if item[0] != self.AUDIENCE_ALL_PROMOTIONAL
            ]

        self.apply_styles()

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience")
        message_type = cleaned.get("message_type")
        message = str(cleaned.get("message") or "").strip()
        template = cleaned.get("template")

        if template and not message:
            message = template.message
            cleaned["message"] = message

        if not message:
            self.add_error("message", "Enter the SMS message.")

        if message and calculate_sms_parts(message)["parts"] > 6:
            self.add_error("message", "Keep the message within 6 SMS parts.")

        if message_type == SMSCampaign.MessageType.PROMOTIONAL and not self.allow_promotional:
            self.add_error("message_type", "Your role cannot send promotional messages.")

        if audience == self.AUDIENCE_SELECTED and not cleaned.get("contacts"):
            self.add_error("contacts", "Select at least one contact.")
        elif audience == self.AUDIENCE_GROUPS and not cleaned.get("groups"):
            self.add_error("groups", "Select at least one group.")
        elif audience == self.AUDIENCE_MANUAL:
            raw_numbers = list(split_phone_values(cleaned.get("manual_numbers")))
            valid_numbers = []
            invalid_numbers = []
            for raw in raw_numbers:
                phone = normalize_phone(raw)
                if is_valid_tz_phone(phone):
                    valid_numbers.append(phone)
                else:
                    invalid_numbers.append(raw)

            if invalid_numbers:
                self.add_error(
                    "manual_numbers",
                    "Invalid numbers: " + ", ".join(invalid_numbers[:6]),
                )
            elif not valid_numbers:
                self.add_error("manual_numbers", "Enter at least one valid phone number.")

            if message_type == SMSCampaign.MessageType.PROMOTIONAL:
                self.add_error(
                    "manual_numbers",
                    "Promotional SMS can only be sent to saved contacts who opted in.",
                )

            cleaned["normalized_manual_numbers"] = valid_numbers
        else:
            cleaned["normalized_manual_numbers"] = []

        return cleaned
