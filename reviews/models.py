from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.validators import validate_image_file


class ReviewQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(status=Review.Status.PUBLISHED)


class Review(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = "published", "Publicada"
        PENDING = "pending", "En revisión"
        HIDDEN = "hidden", "Oculta por moderación"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews",
                             verbose_name="usuario")
    community = models.ForeignKey("communities.Community", null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="reviews", verbose_name="pueblo")
    place = models.ForeignKey("tourism.Place", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="reviews", verbose_name="lugar")
    rating = models.PositiveSmallIntegerField("puntuación", validators=[MinValueValidator(1),
                                                                       MaxValueValidator(5)])
    comment = models.TextField("comentario", max_length=2000)
    photo = models.ImageField("fotografía (opcional)", upload_to="reviews/%Y/%m/", blank=True,
                              validators=[validate_image_file])
    status = models.CharField("estado de moderación", max_length=10, choices=Status.choices,
                              default=Status.PUBLISHED, db_index=True)
    moderation_note = models.CharField("nota de moderación", max_length=300, blank=True)
    created_at = models.DateTimeField("fecha de publicación", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "reseña"
        verbose_name_plural = "reseñas"
        constraints = [
            models.CheckConstraint(
                condition=(Q(community__isnull=False, place__isnull=True) | Q(community__isnull=True,
                                                                              place__isnull=False)),
                name="review_single_target"),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"),
            models.UniqueConstraint(fields=["user", "community"], condition=Q(community__isnull=False),
                                    name="one_review_per_user_community"),
            models.UniqueConstraint(fields=["user", "place"], condition=Q(place__isnull=False),
                                    name="one_review_per_user_place"),
        ]

    def __str__(self):
        return f"{self.rating}★ {self.target} — {self.user}"

    @property
    def target(self):
        return self.community or self.place

    def get_absolute_url(self):
        return self.target.get_absolute_url() + "#resenas"
