"""Top-level URL configuration.

Business API routes will be added in Stage 4 after their contracts are defined.
"""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.refunds.urls")),
]
