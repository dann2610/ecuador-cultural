from django.urls import path

from . import views

app_name = "tourism"

urlpatterns = [
    path("mapa/", views.map_page, name="map"),
    path("api/mapa/", views.map_data, name="map_data"),
    path("lugares/<slug:slug>/", views.place_detail, name="place_detail"),
    path("lugares/<slug:slug>/favorito/", views.toggle_place_favorite, name="place_favorite"),
]
