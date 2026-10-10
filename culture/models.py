from django.db import models
from django.urls import reverse

from communities.models import Category, Community
from core.models import ReviewableModel
from core.validators import validate_image_file


class CulturalContent(ReviewableModel):
    class Kind(models.TextChoices):
        HISTORY = "history", "Historia"
        IDENTITY = "identity", "Cultura e identidad"
        TRADITION = "tradition", "Tradiciones y costumbres"
        CLOTHING = "clothing", "Vestimenta tradicional"
        MUSIC = "music", "Música y danzas"
        OTHER = "other", "Otro"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="cultural_contents",
                                  verbose_name="comunidad")
    kind = models.CharField("tipo", max_length=12, choices=Kind.choices, default=Kind.TRADITION, db_index=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL,
                                 verbose_name="categoría")
    title = models.CharField("título", max_length=160)
    description = models.TextField("descripción")
    photo = models.ForeignKey("communities.Photo", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+", verbose_name="fotografía")

    class Meta:
        ordering = ["kind", "title"]
        verbose_name = "contenido cultural"
        verbose_name_plural = "contenidos culturales"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("communities:detail", args=[self.community.slug]) + "#cultura"


class Dish(ReviewableModel):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="dishes",
                                  verbose_name="comunidad de origen")
    name = models.CharField("nombre", max_length=120)
    description = models.TextField("descripción")
    ingredients = models.TextField("ingredientes documentados", blank=True)
    cultural_context = models.TextField("contexto cultural", blank=True)
    image = models.ImageField("fotografía", upload_to="dishes/", blank=True, validators=[validate_image_file])
    image_credit = models.CharField("crédito y licencia de la fotografía", max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "plato típico"
        verbose_name_plural = "gastronomía"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("communities:detail", args=[self.community.slug]) + "#gastronomia"


class Craft(ReviewableModel):
    class Kind(models.TextChoices):
        TEXTILE = "textile", "Tejidos"
        CERAMIC = "ceramic", "Cerámica"
        HAT = "hat", "Sombreros"
        CARVING = "carving", "Tallados"
        JEWELRY = "jewelry", "Joyería y bisutería"
        OTHER = "other", "Otra expresión artesanal"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="crafts",
                                  verbose_name="comunidad de origen")
    name = models.CharField("nombre", max_length=120)
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices, default=Kind.OTHER)
    description = models.TextField("descripción")
    materials = models.TextField("materiales", blank=True)
    technique = models.TextField("técnicas", blank=True)
    cultural_meaning = models.TextField("significado cultural documentado", blank=True)
    image = models.ImageField("fotografía", upload_to="crafts/", blank=True, validators=[validate_image_file])
    image_credit = models.CharField("crédito y licencia de la fotografía", max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "artesanía"
        verbose_name_plural = "artesanías"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("communities:detail", args=[self.community.slug]) + "#artesanias"


class Festivity(ReviewableModel):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="festivities",
                                  verbose_name="comunidad")
    name = models.CharField("nombre", max_length=140)
    description = models.TextField("descripción")
    period = models.CharField("fecha o período de celebración", max_length=120, blank=True)
    location = models.CharField("ubicación", max_length=200, blank=True)
    history = models.TextField("historia", blank=True)
    visitor_tips = models.TextField("recomendaciones para visitantes", blank=True,
                                    help_text="Incluya normas de respeto en ceremonias y espacios sagrados.")
    image = models.ImageField("fotografía", upload_to="festivities/", blank=True,
                              validators=[validate_image_file])
    image_credit = models.CharField("crédito y licencia de la fotografía", max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "festividad"
        verbose_name_plural = "tradiciones y festividades"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("communities:detail", args=[self.community.slug]) + "#festividades"
