from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ReceiptSettings(models.Model):
    business_name = models.CharField(max_length=120, default="CHIDO WOOD")
    receipt_title = models.CharField(max_length=80, default="SALES RECEIPT")
    address = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    tin = models.CharField("TIN", max_length=60, blank=True)
    vrn = models.CharField("VRN", max_length=60, blank=True)
    header_note = models.CharField(max_length=200, blank=True)
    footer_line_1 = models.CharField(
        max_length=160,
        default="Thank you for your business.",
        blank=True,
    )
    footer_line_2 = models.CharField(
        max_length=160,
        default="Karibu tena.",
        blank=True,
    )
    characters_per_line = models.PositiveSmallIntegerField(
        default=42,
        validators=[MinValueValidator(32), MaxValueValidator(64)],
    )
    feed_lines_before_cut = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(2), MaxValueValidator(12)],
    )
    show_customer_phone = models.BooleanField(default=True)
    show_cashier = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Receipt settings"
        verbose_name_plural = "Receipt settings"

    def __str__(self):
        return "Receipt settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
