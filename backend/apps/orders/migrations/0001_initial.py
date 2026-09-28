import decimal

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [("customers", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("placed", "Placed"), ("paid", "Paid"), ("fulfilled", "Fulfilled"), ("cancelled", "Cancelled")], default="placed", max_length=16)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("ordered_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="customers.customer")),
            ],
            options={"ordering": ["-ordered_at", "-id"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku", models.CharField(max_length=64)),
                ("product_name", models.CharField(max_length=255)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))])),
                ("quantity", models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="orders.order")),
            ],
        ),
        migrations.AddConstraint(model_name="order", constraint=models.CheckConstraint(condition=models.Q(("total_amount__gte", 0)), name="order_total_amount_nonnegative")),
        migrations.AddIndex(model_name="order", index=models.Index(fields=["customer", "status", "-ordered_at"], name="orders_orde_custome_64c2d7_idx")),
        migrations.AddConstraint(model_name="orderitem", constraint=models.CheckConstraint(condition=models.Q(("unit_price__gte", 0)), name="order_item_unit_price_nonnegative")),
        migrations.AddConstraint(model_name="orderitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gte", 1)), name="order_item_quantity_positive")),
        migrations.AddIndex(model_name="orderitem", index=models.Index(fields=["order", "sku"], name="orders_orde_order_i_ecd151_idx")),
    ]
