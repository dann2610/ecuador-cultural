"""Consultas reutilizables (capa de lógica de negocio sobre el ORM)."""
from django.db.models import Avg, Prefetch, Q

from .models import Community, Photo


def photo_prefetch():
    return Prefetch("photos", queryset=Photo.objects.order_by("order", "id"), to_attr="prefetched_photos")


def published_communities():
    return (Community.objects.published()
            .select_related("province", "canton")
            .prefetch_related("categories", photo_prefetch()))


def filter_communities(qs, data):
    q = (data.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(canton__name__icontains=q)
                       | Q(parish__icontains=q))
    if data.get("province"):
        qs = qs.filter(province=data["province"])
    if data.get("canton"):
        qs = qs.filter(canton=data["canton"])
    if data.get("category"):
        qs = qs.filter(categories=data["category"])
    order = data.get("order") or "name"
    if order == "-name":
        qs = qs.order_by("-name")
    elif order == "recent":
        qs = qs.order_by("-published_at", "-created_at")
    elif order == "rating":
        qs = qs.annotate(avg_rating=Avg("reviews__rating", filter=Q(reviews__status="published"))).order_by(
            "-avg_rating", "name")
    else:
        qs = qs.order_by("name")
    return qs.distinct()


def carousel_slides():
    """Cuatro destinos para el carrusel: elegidos por el administrador y, si faltan,
    completados con destinos de demostración claramente identificados. Nunca repite fotografías."""
    chosen = list(published_communities().filter(featured_order__isnull=False).order_by("featured_order"))
    if len(chosen) < 4:
        extra = (published_communities().exclude(pk__in=[c.pk for c in chosen])
                 .order_by("-is_demo", "name")[: 4 - len(chosen)])
        for c in extra:
            c.carousel_filler = True
        chosen += list(extra)
    slides, used = [], set()
    for c in chosen[:4]:
        photos = getattr(c, "prefetched_photos", [])
        ordered = sorted(photos, key=lambda p: (not p.is_cover, not p.is_featured, p.order, p.id))
        photo = next((p for p in ordered if p.image.name not in used), None)
        if photo:
            used.add(photo.image.name)
        slides.append({"community": c, "photo": photo, "is_demo": c.is_demo or getattr(c, "carousel_filler", False)})
    return slides
