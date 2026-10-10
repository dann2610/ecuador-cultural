from django.urls import path

from . import views

app_name = "donations"

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("aportar/", views.donate, name="donate"),
    path("mis-aportes/", views.my_donations, name="mine"),
    path("<slug:slug>/", views.project_detail, name="project_detail"),
    path("<slug:slug>/avance/", views.add_update, name="add_update"),
    path("<slug:slug>/aportes/", views.project_donations, name="project_donations"),
]
