"""Panel del administrador general."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import admin_required
from communities.forms import CommunityForm, FeaturedCarouselForm
from communities.models import Canton, Community, CommunityRequest, RepresentativeAssignment
from donations.models import Donation, Project
from itineraries.models import Itinerary
from reviews.models import Review
from tourism.models import Place

from ..managed import MODERATED, display_name
from ..models import AuditLog, ReviewStatus
from ..services import log_action, notify

User = get_user_model()


@admin_required
def dashboard(request):
    pending_total = sum(m.objects.filter(status=ReviewStatus.PENDING).count() for m in MODERATED.values())
    published_content = sum(m.objects.published().count() for k, m in MODERATED.items()
                            if k not in {"comunidad", "proyecto", "itinerario"})
    kpis = [
        ("Comunidades", Community.objects.count(), "bi-people", "communities:list"),
        ("Lugares turísticos", Place.objects.count(), "bi-geo-alt", "tourism:map"),
        ("Contenidos publicados", published_content, "bi-journal-check", None),
        ("Pendientes de revisión", pending_total, "bi-hourglass-split", "core:admin_moderation"),
        ("Itinerarios publicados", Itinerary.objects.published().count(), "bi-signpost-split", "itineraries:list"),
        ("Reseñas registradas", Review.objects.count(), "bi-star", "core:admin_reviews"),
        ("Proyectos activos", Project.objects.published().filter(
            phase__in=[Project.Phase.FUNDRAISING, Project.Phase.IN_PROGRESS]).count(), "bi-heart", "donations:project_list"),
        ("Donaciones confirmadas", Donation.objects.filter(status=Donation.Status.CONFIRMED).count(),
         "bi-cash-coin", "core:admin_donations"),
    ]
    confirmed_sum = Donation.objects.filter(status=Donation.Status.CONFIRMED).aggregate(s=Sum("amount"))["s"] or 0
    return render(request, "core/admin/dashboard.html", {
        "kpis": kpis, "confirmed_sum": confirmed_sum,
        "to_verify": Donation.objects.filter(status__in=[Donation.Status.PLEDGED, Donation.Status.UNDER_REVIEW]).count(),
        "requests": CommunityRequest.objects.filter(status=CommunityRequest.Status.PENDING).count(),
        "audit": AuditLog.objects.select_related("actor")[:12],
        "communities": Community.objects.select_related("province").annotate(
            reps=Count("assignments", filter=Q(assignments__is_active=True))).order_by("name")[:50],
    })


@admin_required
def moderation(request):
    queue = []
    for key, model in MODERATED.items():
        qs = model.objects.filter(status=ReviewStatus.PENDING).select_related("created_by")
        for obj in qs:
            community = obj if isinstance(obj, Community) else getattr(obj, "community", None)
            queue.append({"key": key, "obj": obj, "label": model._meta.verbose_name, "name": display_name(obj),
                          "community": community, "url": obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else ""})
    queue.sort(key=lambda x: x["obj"].updated_at)
    return render(request, "core/admin/moderation.html", {"queue": queue})


@admin_required
@require_POST
def moderate(request, key, pk, action):
    model = MODERATED.get(key)
    if model is None or action not in {"aprobar", "rechazar", "retirar"}:
        raise Http404
    obj = get_object_or_404(model, pk=pk)
    note = request.POST.get("note", "").strip()[:1000]
    if action == "aprobar":
        obj.mark_published()
        msg = f"Tu contenido «{display_name(obj)}» fue aprobado y publicado."
    elif action == "rechazar":
        obj.status = ReviewStatus.REJECTED
        msg = f"Tu contenido «{display_name(obj)}» fue rechazado. {note}"
    else:
        obj.status = ReviewStatus.DRAFT
        msg = f"«{display_name(obj)}» fue retirado de la publicación para revisión. {note}"
    obj.review_notes = note
    obj.save()
    log_action(request.user, f"moderacion_{action}", obj, note)
    notify(obj.created_by, msg, obj.get_absolute_url() if obj.is_published and hasattr(obj, "get_absolute_url") else "")
    messages.success(request, f"«{display_name(obj)}»: {obj.get_status_display()}.")
    return redirect(request.POST.get("next") or "core:admin_moderation")


@admin_required
def featured(request):
    form = FeaturedCarouselForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        for c in Community.objects.filter(featured_order__isnull=False):
            log_action(request.user, "carrusel_actualizado", c, f"Diapositiva {c.featured_order}")
        messages.success(request, "Carrusel principal actualizado.")
        return redirect("core:admin_featured")
    return render(request, "core/admin/featured.html", {"form": form})


@admin_required
def donations(request):
    status = request.GET.get("estado", "")
    qs = Donation.objects.select_related("project__community", "user", "verified_by")
    if status in Donation.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "core/admin/donations.html", {"page": page, "statuses": Donation.Status.choices,
                                                         "current": status})


@admin_required
@require_POST
def donation_action(request, pk, action):
    donation = get_object_or_404(Donation, pk=pk)
    note = request.POST.get("note", "").strip()[:300]
    if action == "confirmar":
        donation.status = Donation.Status.CONFIRMED
        donation.verified_by = request.user
        donation.verified_at = timezone.now()
        msg = f"Tu aporte de ${donation.amount} para «{donation.project}» fue confirmado. ¡Gracias!"
    elif action == "rechazar":
        donation.status = Donation.Status.REJECTED
        msg = f"No pudimos verificar tu aporte para «{donation.project}». {note}"
    elif action == "cancelar":
        donation.status = Donation.Status.CANCELLED
        msg = f"Tu registro de aporte para «{donation.project}» fue cancelado. {note}"
    else:
        raise Http404
    donation.admin_note = note
    donation.save()
    log_action(request.user, f"donacion_{action}", donation, note)
    notify(donation.user, msg, "/proyectos/mis-aportes/")
    messages.success(request, f"Aporte #{donation.pk}: {donation.get_status_display()}.")
    return redirect(request.POST.get("next") or "core:admin_donations")


@admin_required
def reviews(request):
    status = request.GET.get("estado", "")
    qs = Review.objects.select_related("user", "community", "place")
    if status in Review.Status.values:
        qs = qs.filter(status=status)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "core/admin/reviews.html", {"page": page, "statuses": Review.Status.choices,
                                                       "current": status})


@admin_required
@require_POST
def review_action(request, pk, action):
    review = get_object_or_404(Review, pk=pk)
    note = request.POST.get("note", "").strip()[:300]
    if action == "ocultar":
        review.status = Review.Status.HIDDEN
    elif action == "publicar":
        review.status = Review.Status.PUBLISHED
    elif action == "eliminar":
        log_action(request.user, "resena_eliminada", review, note)
        notify(review.user, f"Tu reseña sobre {review.target} fue retirada por moderación. {note}")
        review.delete()
        messages.success(request, "Reseña eliminada.")
        return redirect("core:admin_reviews")
    else:
        raise Http404
    review.moderation_note = note
    review.save()
    log_action(request.user, f"resena_{action}", review, note)
    if action == "ocultar":
        notify(review.user, f"Tu reseña sobre {review.target} fue ocultada por moderación. {note}")
    messages.success(request, f"Reseña: {review.get_status_display()}.")
    return redirect(request.POST.get("next") or "core:admin_reviews")


@admin_required
def requests_list(request):
    return render(request, "core/admin/requests.html", {
        "items": CommunityRequest.objects.select_related("user", "province", "community")})


@admin_required
@require_POST
def request_action(request, pk, action):
    req = get_object_or_404(CommunityRequest, pk=pk, status=CommunityRequest.Status.PENDING)
    if action == "aprobar":
        with transaction.atomic():
            canton = Canton.objects.filter(province=req.province, name__iexact=req.canton).first()
            community = Community.objects.create(
                name=req.community_name, province=req.province, canton=canton,
                short_description=req.message[:300], status=ReviewStatus.DRAFT, created_by=req.user)
            RepresentativeAssignment.objects.get_or_create(user=req.user, community=community)
            user = req.user
            if not user.is_platform_admin:
                user.role = User.Role.REPRESENTATIVE
                user.save(update_fields=["role"])
            req.status, req.community = CommunityRequest.Status.APPROVED, community
            req.save()
        log_action(request.user, "solicitud_aprobada", req)
        notify(req.user, f"¡Tu solicitud para {community.name} fue aprobada! Ya puedes completar su información.",
               f"/panel/comunidad/{community.slug}/")
        messages.success(request, f"Solicitud aprobada. Se creó «{community.name}» como borrador.")
    elif action == "rechazar":
        req.status = CommunityRequest.Status.REJECTED
        req.save()
        log_action(request.user, "solicitud_rechazada", req)
        notify(req.user, f"Tu solicitud para {req.community_name} no fue aprobada. "
                         f"{request.POST.get('note', '')[:200]}")
        messages.info(request, "Solicitud rechazada.")
    else:
        raise Http404
    return redirect("core:admin_requests")


@admin_required
def community_create(request):
    form = CommunityForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        c.created_by = request.user
        c.status = ReviewStatus.DRAFT
        c.save()
        form.save_m2m()
        log_action(request.user, "comunidad_creada", c)
        messages.success(request, "Comunidad creada como borrador. Agrega fotografías y publícala.")
        return redirect("core:manage_community", slug=c.slug)
    return render(request, "core/manage/community_form.html", {"form": form, "community": None})


@admin_required
def users(request):
    q = request.GET.get("q", "").strip()
    qs = User.objects.order_by("username").annotate(n_comm=Count("assignments", filter=Q(assignments__is_active=True)))
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "core/admin/users.html", {"page": page, "roles": User.Role.choices, "q": q})


@admin_required
@require_POST
def user_role(request, pk):
    target = get_object_or_404(User, pk=pk)
    role = request.POST.get("role")
    if role not in User.Role.values:
        raise Http404
    if target == request.user and role != User.Role.ADMIN:
        messages.error(request, "No puedes quitarte tu propio rol de administrador.")
        return redirect("core:admin_users")
    target.role = role
    target.is_active = request.POST.get("is_active") == "on"
    target.save(update_fields=["role", "is_active"])
    if role != User.Role.REPRESENTATIVE:
        target.assignments.update(is_active=False)
    log_action(request.user, "rol_actualizado", target, f"Nuevo rol: {target.get_role_display()}")
    messages.success(request, f"{target}: {target.get_role_display()}.")
    return redirect(request.POST.get("next") or "core:admin_users")


@admin_required
@require_POST
def assign_representative(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.POST.get("remove"):
        RepresentativeAssignment.objects.filter(pk=request.POST["remove"], community=community).delete()
        messages.info(request, "Asignación eliminada.")
        return redirect("core:manage_community", slug=slug)
    ident = request.POST.get("user", "").strip()
    user = User.objects.filter(Q(username__iexact=ident) | Q(email__iexact=ident)).first()
    if not user:
        messages.error(request, "No existe un usuario con ese nombre o correo.")
    else:
        if not user.is_platform_admin:
            user.role = User.Role.REPRESENTATIVE
            user.save(update_fields=["role"])
        a, _ = RepresentativeAssignment.objects.get_or_create(user=user, community=community)
        a.is_active = True
        a.save()
        log_action(request.user, "representante_asignado", a)
        notify(user, f"Fuiste asignado/a como representante de {community.name}.", f"/panel/comunidad/{slug}/")
        messages.success(request, f"{user} ahora representa a {community.name}.")
    return redirect("core:manage_community", slug=slug)


@admin_required
def audit(request):
    page = Paginator(AuditLog.objects.select_related("actor"), 50).get_page(request.GET.get("page"))
    return render(request, "core/admin/audit.html", {"page": page})

