from django.contrib.auth.models import AbstractUser
from django.db import models

from core.validators import validate_image_file


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        REPRESENTATIVE = "representative", "Representante comunitario"
        TOURIST = "tourist", "Turista registrado"

    email = models.EmailField("correo electrónico", unique=True)
    role = models.CharField("rol", max_length=20, choices=Role.choices, default=Role.TOURIST, db_index=True)
    phone = models.CharField("teléfono", max_length=20, blank=True)
    bio = models.TextField("sobre mí", blank=True, max_length=600)
    avatar = models.ImageField("foto de perfil", upload_to="avatars/%Y/%m/", blank=True,
                               validators=[validate_image_file])

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    @property
    def is_platform_admin(self):
        return self.is_active and (self.is_superuser or self.role == self.Role.ADMIN)

    @property
    def is_representative(self):
        return self.is_active and self.role == self.Role.REPRESENTATIVE

    def managed_communities(self):
        from communities.models import Community

        if self.is_platform_admin:
            return Community.objects.all()
        if self.is_representative:
            return Community.objects.filter(assignments__user=self, assignments__is_active=True)
        return Community.objects.none()

    def can_manage_community(self, community):
        if not self.is_authenticated or not self.is_active:
            return False
        if self.is_platform_admin:
            return True
        if not self.is_representative or community is None:
            return False
        return community.assignments.filter(user=self, is_active=True).exists()

    def __str__(self):
        return self.get_full_name() or self.username
