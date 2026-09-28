from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("refunds", "0003_refundrequest_idempotency_key_and_more")]

    operations = [
        migrations.CreateModel(
            name="RefundAIAssistance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("available", "Available"), ("not_configured", "Not configured"), ("provider_unavailable", "Provider unavailable"), ("rate_limited", "Rate limited"), ("timed_out", "Timed out"), ("invalid_response", "Invalid response")], max_length=32)),
                ("provider", models.CharField(blank=True, max_length=32)),
                ("model_identifier", models.CharField(blank=True, max_length=128)),
                ("classification", models.CharField(blank=True, choices=[("consistent", "Consistent"), ("conflicting", "Conflicting"), ("unclear", "Unclear")], max_length=16)),
                ("risk", models.CharField(blank=True, choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")], max_length=16)),
                ("summary", models.CharField(blank=True, max_length=500)),
                ("reasoning", models.TextField(blank=True)),
                ("customer_message", models.TextField(blank=True)),
                ("policy_alignment", models.CharField(blank=True, max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("refund_request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="ai_assistance", to="refunds.refundrequest")),
            ],
        ),
        migrations.AddIndex(model_name="refundaiassistance", index=models.Index(fields=["status", "-created_at"], name="refunds_ref_status_30f133_idx")),
    ]
