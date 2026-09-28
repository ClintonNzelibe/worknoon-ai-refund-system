from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "status", "total_amount", "currency", "ordered_at")
    list_filter = ("status", "currency")
    search_fields = ("reference", "customer__email", "customer__full_name")
    readonly_fields = ("created_at", "updated_at")
    inlines = (OrderItemInline,)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("product_name", "sku", "order", "unit_price", "quantity")
    search_fields = ("sku", "product_name", "order__reference")
