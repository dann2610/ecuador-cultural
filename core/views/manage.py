"""Panel del representante comunitario y gestión de contenidos por comunidad."""
import inspect

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import get_managed_community, manager_required
from communities.forms import CommunityForm
from communities.models import Photo
from donations.models import Donation, Project
from itineraries.models import Itinerary

from ..managed import MANAGED, MODERATED, display_name
from ..models import ReviewableModel, ReviewStatus
from ..services import log_action, notify_admins


@manager_required
def rep_dashboard(request):
    communities = (request.user.managed_communities().select_related("province")
                   .annotate(n_photos=Count("photos", distinct=True), n_places=Count("places", distinct=True)))
    ids = list(communities.values_list("id", flat=True))
    pending = []
    for key, model in MODERATED.items():
        field = "pk" if key == "comunidad" else "community"
        if key == "itinerario":
            qs = model.objects.filter(community__in=ids)
        else:
            qs = model.objects.filter(**{f"{field}__in": ids})
        for obj in qs.exclude(status=ReviewStatus.PUBLISHED):
            pending.append({"obj": obj, "label": model._meta.verbose_name, "name": display_name(obj)})
    projects = (Project.objects.filter(community__in=ids).select_related("community")
                .annotate(confirmed_total=Sum("donations__amount", filter=Q(donations__status=Donation.Status.CONFIRMED)),
                          n_confirmed=Count("donations", filter=Q(donations__status=Donation.Status.CONFIRMED))))
    return render(request, "core/manage/rep_dashboard.html", {
        "communities": communities, "pending": pending, "projects": projects,
        "itineraries": Itinerary.objects.filter(community__in=ids),
    })


@manager_required
def manage_community(request, slug):
    community = get_managed_community(request.user, slug)
    sections = []
    for key, (model, _form, singular, plural) in MANAGED.items():
        if key == "foto":
            continue
        sections.append({"key": key, "singular": singular, "plural": plural,
                         "items": model.objects.filter(community=community).order_by("-updated_at")})
    return render(request, "core/manage/community.html", {
        "c": community, "sections": sections,
        "photos": community.photos.select_related("place").order_by("order", "id"),
        "assignments": community.assignments.select_related("user"),
        "itineraries": Itinerary.objects.filter(community=community),
    })


@manager_required
def edit_community(request, slug):
    community = get_managed_community(request.user, slug)
    form = CommunityForm(request.POST or None, instance=community, user=request.user)
    if request.method == "POST" and form.is_valid():
        c = form.save()
        log_action(request.user, "comunidad_editada", c, ", ".join(form.changed_data))
        if not request.user.is_platform_admin and c.is_published:
            notify_admins(f"{request.user} actualizó la información publicada de {c.name}",
                          reverse("core:manage_community", args=[c.slug]))
        messages.success(request, "Información de la comunidad guardada.")
        return redirect("core:manage_community", slug=c.slug)
    return render(request, "core/manage/community_form.html", {"form": form, "community": community})


@manager_required
@require_POST
def community_status(request, slug):
    community = get_managed_community(request.user, slug)
    action = request.POST.get("action")
    if request.user.is_platform_admin and action == "publish":
        community.mark_published()
    elif action == "submit" and community.status in {ReviewStatus.DRAFT, ReviewStatus.REJECTED}:
        community.status = ReviewStatus.PENDING
        notify_admins(f"{community.name} fue enviada a revisión", reverse("core:admin_moderation"))
    else:
        raise PermissionDenied
    community.save()
    log_action(request.user, f"comunidad_{action}", community)
    messages.success(request, f"{community.name}: {community.get_status_display()}.")
    return redirect("core:manage_community", slug=slug)


def _form_kwargs(form_class, community, user):
    params = inspect.signature(form_class.__init__).parameters
    kw = {}
    if "community" in params:
        kw["community"] = community
    if "user" in params:
        kw["user"] = user
    return kw


def _apply_status(obj, user, action, is_new):
    """Reglas editoriales: el representante propone (borrador/pendiente), el administrador publica."""
    if not isinstance(obj, ReviewableModel):
        return
    if user.is_platform_admin:
        if action == "publish":
            obj.mark_published()
        elif action == "draft":
            obj.status = ReviewStatus.DRAFT
    elif is_new or not obj.is_published:
        obj.status = ReviewStatus.PENDING if action == "submit" else ReviewStatus.DRAFT


@manager_required
def item_form(request, slug, kind, pk=None):
    community = get_managed_community(request.user, slug)
    if kind not in MANAGED:
        raise Http404
    model, form_class, singular, _plural = MANAGED[kind]
    instance = get_object_or_404(model, pk=pk, community=community) if pk else model(community=community)
    form = form_class(request.POST or None, request.FILES or None, instance=instance,
                      **_form_kwargs(form_class, community, request.user))
    if request.method == "POST" and form.is_valid():
        is_new = instance.pk is None
        with transaction.atomic():
            obj = form.save(commit=False)
            obj.community = community
            if is_new and hasattr(obj, "created_by"):
                obj.created_by = request.user
            if isinstance(obj, Photo) and is_new:
                obj.uploaded_by = request.user
            if isinstance(obj, Project) and is_new:
                obj.responsible = request.user
            _apply_status(obj, request.user, request.POST.get("action", "draft"), is_new)
            obj.save()
            form.save_m2m()
        log_action(request.user, f"{kind}_{'creado' if is_new else 'editado'}", obj)
        if isinstance(obj, ReviewableModel):
            if obj.status == ReviewStatus.PENDING:
                notify_admins(f"Pendiente de revisión: {singular} «{display_name(obj)}» ({community.name})",
                              reverse("core:admin_moderation"))
            elif obj.is_published and not request.user.is_platform_admin:
                notify_admins(f"{request.user} actualizó {singular} publicado «{display_name(obj)}»",
                              reverse("core:manage_community", args=[slug]))
        messages.success(request, f"{singular.capitalize()} guardado"
                         + (f" ({obj.get_status_display()})." if isinstance(obj, ReviewableModel) else "."))
        return redirect(reverse("core:manage_community", args=[slug]) + f"#{kind}")
    return render(request, "core/manage/item_form.html", {
        "form": form, "community": community, "kind": kind, "singular": singular, "instance": instance,
        "reviewable": issubclass(model, ReviewableModel),
    })


@manager_required
@require_POST
def item_delete(request, slug, kind, pk):
    community = get_managed_community(request.user, slug)
    if kind not in MANAGED:
        raise Http404
    model = MANAGED[kind][0]
    obj = get_object_or_404(model, pk=pk, community=community)
    if isinstance(obj, Project) and obj.donations.exists():
        messages.error(request, "No se puede eliminar un proyecto con aportes registrados. Cámbialo a «Cancelado».")
        return redirect("core:manage_community", slug=slug)
    log_action(request.user, f"{kind}_eliminado", obj)
    if isinstance(obj, Photo):
        obj.image.delete(save=False)
        if obj.card_image:
            obj.card_image.delete(save=False)
    obj.delete()
    messages.success(request, "Elemento eliminado.")
    return redirect(reverse("core:manage_community", args=[slug]) + f"#{kind}")


@manager_required
@require_POST
def photo_move(request, slug, pk, direction):
    community = get_managed_community(request.user, slug)
    photos = list(community.photos.order_by("order", "id"))
    idx = next((i for i, p in enumerate(photos) if p.pk == pk), None)
    if idx is None or direction not in {"subir", "bajar"}:
        raise Http404
    swap = idx - 1 if direction == "subir" else idx + 1
    if 0 <= swap < len(photos):
        photos[idx], photos[swap] = photos[swap], photos[idx]
    with transaction.atomic():
        for i, p in enumerate(photos, start=1):
            if p.order != i:
                Photo.objects.filter(pk=p.pk).update(order=i)
    return redirect(reverse("core:manage_community", args=[slug]) + "#foto")


@manager_required
@require_POST
def photo_flag(request, slug, pk, flag):
    community = get_managed_community(request.user, slug)
    photo = get_object_or_404(Photo, pk=pk, community=community)
    if flag == "destacada":
        if not photo.is_featured and community.photos.filter(is_featured=True).count() >= Photo.MAX_FEATURED:
            messages.error(request, "Ya hay 3 fotografías destacadas. Quita una antes de agregar otra.")
        else:
            photo.is_featured = not photo.is_featured
            photo.save(update_fields=["is_featured"])
    elif flag == "portada":
        photo.is_cover = True
        photo.save()
    else:
        raise Http404
    return redirect(reverse("core:manage_community", args=[slug]) + "#foto")
