from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.services import log_action, notify_admins
from culture.models import CulturalContent
from donations.models import Project
from itineraries.models import Itinerary
from reviews.forms import ReviewForm
from reviews.models import Review
from tourism.models import Place

from .forms import CommunityFilterForm, CommunityRequestForm
from .models import Community, Favorite
from .selectors import filter_communities, published_communities


def community_list(request):
    form = CommunityFilterForm(request.GET or None)
    data = form.cleaned_data if form.is_valid() else {}
    qs = filter_communities(published_communities(), data)
    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    fav_ids = set()
    if request.user.is_authenticated:
        fav_ids = set(Favorite.objects.filter(user=request.user, community__isnull=False)
                      .values_list("community_id", flat=True))
    return render(request, "communities/list.html", {
        "form": form, "page": page, "querystring": params.urlencode(), "fav_ids": fav_ids,
        "total": qs.count(),
    })


def community_detail(request, slug):
    community = get_object_or_404(
        Community.objects.select_related("province", "canton").prefetch_related("categories"), slug=slug)
    can_manage = request.user.is_authenticated and request.user.can_manage_community(community)
    if not community.is_published and not can_manage:
        raise Http404("Pueblo no publicado")

    contents = CulturalContent.objects.published().filter(community=community)
    places = list(Place.objects.published().filter(community=community).prefetch_related("photos"))
    heritage = [p for p in places if p.kind in Place.HERITAGE_KINDS]
    nature = [p for p in places if p.kind in Place.NATURE_KINDS]
    services_places = [p for p in places if p.kind in Place.SERVICE_KINDS]
    other_places = [p for p in places if p not in heritage + nature + services_places]
    itineraries = (Itinerary.objects.published()
                   .filter(Q(community=community) | Q(stops__community=community)
                           | Q(stops__place__community=community)).distinct())
    reviews = Review.objects.visible().filter(community=community).select_related("user")
    projects = Project.objects.published().filter(community=community)

    user_review, review_form, is_favorite = None, None, False
    if request.user.is_authenticated:
        user_review = Review.objects.filter(community=community, user=request.user).first()
        review_form = None if user_review else ReviewForm()
        is_favorite = Favorite.objects.filter(user=request.user, community=community).exists()

    map_points = [{"name": community.name, "lat": float(community.latitude), "lng": float(community.longitude),
                   "kind": "community", "verified": community.location_verified}] if community.has_location else []
    map_points += [{"name": p.name, "lat": float(p.latitude), "lng": float(p.longitude), "kind": p.kind,
                    "url": p.get_absolute_url(), "verified": p.location_verified} for p in places if p.has_location]

    return render(request, "communities/detail.html", {
        "c": community,
        "can_manage": can_manage,
        "contents_by_kind": {k: [x for x in contents if x.kind == k] for k, _ in CulturalContent.Kind.choices},
        "content_kinds": CulturalContent.Kind.choices,
        "dishes": community.dishes.published(),
        "crafts": community.crafts.published(),
        "festivities": community.festivities.published(),
        "heritage": heritage, "nature": nature, "service_places": services_places, "other_places": other_places,
        "services": community.services.published(),
        "photos": community.photos.select_related("place"),
        "itineraries": itineraries,
        "reviews": reviews,
        "rating": community.rating_summary(),
        "user_review": user_review, "review_form": review_form,
        "projects": projects,
        "is_favorite": is_favorite,
        "map_points": map_points,
    })


@login_required
@require_POST
def toggle_favorite(request, slug):
    community = get_object_or_404(Community.objects.published(), slug=slug)
    fav, created = Favorite.objects.get_or_create(user=request.user, community=community)
    if not created:
        fav.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorite": created})
    messages.success(request, "Guardado en favoritos." if created else "Eliminado de favoritos.")
    return redirect(request.POST.get("next") or community.get_absolute_url())


@login_required
def request_registration(request):
    form = CommunityRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        req = form.save(commit=False)
        req.user = request.user
        req.save()
        log_action(request.user, "solicitud_comunidad", req)
        notify_admins(f"Nueva solicitud de registro: {req.community_name}", reverse("core:admin_requests"))
        messages.success(request, "Solicitud enviada. El administrador la revisará y te notificará.")
        return redirect("accounts:notifications")
    return render(request, "communities/request_form.html", {
        "form": form, "my_requests": request.user.community_requests.all()})
