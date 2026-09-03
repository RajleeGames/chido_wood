from django import template
from core.models import ReceiptSettings

register = template.Library()

@register.simple_tag
def get_receipt_settings():
    return ReceiptSettings.load()
