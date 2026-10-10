from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils.text import slugify

from communities.models import Community
from core.models import ReviewableModel
from core.validators import validate_document_file, validate_image_file


class Project(ReviewableModel):
    """Proyecto comunitario. `status` (heredado) controla la publicación; `phase` el avance."""

    class Phase(models.TextChoices):
        FUNDRAISING = "fundraising", "Recaudando apoyo"
        IN_PROGRESS = "in_progress", "En ejecución"
        COMPLETED = "completed", "Finalizado"
        CANCELLED = "cancelled", "Cancelado"

    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="projects",
                                  verbose_name="comunidad beneficiaria")
    name = models.CharField("nombre", max_length=150)
    slug = models.SlugField(max_length=170, unique=True)
    description = models.TextField("descripción")
    objective = models.TextField("objetivo")
    goal_amount = models.DecimalField("monto objetivo (USD)", max_digits=10, decimal_places=2,
                                      validators=[MinValueValidator(Decimal("1.00"))])
    start_date = models.DateField("fecha de inicio")
    deadline = models.DateField("fecha límite", null=True, blank=True)
    image = models.ImageField("fotografía", upload_to="projects/", blank=True, validators=[validate_image_file])
    image_credit = models.CharField("crédito de la fotografía", max_length=200, blank=True)
    phase = models.CharField("estado del proyecto", max_length=12, choices=Phase.choices,
                             default=Phase.FUNDRAISING, db_index=True)
    responsible_name = models.CharField("responsable", max_length=150)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="managed_projects", verbose_name="usuario responsable")
    payment_instructions = models.TextField(
        "instrucciones para aportar", blank=True,
        help_text="Cuenta oficial de la comunidad u otro medio verificado por el administrador. "
                  "Solo se muestran cuando el proyecto está publicado.")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "proyecto comunitario"
        verbose_name_plural = "proyectos comunitarios"
        constraints = [
            models.CheckConstraint(condition=Q(deadline__isnull=True) | Q(deadline__gte=models.F("start_date")),
                                   name="project_deadline_after_start"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or "proyecto"
            slug, n = base, 2
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("donations:project_detail", args=[self.slug])

    @property
    def confirmed_amount(self):
        """Calculado desde las donaciones confirmadas: nunca se almacena por separado."""
        if hasattr(self, "confirmed_total"):
            return self.confirmed_total or Decimal("0")
        return self.donations.filter(status=Donation.Status.CONFIRMED).aggregate(
            t=Sum("amount"))["t"] or Decimal("0")

    @property
    def progress_percent(self):
        if not self.goal_amount:
            return 0
        return min(100, int(self.confirmed_amount * 100 / self.goal_amount))

    @property
    def accepts_donations(self):
        return self.is_published and self.phase in {self.Phase.FUNDRAISING, self.Phase.IN_PROGRESS}


class ProjectUpdate(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="updates",
                                verbose_name="proyecto")
    title = models.CharField("título", max_length=150)
    description = models.TextField("descripción del avance")
    evidence = models.ImageField("evidencia fotográfica", upload_to="project_updates/", blank=True,
                                 validators=[validate_image_file])
    date = models.DateField("fecha del avance")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "avance de proyecto"
        verbose_name_plural = "avances de proyectos"

    def __str__(self):
        return self.title


class Donation(models.Model):
    """Registro de aporte. Esta versión no procesa pagos: un aporte solo se confirma manualmente
    por un administrador cuando existe una evidencia verificable."""

    class Status(models.TextChoices):
        PLEDGED = "pledged", "Compromiso registrado"
        UNDER_REVIEW = "under_review", "Comprobante en verificación"
        CONFIRMED = "confirmed", "Confirmada"
        REJECTED = "rejected", "No verificada"
        CANCELLED = "cancelled", "Cancelada"

    class Method(models.TextChoices):
        TRANSFER = "transfer", "Transferencia bancaria"
        DEPOSIT = "deposit", "Depósito"
        IN_PERSON = "in_person", "Entrega directa en la comunidad"
        GATEWAY = "gateway", "Pasarela de pagos (próximamente)"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="donations",
                                verbose_name="proyecto")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="donations", verbose_name="usuario")
    donor_name = models.CharField("nombre del donante (opcional)", max_length=150, blank=True)
    is_anonymous = models.BooleanField("mostrar como anónimo", default=True)
    amount = models.DecimalField("monto (USD)", max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal("1.00"))])
    method = models.CharField("método de pago", max_length=10, choices=Method.choices, default=Method.TRANSFER)
    transaction_reference = models.CharField("referencia de transacción", max_length=80, blank=True,
                                             help_text="Número de comprobante. Nunca ingrese datos de tarjetas.")
    receipt = models.FileField("comprobante", upload_to="receipts/%Y/%m/", blank=True,
                               validators=[validate_document_file])
    status = models.CharField("estado", max_length=12, choices=Status.choices, default=Status.PLEDGED,
                              db_index=True)
    gateway_payload_id = models.CharField("id externo de pasarela", max_length=120, blank=True,
                                          help_text="Reservado para una futura integración de pagos.")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="verificada por")
    verified_at = models.DateTimeField("fecha de verificación", null=True, blank=True)
    admin_note = models.CharField("nota interna", max_length=300, blank=True)
    created_at = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "donación"
        verbose_name_plural = "donaciones"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=1), name="donation_min_amount"),
            models.CheckConstraint(
                condition=~Q(status="confirmed") | Q(verified_by__isnull=False, verified_at__isnull=False),
                name="donation_confirmed_requires_verification"),
        ]

    def __str__(self):
        return f"${self.amount} → {self.project} ({self.get_status_display()})"

    @property
    def public_name(self):
        if self.is_anonymous or not self.donor_name:
            return "Aporte anónimo"
        return self.donor_name
