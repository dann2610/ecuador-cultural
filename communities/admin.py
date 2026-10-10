from django.contrib import admin

from .models import (Canton, Category, Community, CommunityRequest, Favorite, Photo, Province,
                     RepresentativeAssignment)


class PhotoInline(admin.TabularInline):
    model = Photo
    fk_name = "community"
    extra = 0
    fields = ("image", "title", "alt_text", "author", "license", "is_featured", "is_cover", "order")


class AssignmentInline(admin.TabularInline):
    model = RepresentativeAssignment
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "status", "is_demo", "location_verified", "featured_order")
    list_filter = ("status", "province__region", "province", "is_demo", "location_verified")
    list_editable = ("status", "featured_order")
    search_fields = ("name", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("categories",)
    inlines = [AssignmentInline, PhotoInline]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "community", "place", "is_featured", "is_cover", "order", "license", "is_placeholder")
    list_filter = ("is_featured", "is_cover", "kind", "is_placeholder")
    search_fields = ("title", "author", "community__name")


admin.site.register(Province, list_display=("name", "region"), list_filter=("region",), search_fields=("name",))
admin.site.register(Canton, list_display=("name", "province"), list_filter=("province",), search_fields=("name",))
admin.site.register(Category, list_display=("name", "icon", "order"), prepopulated_fields={"slug": ("name",)})
admin.site.register(CommunityRequest, list_display=("community_name", "user", "province", "status", "created_at"),
                    list_filter=("status",))
admin.site.register(Favorite, list_display=("user", "community", "place", "created_at"))
admin.site.register(RepresentativeAssignment, list_display=("user", "community", "is_active", "assigned_at"))
