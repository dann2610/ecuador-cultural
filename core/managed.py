"""Registro de contenidos administrables por comunidad y moderables por el administrador."""
from communities.forms import PhotoForm
from communities.models import Community, Photo
from culture.forms import CraftForm, CulturalContentForm, DishForm, FestivityForm
from culture.models import Craft, CulturalContent, Dish, Festivity
from donations.forms import ProjectForm
from donations.models import Project
from itineraries.models import Itinerary
from tourism.forms import PlaceForm, TouristServiceForm
from tourism.models import Place, TouristService

# clave URL → (modelo, formulario, etiqueta singular, etiqueta plural)
MANAGED = {
    "contenido": (CulturalContent, CulturalContentForm, "contenido cultural", "Contenidos culturales"),
    "plato": (Dish, DishForm, "plato típico", "Gastronomía"),
    "artesania": (Craft, CraftForm, "artesanía", "Artesanías"),
    "festividad": (Festivity, FestivityForm, "festividad", "Festividades"),
    "lugar": (Place, PlaceForm, "lugar turístico", "Lugares turísticos"),
    "servicio": (TouristService, TouristServiceForm, "servicio turístico", "Servicios"),
    "proyecto": (Project, ProjectForm, "proyecto comunitario", "Proyectos comunitarios"),
    "foto": (Photo, PhotoForm, "fotografía", "Fotografías"),
}

# Modelos que pasan por la cola de moderación
MODERATED = {
    "comunidad": Community,
    "contenido": CulturalContent,
    "plato": Dish,
    "artesania": Craft,
    "festividad": Festivity,
    "lugar": Place,
    "servicio": TouristService,
    "proyecto": Project,
    "itinerario": Itinerary,
}


def display_name(obj):
    return getattr(obj, "name", None) or getattr(obj, "title", None) or str(obj)
