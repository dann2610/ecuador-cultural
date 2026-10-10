from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q
from django.urls import reverse
from django.utils.text import slugify
from PIL import Image, ImageOps

from core.models import ReviewableModel
from core.services import google_maps_directions_url
from core.validators import validate_image_file


class Region(models.TextChoices):
    COSTA = "costa", "Costa"
    SIERRA = "sierra", "Sierra"
    AMAZONIA = "amazonia", "Amazonía"
    INSULAR = "insular", "Región Insular (Galápagos)"


class Province(models.Model):
    name = models.CharField("nombre", max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    region = models.CharField("región", max_length=10, choices=Region.choices)

    class Meta:
        ordering = ["name"]
        verbose_name = "provincia"
        verbose_name_plural = "provincias"

    def __str__(self):
        return self.name


class Canton(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cantons",
                                 verbose_name="provincia")
    name = models.CharField("nombre", max_length=80)

    class Meta:
        ordering = ["province__name", "name"]
        verbose_name = "cantón"
        verbose_name_plural = "cantones"
        constraints = [models.UniqueConstraint(fields=["province", "name"], name="unique_canton_per_province")]

    def __str__(self):
        return f"{self.name} ({self.province})"


class Category(models.Model):
    name = models.CharField("nombre", max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    icon = models.CharField("icono Bootstrap", max_length=50, default="bi-stars",
                            help_text="Nombre de icono de Bootstrap Icons, p. ej. bi-palette")
    description = models.CharField("descripción", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("orden", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.name


class Community(ReviewableModel):
    name = models.CharField("nombre", max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="communities",
                                 verbose_name="provincia")
    canton = models.ForeignKey(Canton, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="communities", verbose_name="cantón")
    parish = models.CharField("parroquia", max_length=120, blank=True)
    short_description = models.CharField("descripción breve", max_length=300)
    history = models.TextField("historia documentada", blank=True)
    identity = models.TextField("cultura e identidad local", blank=True)
    clothing = models.TextField("vestimenta tradicional", blank=True)
    music_dance = models.TextField("música y danzas", blank=True)
    activities = models.TextField("actividades turísticas", blank=True)
    latitude = models.DecimalField("latitud", max_digits=9, decimal_places=6, null=True, blank=True,
                                   validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField("longitud", max_digits=9, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_verified = models.BooleanField("ubicación verificada", default=False)
    categories = models.ManyToManyField(Category, blank=True, related_name="communities",
                                        verbose_name="categorías")
    featured_order = models.PositiveSmallIntegerField(
        "posición en el carrusel principal", null=True, blank=True, unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)])

    class Meta:
        ordering = ["name"]
        verbose_name = "comunidad / pueblo"
        verbose_name_plural = "comunidades / pueblos"
        indexes = [models.Index(fields=["status", "province"]), models.Index(fields=["name"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(featured_order__isnull=True) | Q(featured_order__gte=1, featured_order__lte=4),
                name="community_featured_order_1_4"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "pueblo"
            slug, n = base, 2
            while Community.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("communities:detail", args=[self.slug])

    @property
    def region(self):
        return self.province.get_region_display()

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def directions_url(self):
        return google_maps_directions_url(self.latitude, self.longitude) if self.has_location else ""

    def cover_photo(self):
        photos = getattr(self, "prefetched_photos", None)
        if photos is not None:
            for p in photos:
                if p.is_cover:
                    return p
            return photos[0] if photos else None
        return self.photos.order_by("-is_cover", "-is_featured", "order", "id").first()

    def featured_photos(self):
        """Hasta tres fotografías destacadas para las tarjetas (usa prefetch si existe)."""
        photos = getattr(self, "prefetched_photos", None)
        if photos is None:
            photos = list(self.photos.order_by("order", "id"))
        featured = [p for p in photos if p.is_featured][:3]
        if not featured and photos:
            featured = [next((p for p in photos if p.is_cover), photos[0])]
        return featured

    def rating_summary(self):
        from reviews.models import Review

        return Review.objects.visible().filter(community=self).aggregate(avg=Avg("rating"), total=models.Count("id"))


class RepresentativeAssignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments",
                             verbose_name="representante")
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="assignments",
                                  verbose_name="comunidad")
    is_active = models.BooleanField("activa", default=True)
    assigned_at = models.DateTimeField("asignada", auto_now_add=True)

    class Meta:
        verbose_name = "asignación de representante"
        verbose_name_plural = "asignaciones de representantes"
        constraints = [models.UniqueConstraint(fields=["user", "community"], name="unique_rep_assignment")]

    def __str__(self):
        return f"{self.user} → {self.community}"


class CommunityRequest(models.Model):
    """Solicitud de una comunidad para registrarse en la plataforma."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="community_requests", verbose_name="solicitante")
    community_name = models.CharField("nombre de la comunidad", max_length=120)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, verbose_name="provincia")
    canton = models.CharField("cantón", max_length=80, blank=True)
    role_in_community = models.CharField("cargo o vínculo con la comunidad", max_length=120)
    message = models.TextField("presentación de la comunidad", max_length=2000)
    status = models.CharField("estado", max_length=10, choices=Status.choices, default=Status.PENDING,
                              db_index=True)
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.SET_NULL,
                                  verbose_name="comunidad creada")
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "solicitud de comunidad"
        verbose_name_plural = "solicitudes de comunidades"

    def __str__(self):
        return f"{self.community_name} ({self.get_status_display()})"


def photo_upload_to(instance, filename):
    ext = Path(filename).suffix.lower() or ".jpg"
    folder = instance.community.slug if instance.community_id else "general"
    return f"photos/{folder}/{slugify(Path(filename).stem)[:60] or 'foto'}{ext}"


class Photo(models.Model):
    class Kind(models.TextChoices):
        LANDSCAPE = "landscape", "Paisaje"
        CULTURE = "culture", "Cultura y tradiciones"
        FOOD = "food", "Gastronomía"
        CRAFT = "craft", "Artesanías"
        HERITAGE = "heritage", "Patrimonio"
        NATURE = "nature", "Naturaleza"
        OTHER = "other", "Otra"

    MAX_FEATURED = 3
    CARD_WIDTH = 720
    MAX_WIDTH = 1920

    image = models.ImageField("archivo", upload_to=photo_upload_to, validators=[validate_image_file])
    card_image = models.ImageField("versión para tarjetas", upload_to="photos/cards/", blank=True, editable=False)
    title = models.CharField("título", max_length=150)
    description = models.CharField("descripción", max_length=400, blank=True)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="photos",
                                  verbose_name="comunidad", null=True, blank=True)
    place = models.ForeignKey("tourism.Place", on_delete=models.CASCADE, related_name="photos",
                              verbose_name="lugar", null=True, blank=True)
    kind = models.CharField("categoría", max_length=12, choices=Kind.choices, default=Kind.LANDSCAPE)
    alt_text = models.CharField("texto alternativo", max_length=200)
    source = models.CharField("fuente", max_length=300, blank=True)
    author = models.CharField("autor o entidad responsable", max_length=150)
    license = models.CharField("licencia o permiso de uso", max_length=150)
    is_featured = models.BooleanField("destacada en tarjetas", default=False)
    is_cover = models.BooleanField("portada", default=False)
    is_placeholder = models.BooleanField("marcador de demostración", default=False)
    order = models.PositiveSmallIntegerField("orden", default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="subida por")
    uploaded_at = models.DateTimeField("fecha de carga", auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "fotografía"
        verbose_name_plural = "fotografías"
        constraints = [
            models.CheckConstraint(condition=Q(community__isnull=False) | Q(place__isnull=False),
                                   name="photo_has_owner"),
        ]

    def __str__(self):
        return self.title

    @property
    def card_url(self):
        if self.card_image:
            return self.card_image.url
        return self.image.url if self.image else ""

    def save(self, *args, **kwargs):
        if self.place_id and not self.community_id:
            self.community_id = self.place.community_id
        new_file = self.image and not getattr(self.image, "_committed", True)
        if new_file:
            self._optimize()
        super().save(*args, **kwargs)
        if self.is_cover and self.community_id:
            Photo.objects.filter(community_id=self.community_id, place__isnull=True, is_cover=True).exclude(
                pk=self.pk).update(is_cover=False)

    def _optimize(self):
        """Reduce la imagen original y genera una versión liviana para tarjetas."""
        try:
            self.image.seek(0)
            img = ImageOps.exif_transpose(Image.open(self.image))
            img = img.convert("RGB")
        except Exception:
            return
        stem = Path(self.image.name).stem
        if img.width > self.MAX_WIDTH:
            img.thumbnail((self.MAX_WIDTH, self.MAX_WIDTH * 2))
        buf = BytesIO()
        img.save(buf, "JPEG", quality=85, optimize=True, progressive=True)
        self.image.save(f"{stem}.jpg", ContentFile(buf.getvalue()), save=False)
        card = img.copy()
        card.thumbnail((self.CARD_WIDTH, self.CARD_WIDTH))
        buf = BytesIO()
        card.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
        self.card_image.save(f"{stem}-card.jpg", ContentFile(buf.getvalue()), save=False)


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites",
                             verbose_name="usuario")
    community = models.ForeignKey(Community, null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="favorited_by", verbose_name="comunidad")
    place = models.ForeignKey("tourism.Place", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="favorited_by", verbose_name="lugar")
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "favorito"
        verbose_name_plural = "favoritos"
        constraints = [
            models.UniqueConstraint(fields=["user", "community"], condition=Q(community__isnull=False),
                                    name="unique_fav_community"),
            models.UniqueConstraint(fields=["user", "place"], condition=Q(place__isnull=False),
                                    name="unique_fav_place"),
            models.CheckConstraint(
                condition=(Q(community__isnull=False, place__isnull=True) | Q(community__isnull=True,
                                                                              place__isnull=False)),
                name="favorite_single_target"),
        ]

    def __str__(self):
        return f"{self.user} ♥ {self.community or self.place}"
