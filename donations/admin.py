from django.contrib import admin

from .models import Donation, Project, ProjectUpdate


class UpdateInline(admin.StackedInline):
    model = ProjectUpdate
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "community", "goal_amount", "phase", "status", "is_demo")
    list_filter = ("phase", "status", "is_demo")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [UpdateInline]


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "amount", "status", "method", "created_at", "verified_by")
    list_filter = ("status", "method")
    readonly_fields = ("verified_by", "verified_at", "created_at")
    # La confirmación se hace desde el panel /panel/administracion/donaciones/ para registrar quién verificó.
