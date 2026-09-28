from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [("refunds", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=64)),
                ("message", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("refund_request", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_logs", to="refunds.refundrequest")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(model_name="auditlog", index=models.Index(fields=["refund_request", "-created_at"], name="audit_audit_refund__912ef6_idx")),
    ]
