import decimal

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [("orders", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="RefundRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("paid", "Paid"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
                ("reason", models.TextField()),
                ("requested_amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))])),
                ("resolution_note", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refund_requests", to="orders.order")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(model_name="refundrequest", constraint=models.CheckConstraint(condition=models.Q(("requested_amount__gt", 0)), name="refund_requested_amount_positive")),
        migrations.AddIndex(model_name="refundrequest", index=models.Index(fields=["order", "status", "-created_at"], name="refunds_ref_order_i_3e961d_idx")),
        migrations.AddIndex(model_name="refundrequest", index=models.Index(fields=["status", "-created_at"], name="refunds_ref_status_9c10bf_idx")),
    ]
