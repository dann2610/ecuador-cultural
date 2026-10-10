from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Ecuador Cultural · Administración técnica"
admin.site.site_title = "Ecuador Cultural"
admin.site.index_title = "Gestión de datos"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/", include("accounts.urls")),
    path("pueblos/", include("communities.urls")),
    path("itinerarios/", include("itineraries.urls")),
    path("proyectos/", include("donations.urls")),
    path("resenas/", include("reviews.urls")),
    path("asistente/", include("chatbot.urls")),
    path("", include("culture.urls")),
    path("", include("tourism.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.errors.not_found"
handler500 = "core.views.errors.server_error"
handler403 = "core.views.errors.forbidden"
