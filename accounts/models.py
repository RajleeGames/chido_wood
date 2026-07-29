from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        db_index=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    def __str__(self):
        full_name = self.get_full_name().strip()

        if full_name:
            return full_name

        return self.username

    @property
    def is_admin_user(self):
        return (
            self.is_superuser
            or self.role == self.Role.ADMIN
        )

    @property
    def is_manager_user(self):
        """
        True for both Administrator and Manager.

        Used in templates to hide management links
        from cashiers.
        """
        return (
            self.is_superuser
            or self.role
            in {
                self.Role.ADMIN,
                self.Role.MANAGER,
            }
        )

    @property
    def is_cashier_user(self):
        return (
            not self.is_superuser
            and self.role == self.Role.CASHIER
        )