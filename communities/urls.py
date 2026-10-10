from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("", views.community_list, name="list"),
    path("registrar-comunidad/", views.request_registration, name="request"),
    path("<slug:slug>/", views.community_detail, name="detail"),
    path("<slug:slug>/favorito/", views.toggle_favorite, name="favorite"),
]
