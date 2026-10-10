from django.contrib import admin

from .models import AuditLog, Notification


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "model_label", "object_repr")
    list_filter = ("action", "model_label")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False


admin.site.register(Notification, list_display=("user", "message", "is_read", "created_at"))
