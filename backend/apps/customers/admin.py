from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "user", "created_at")
    search_fields = ("full_name", "email")
    readonly_fields = ("created_at", "updated_at")
