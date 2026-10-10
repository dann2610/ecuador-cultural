from django.conf import settings
from django.db import models
from django.utils import timezone


class ReviewStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    PENDING = "pending", "Pendiente de revisión"
    PUBLISHED = "published", "Publicado"
    REJECTED = "rejected", "Rechazado"


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=ReviewStatus.PUBLISHED)


class ReviewableModel(models.Model):
    """Campos comunes para todo contenido que pasa por revisión editorial."""

    status = models.CharField("estado de revisión", max_length=12, choices=ReviewStatus.choices,
                              default=ReviewStatus.DRAFT, db_index=True)
    source = models.CharField("fuente bibliográfica o URL", max_length=500, blank=True)
    author_entity = models.CharField("autor o entidad responsable", max_length=200, blank=True)
    is_demo = models.BooleanField("dato de demostración (no verificado)", default=False)
    review_notes = models.TextField("observaciones de revisión", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+", verbose_name="creado por")
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)
    published_at = models.DateTimeField("publicado", null=True, blank=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_published(self):
        return self.status == ReviewStatus.PUBLISHED

    def mark_published(self):
        self.status = ReviewStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="notifications", verbose_name="usuario")
    message = models.CharField("mensaje", max_length=300)
    url = models.CharField("enlace", max_length=300, blank=True)
    is_read = models.BooleanField("leída", default=False, db_index=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return self.message


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="audit_entries", verbose_name="usuario")
    action = models.CharField("acción", max_length=40, db_index=True)
    model_label = models.CharField("modelo", max_length=80)
    object_id = models.CharField("id del objeto", max_length=40)
    object_repr = models.CharField("objeto", max_length=200)
    detail = models.TextField("detalle", blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "historial de moderación y auditoría"

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.object_repr}"
