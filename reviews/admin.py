from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("__str__", "rating", "status", "created_at")
    list_filter = ("status", "rating")
    list_editable = ("status",)
