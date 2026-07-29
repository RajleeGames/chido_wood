from django.core.management.base import BaseCommand

from sms.models import SMSSetting, SMSTemplate


DEFAULT_TEMPLATES = [
    {
        "title": "Sale Thank You - Swahili",
        "category": SMSTemplate.Category.THANK_YOU,
        "language": SMSTemplate.Language.SWAHILI,
        "message": (
            "Ndugu {first_name}, asante kwa kununua CHIDO Wood. "
            "Jumla TZS {amount}. Risiti {receipt}. Karibu tena."
        ),
    },
    {
        "title": "Sale Thank You - English",
        "category": SMSTemplate.Category.THANK_YOU,
        "language": SMSTemplate.Language.ENGLISH,
        "message": (
            "Dear {first_name}, thank you for shopping with CHIDO Wood. "
            "Total TZS {amount}. Receipt {receipt}. Welcome again."
        ),
    },
    {
        "title": "Debt Reminder - Swahili",
        "category": SMSTemplate.Category.DEBT_REMINDER,
        "language": SMSTemplate.Language.SWAHILI,
        "message": (
            "Ndugu {first_name}, tunakukumbusha salio lako la TZS {balance} "
            "kwa CHIDO Wood. Asante."
        ),
    },
    {
        "title": "Payment Confirmation - Swahili",
        "category": SMSTemplate.Category.PAYMENT_CONFIRMATION,
        "language": SMSTemplate.Language.SWAHILI,
        "message": (
            "Ndugu {first_name}, tumepokea malipo yako ya TZS {amount}. "
            "Salio lililobaki ni TZS {balance}. Asante."
        ),
    },
    {
        "title": "New Stock Promotion - Swahili",
        "category": SMSTemplate.Category.NEW_STOCK,
        "language": SMSTemplate.Language.SWAHILI,
        "message": (
            "Ndugu {first_name}, bidhaa mpya za mbao zimewasili CHIDO Wood. "
            "Tembelea duka letu kwa maelezo zaidi."
        ),
    },
]


class Command(BaseCommand):
    help = "Create the default CHIDO Wood SMS templates and settings."

    def handle(self, *args, **options):
        created_count = 0

        for item in DEFAULT_TEMPLATES:
            _, created = SMSTemplate.objects.get_or_create(
                title=item["title"],
                language=item["language"],
                defaults={
                    "category": item["category"],
                    "message": item["message"],
                    "is_active": True,
                },
            )
            created_count += int(created)

        setting = SMSSetting.load()
        if not setting.automatic_sale_template_id:
            setting.automatic_sale_template = SMSTemplate.objects.filter(
                category=SMSTemplate.Category.THANK_YOU,
                language=SMSTemplate.Language.SWAHILI,
                is_active=True,
            ).first()
            setting.save(update_fields=["automatic_sale_template", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"SMS Center initialized. {created_count} templates created."
            )
        )
