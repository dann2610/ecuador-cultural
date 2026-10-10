from django.urls import path

from . import views

app_name = "culture"

urlpatterns = [
    path("gastronomia/", views.gastronomy, name="gastronomy"),
    path("artesanias/", views.crafts, name="crafts"),
    path("cultura-y-tradiciones/", views.traditions, name="traditions"),
]
