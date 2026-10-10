"""Servicios compartidos: auditoría, notificaciones y enlaces de Google Maps."""
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib.auth import get_user_model

from .models import AuditLog, Notification


def log_action(actor, action, obj, detail=""):
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        model_label=obj._meta.label,
        object_id=str(obj.pk),
        object_repr=str(obj)[:200],
        detail=detail[:2000],
    )


def notify(user, message, url=""):
    if user is not None:
        Notification.objects.create(user=user, message=message[:300], url=url[:300])


def notify_admins(message, url=""):
    User = get_user_model()
    admins = User.objects.filter(is_active=True).filter(role=User.Role.ADMIN) | User.objects.filter(
        is_active=True, is_superuser=True)
    Notification.objects.bulk_create(
        [Notification(user=u, message=message[:300], url=url[:300]) for u in admins.distinct()]
    )


def _valid_coord(lat, lng):
    try:
        lat, lng = Decimal(str(lat)), Decimal(str(lng))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not (Decimal(-90) <= lat <= Decimal(90) and Decimal(-180) <= lng <= Decimal(180)):
        return None
    return f"{lat:.6f},{lng:.6f}"


def google_maps_directions_url(lat, lng):
    """Enlace oficial de Google Maps (api=1) con coordenadas validadas y codificadas."""
    dest = _valid_coord(lat, lng)
    if dest is None:
        return ""
    return "https://www.google.com/maps/dir/?" + urlencode({"api": 1, "destination": dest})


def google_maps_route_url(points):
    """Ruta con varias paradas: origen opcional, destino = última parada, intermedias como waypoints."""
    coords = [c for c in (_valid_coord(lat, lng) for lat, lng in points) if c]
    if not coords:
        return ""
    params = {"api": 1, "destination": coords[-1], "travelmode": "driving"}
    if len(coords) > 1:
        params["origin"] = coords[0]
        if len(coords) > 2:
            params["waypoints"] = "|".join(coords[1:-1][:9])
    return "https://www.google.com/maps/dir/?" + urlencode(params)
