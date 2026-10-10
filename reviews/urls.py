from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("mis-resenas/", views.my_reviews, name="mine"),
    path("nueva/<str:kind>/<slug:slug>/", views.create_review, name="create"),
    path("<int:pk>/editar/", views.edit_review, name="edit"),
    path("<int:pk>/eliminar/", views.delete_review, name="delete"),
]
