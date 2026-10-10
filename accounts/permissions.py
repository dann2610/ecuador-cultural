"""Control de acceso por rol y por comunidad asignada (validado siempre en el backend)."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404


def admin_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_platform_admin:
            raise PermissionDenied("Solo el administrador puede acceder a esta sección.")
        return view(request, *args, **kwargs)

    return wrapper


def manager_required(view):
    """Administradores y representantes comunitarios activos."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not (u.is_platform_admin or u.is_representative):
            raise PermissionDenied("Esta sección es solo para representantes comunitarios.")
        return view(request, *args, **kwargs)

    return wrapper


def get_managed_community(user, slug):
    from communities.models import Community

    community = get_object_or_404(Community, slug=slug)
    if not user.can_manage_community(community):
        raise PermissionDenied("No tiene permisos sobre esta comunidad.")
    return community
