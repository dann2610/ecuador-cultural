from django.contrib import admin

from .models import Craft, CulturalContent, Dish, Festivity

for model in (CulturalContent, Dish, Craft, Festivity):
    admin.site.register(model, list_display=("__str__", "community", "status", "is_demo", "updated_at"),
                        list_filter=("status", "is_demo"), search_fields=("community__name",))
