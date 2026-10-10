from django.contrib import admin

from .models import CustomTrip, CustomTripStop, FavoriteItinerary, Itinerary, ItineraryStop


class StopInline(admin.TabularInline):
    model = ItineraryStop
    extra = 1


class TripStopInline(admin.TabularInline):
    model = CustomTripStop
    extra = 0


@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "province", "duration_days", "status", "is_demo")
    list_filter = ("kind", "status", "is_demo")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [StopInline]


@admin.register(CustomTrip)
class CustomTripAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "start_date", "updated_at")
    inlines = [TripStopInline]


admin.site.register(FavoriteItinerary, list_display=("user", "itinerary", "created_at"))
