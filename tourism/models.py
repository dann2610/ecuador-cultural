from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.text import slugify

from communities.models import Community
from core.models import ReviewableModel
from core.services import google_maps_directions_url


class Place(ReviewableModel):
    class Kind(models.TextChoices):
        ATTRACTION = "attraction", "Atractivo turístico"
        CHURCH = "church", "Iglesia"
        CEMETERY = "cemetery", "Cementerio patrimonial"
        MUSEUM = "museum", "Museo"
        HISTORIC = "historic", "Sitio histórico"
        PARK = "park", "Parque o espacio natural"
        WATERFALL = "waterfall", "Cascada"
        VIEWPOINT = "viewpoint", "Mirador"
        RESTAURANT = "restaurant", "Restaurante"
        LODGING = "lodging", "Hospedaje"
        MARKET = "market", "Mercado o plaza artesanal"

    HERITAGE_KINDS = {Kind.CHURCH, Kind.CEMETERY, Kind.MUSEUM, Kind.HISTORIC}
    NATURE_KINDS = {Kind.PARK, Kind.WATERFALL, Kind.VIEWPOINT}
    SERVICE_KINDS = {Kind.RESTAURANT, Kind.LODGING}

    ICONS = {
        "attraction": "bi-star", "church": "bi-bank2", "cemetery": "bi-flower1", "museum": "bi-building",
        "historic": "bi-hourglass-split", "park": "bi-tree", "waterfall": "bi-droplet", "viewpoint": "bi-binoculars",
        "restaurant": "bi-cup-hot", "lodging": "bi-house-door", "market": "bi-shop",
    }

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="places",
                                  verbose_name="comunidad")
    name = models.CharField("nombre", max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    kind = models.CharField("tipo", max_length=12, choices=Kind.choices, default=Kind.ATTRACTION, db_index=True)
    description = models.TextField("descripción")
    heritage_features = models.TextField("características patrimoniales", blank=True)
    visiting_rules = models.TextField("normas de visita", blank=True)
    address = models.CharField("dirección o referencia", max_length=250, blank=True)
    opening_hours = models.CharField("horario (si está confirmado)", max_length=200, blank=True)
    latitude = models.DecimalField("latitud", max_digits=9, decimal_places=6, null=True, blank=True,
                                   validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField("longitud", max_digits=9, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_verified = models.BooleanField("ubicación verificada", default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "lugar turístico"
        verbose_name_plural = "lugares turísticos"
        indexes = [models.Index(fields=["status", "kind"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or "lugar"
            slug, n = base, 2
            while Place.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("tourism:place_detail", args=[self.slug])

    @property
    def icon(self):
        return self.ICONS.get(self.kind, "bi-geo-alt")

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def directions_url(self):
        return google_maps_directions_url(self.latitude, self.longitude) if self.has_location else ""

    def rating_summary(self):
        from reviews.models import Review

        return Review.objects.visible().filter(place=self).aggregate(avg=Avg("rating"), total=Count("id"))


class TouristService(ReviewableModel):
    class Kind(models.TextChoices):
        GUIDE = "guide", "Guianza local"
        TRANSPORT = "transport", "Transporte"
        TOUR = "tour", "Operador de turismo comunitario"
        WORKSHOP = "workshop", "Taller o experiencia"
        OTHER = "other", "Otro"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="services",
                                  verbose_name="comunidad")
    name = models.CharField("nombre", max_length=150)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.OTHER)
    description = models.TextField("descripción")
    contact = models.CharField("contacto público", max_length=200, blank=True,
                               help_text="Solo datos autorizados para publicación.")
    price_note = models.CharField("referencia de precio (si está confirmada)", max_length=150, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "servicio turístico"
        verbose_name_plural = "servicios turísticos"

    def __str__(self):
        return self.name
