from django.urls import path

from . import views

app_name = "itineraries"

urlpatterns = [
    path("", views.itinerary_list, name="list"),
    path("nuevo/", views.manage_itinerary, name="create"),
    path("mis-recorridos/", views.trip_list, name="trips"),
    path("mis-recorridos/<int:pk>/", views.trip_detail, name="trip_detail"),
    path("mis-recorridos/<int:pk>/agregar/", views.trip_add_stop, name="trip_add_stop"),
    path("mis-recorridos/<int:pk>/reordenar/", views.trip_reorder, name="trip_reorder"),
    path("mis-recorridos/<int:pk>/eliminar/", views.trip_delete, name="trip_delete"),
    path("mis-recorridos/<int:pk>/parada/<int:stop_id>/<str:action>/", views.trip_stop_action,
         name="trip_stop_action"),
    path("<slug:slug>/", views.itinerary_detail, name="detail"),
    path("<slug:slug>/editar/", views.manage_itinerary, name="edit"),
    path("<slug:slug>/favorito/", views.toggle_favorite, name="favorite"),
    path("<slug:slug>/copiar/", views.trip_from_itinerary, name="copy"),
]
