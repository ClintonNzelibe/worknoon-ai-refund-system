from django.conf import settings
from django.db import models


class Customer(models.Model):
    """A person or organization that places orders and requests refunds."""

    # Customers without an authenticated account remain support-managed only.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="refund_customer",
    )
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name", "id"]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"
