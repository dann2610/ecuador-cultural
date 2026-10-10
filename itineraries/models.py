from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from communities.models import Community, Province, Region
from core.models import ReviewableModel
from core.services import google_maps_route_url
from core.validators import validate_image_file
from tourism.models import Place


class StopTarget(models.Model):
    """Parada que apunta a un lugar o a una comunidad registrados."""

    place = models.ForeignKey(Place, null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                              verbose_name="lugar")
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                                  verbose_name="pueblo")
    order = models.PositiveSmallIntegerField("orden", default=0)
    notes = models.CharField("notas", max_length=300, blank=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]

    def clean(self):
        if bool(self.place_id) == bool(self.community_id):
            raise ValidationError("Seleccione un lugar o un pueblo (solo uno).")

    @property
    def target(self):
        return self.place or self.community

    @property
    def name(self):
        return str(self.target)

    @property
    def latitude(self):
        return self.target.latitude

    @property
    def longitude(self):
        return self.target.longitude

    @property
    def directions_url(self):
        return self.target.directions_url

    @property
    def url(self):
        return self.target.get_absolute_url()

    @property
    def location_verified(self):
        return self.target.location_verified


class Itinerary(ReviewableModel):
    class Kind(models.TextChoices):
        CULTURAL = "cultural", "Cultural"
        GASTRONOMIC = "gastronomic", "Gastronómico"
        CRAFTS = "crafts", "De artesanías"
        HERITAGE = "heritage", "Histórico y patrimonial"
        NATURE = "nature", "Naturaleza y aventura"
        CHURCHES = "churches", "Iglesias y patrimonio"
        MULTI = "multi", "Recorrido por varios pueblos"

    class Difficulty(models.TextChoices):
        NA = "", "No aplica"
        EASY = "easy", "Baja"
        MEDIUM = "medium", "Media"
        HARD = "hard", "Alta"

    name = models.CharField("nombre", max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    cover = models.ImageField("fotografía de portada", upload_to="itineraries/", blank=True,
                              validators=[validate_image_file])
    cover_credit = models.CharField("crédito de la portada", max_length=200, blank=True)
    description = models.TextField("descripción")
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="itineraries", verbose_name="comunidad responsable")
    province = models.ForeignKey(Province, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="itineraries", verbose_name="provincia")
    region = models.CharField("región", max_length=10, choices=Region.choices, blank=True)
    duration_days = models.PositiveSmallIntegerField("duración estimada (días)", default=1,
                                                     validators=[MinValueValidator(1)])
    difficulty = models.CharField("dificultad", max_length=8, choices=Difficulty.choices, blank=True)
    kind = models.CharField("tipo de experiencia", max_length=12, choices=Kind.choices, db_index=True)
    budget_estimate = models.DecimalField("presupuesto orientativo (USD)", max_digits=8, decimal_places=2,
                                          null=True, blank=True, validators=[MinValueValidator(0)])
    budget_note = models.CharField("nota sobre el presupuesto", max_length=200, blank=True)
    distance_km = models.DecimalField("distancia estimada (km)", max_digits=7, decimal_places=1, null=True,
                                      blank=True, validators=[MinValueValidator(0)])
    estimates_verified = models.BooleanField("distancias y tiempos confirmados", default=False)
    recommendations = models.TextField("recomendaciones", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "itinerario"
        verbose_name_plural = "itinerarios"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or "itinerario"
            slug, n = base, 2
            while Itinerary.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        if self.province_id and not self.region:
            self.region = self.province.region
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("itineraries:detail", args=[self.slug])

    def route_url(self):
        return google_maps_route_url([(s.latitude, s.longitude) for s in self.stops.all() if s.target])


class ItineraryStop(StopTarget):
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name="stops",
                                  verbose_name="itinerario")
    day = models.PositiveSmallIntegerField("día", default=1, validators=[MinValueValidator(1)])
    travel_time_note = models.CharField("tiempo aproximado desde la parada anterior", max_length=120, blank=True,
                                        help_text="Indique si es una estimación.")

    class Meta(StopTarget.Meta):
        verbose_name = "parada de itinerario"
        verbose_name_plural = "paradas de itinerarios"


class FavoriteItinerary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="favorite_itineraries")
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "itinerario favorito"
        verbose_name_plural = "itinerarios favoritos"
        constraints = [models.UniqueConstraint(fields=["user", "itinerary"], name="unique_fav_itinerary")]


class CustomTrip(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_trips",
                             verbose_name="usuario")
    name = models.CharField("nombre del recorrido", max_length=150)
    start_date = models.DateField("fecha de inicio", null=True, blank=True)
    end_date = models.DateField("fecha de fin", null=True, blank=True)
    notes = models.TextField("notas", blank=True)
    based_on = models.ForeignKey(Itinerary, null=True, blank=True, on_delete=models.SET_NULL,
                                 verbose_name="basado en")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "recorrido personalizado"
        verbose_name_plural = "recorridos personalizados"

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "La fecha de fin no puede ser anterior a la de inicio."})

    def get_absolute_url(self):
        return reverse("itineraries:trip_detail", args=[self.pk])

    def route_url(self):
        return google_maps_route_url([(s.latitude, s.longitude) for s in self.stops.all()])

    def normalize_order(self):
        for i, stop in enumerate(self.stops.order_by("order", "id"), start=1):
            if stop.order != i:
                CustomTripStop.objects.filter(pk=stop.pk).update(order=i)


class CustomTripStop(StopTarget):
    trip = models.ForeignKey(CustomTrip, on_delete=models.CASCADE, related_name="stops", verbose_name="recorrido")
    visit_date = models.DateField("fecha de visita", null=True, blank=True)

    class Meta(StopTarget.Meta):
        verbose_name = "parada de recorrido personalizado"
        verbose_name_plural = "paradas de recorridos personalizados"
