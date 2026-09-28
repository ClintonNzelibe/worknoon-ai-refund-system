from django.core.exceptions import ValidationError
from django.db import models


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit log entries are append-only.")

    def delete(self):
        raise ValidationError("Audit log entries cannot be deleted.")


class AuditLog(models.Model):
    """Append-only record of a refund request's meaningful state changes."""

    refund_request = models.ForeignKey(
        "refunds.RefundRequest",
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=["refund_request", "-created_at"])]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.action} for refund #{self.refund_request_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Audit log entries are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit log entries cannot be deleted.")
