from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("preguntar/", views.chat_api, name="ask"),
    path("sugerencias/", views.suggestions, name="suggestions"),
    path("historial/eliminar/", views.delete_history, name="delete_history"),
]
