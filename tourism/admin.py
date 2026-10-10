from django.contrib import admin

from .models import Place, TouristService


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "community", "status", "location_verified", "is_demo")
    list_filter = ("kind", "status", "location_verified", "is_demo")
    search_fields = ("name", "community__name")
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(TouristService, list_display=("name", "kind", "community", "status"), list_filter=("kind", "status"))
