from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from communities.models import Community, Favorite, Province
from itineraries.models import ItineraryStop
from reviews.forms import ReviewForm
from reviews.models import Review

from .models import Place


def place_detail(request, slug):
    place = get_object_or_404(Place.objects.select_related("community__province"), slug=slug)
    can_manage = request.user.is_authenticated and request.user.can_manage_community(place.community)
    if not place.is_published and not can_manage:
        raise Http404
    user_review = review_form = None
    is_favorite = False
    if request.user.is_authenticated:
        user_review = Review.objects.filter(place=place, user=request.user).first()
        review_form = None if user_review else ReviewForm()
        is_favorite = Favorite.objects.filter(user=request.user, place=place).exists()
    return render(request, "tourism/place_detail.html", {
        "p": place, "photos": place.photos.all(), "reviews": Review.objects.visible().filter(place=place)
        .select_related("user"), "rating": place.rating_summary(), "user_review": user_review,
        "review_form": review_form, "is_favorite": is_favorite, "can_manage": can_manage,
        "map_points": [{"name": place.name, "lat": float(place.latitude), "lng": float(place.longitude),
                        "kind": place.kind, "verified": place.location_verified}] if place.has_location else [],
    })


@login_required
@require_POST
def toggle_place_favorite(request, slug):
    place = get_object_or_404(Place.objects.published(), slug=slug)
    fav, created = Favorite.objects.get_or_create(user=request.user, place=place)
    if not created:
        fav.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorite": created})
    messages.success(request, "Guardado en favoritos." if created else "Eliminado de favoritos.")
    return redirect(place.get_absolute_url())


def map_page(request):
    kinds = [("community", "Pueblos y comunidades", "bi-people")] + [
        (k, label, Place.ICONS.get(k, "bi-geo-alt")) for k, label in Place.Kind.choices] + [
        ("stop", "Paradas de itinerarios", "bi-signpost-split")]
    return render(request, "tourism/map.html", {"kinds": kinds, "provinces": Province.objects.all()})


def map_data(request):
    """GeoJSON simplificado construido desde PostgreSQL (solo registros publicados con coordenadas)."""
    features = []
    for c in Community.objects.published().select_related("province").exclude(latitude__isnull=True):
        features.append({
            "kind": "community", "kind_label": "Pueblo / comunidad", "name": c.name, "province": c.province.name,
            "lat": float(c.latitude), "lng": float(c.longitude), "url": c.get_absolute_url(),
            "directions": c.directions_url, "verified": c.location_verified, "summary": c.short_description,
        })
    for p in Place.objects.published().select_related("community__province").exclude(latitude__isnull=True):
        features.append({
            "kind": p.kind, "kind_label": p.get_kind_display(), "name": p.name,
            "province": p.community.province.name, "community": p.community.name,
            "lat": float(p.latitude), "lng": float(p.longitude), "url": p.get_absolute_url(),
            "directions": p.directions_url, "verified": p.location_verified, "summary": p.description[:160],
        })
    stops = (ItineraryStop.objects.filter(itinerary__status="published")
             .select_related("itinerary", "place", "community"))
    for s in stops:
        if s.target is None or s.latitude is None:
            continue
        features.append({
            "kind": "stop", "kind_label": f"Parada {s.order} · {s.itinerary.name}", "name": s.name,
            "lat": float(s.latitude), "lng": float(s.longitude), "url": s.itinerary.get_absolute_url(),
            "directions": s.directions_url, "verified": s.location_verified, "summary": s.notes,
        })
    return JsonResponse({"features": features})
