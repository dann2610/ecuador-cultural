"""Datos mínimos para pruebas (se crean en la base de datos de prueba de PostgreSQL)."""
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from accounts.models import User
from communities.models import Category, Community, Province, RepresentativeAssignment
from core.models import ReviewStatus
from donations.models import Project
from tourism.models import Place


def image_file(name="foto.jpg", color=(30, 120, 60), size=(900, 600)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def user(username, role=User.Role.TOURIST, **kw):
    return User.objects.create_user(username=username, email=f"{username}@test.ec", password="Clave-Segura-2026",
                                    role=role, **kw)


def province(name="Imbabura", region="sierra"):
    return Province.objects.get_or_create(slug=name.lower(), defaults={"name": name, "region": region})[0]


def community(name="Otavalo", prov=None, published=True, lat="0.234300", lng="-78.261100", **kw):
    return Community.objects.create(
        name=name, province=prov or province(), short_description=f"Descripción de {name}",
        status=ReviewStatus.PUBLISHED if published else ReviewStatus.DRAFT,
        published_at=timezone.now() if published else None, latitude=lat, longitude=lng, **kw)


def place(comm, name="Cascada de prueba", kind=Place.Kind.WATERFALL, lat="0.244800", lng="-78.238400"):
    return Place.objects.create(community=comm, name=name, kind=kind, description="Descripción",
                                status=ReviewStatus.PUBLISHED, latitude=lat, longitude=lng)


def project(comm, name="Proyecto de prueba", goal="1000.00"):
    return Project.objects.create(community=comm, name=name, description="d", objective="o",
                                  goal_amount=Decimal(goal), start_date=date.today(), responsible_name="Resp",
                                  status=ReviewStatus.PUBLISHED)


def assign(rep, comm):
    return RepresentativeAssignment.objects.create(user=rep, community=comm)


def category(name="Artesanías"):
    return Category.objects.get_or_create(slug=name.lower(), defaults={"name": name})[0]
