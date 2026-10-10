from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import manager_required
from core.models import ReviewStatus
from core.services import log_action, notify_admins

from .forms import (AddTripStopForm, CustomTripForm, ItineraryFilterForm, ItineraryForm, ItineraryStopFormSet,
                    TripStopDateForm)
from .models import CustomTrip, CustomTripStop, FavoriteItinerary, Itinerary


def _stop_points(stops):
    return [{"order": i, "name": s.name, "lat": float(s.latitude), "lng": float(s.longitude), "url": s.url,
             "directions": s.directions_url, "verified": s.location_verified}
            for i, s in enumerate(stops, start=1) if s.target and s.latitude is not None]


def itinerary_list(request):
    form = ItineraryFilterForm(request.GET or None)
    qs = (Itinerary.objects.published().select_related("province")
          .annotate(num_stops=Count("stops")))
    if form.is_valid():
        d = form.cleaned_data
        if d.get("q"):
            qs = qs.filter(Q(name__icontains=d["q"]) | Q(description__icontains=d["q"]))
        if d.get("province"):
            qs = qs.filter(province=d["province"])
        if d.get("kind"):
            qs = qs.filter(kind=d["kind"])
        if d.get("duration"):
            n = int(d["duration"])
            qs = qs.filter(duration_days__gte=3) if n >= 3 else qs.filter(duration_days=n)
        if d.get("max_budget") is not None:
            qs = qs.filter(budget_estimate__isnull=False, budget_estimate__lte=d["max_budget"])
    params = request.GET.copy()
    params.pop("page", None)
    page = Paginator(qs.order_by("name"), 9).get_page(request.GET.get("page"))
    return render(request, "itineraries/list.html", {"form": form, "page": page, "querystring": params.urlencode()})


def itinerary_detail(request, slug):
    it = get_object_or_404(Itinerary.objects.select_related("province", "community"), slug=slug)
    can_edit = request.user.is_authenticated and (
        request.user.is_platform_admin or (it.community and request.user.can_manage_community(it.community)))
    if not it.is_published and not can_edit:
        raise Http404
    stops = list(it.stops.select_related("place__community", "community"))
    is_fav = request.user.is_authenticated and FavoriteItinerary.objects.filter(
        user=request.user, itinerary=it).exists()
    return render(request, "itineraries/detail.html", {
        "it": it, "stops": stops, "points": _stop_points(stops), "is_fav": is_fav, "can_edit": can_edit,
        "route_url": it.route_url(),
    })


@login_required
@require_POST
def toggle_favorite(request, slug):
    it = get_object_or_404(Itinerary.objects.published(), slug=slug)
    fav, created = FavoriteItinerary.objects.get_or_create(user=request.user, itinerary=it)
    if not created:
        fav.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"favorite": created})
    messages.success(request, "Itinerario guardado." if created else "Itinerario quitado de favoritos.")
    return redirect(it.get_absolute_url())


# ----------------------------------------------------------------------------------------------
# Itinerarios públicos: administración (administrador o representante de la comunidad)
# ----------------------------------------------------------------------------------------------
@manager_required
def manage_itinerary(request, slug=None):
    user = request.user
    it = get_object_or_404(Itinerary, slug=slug) if slug else Itinerary()
    if it.pk and not (user.is_platform_admin or (it.community and user.can_manage_community(it.community))):
        raise PermissionDenied
    form = ItineraryForm(request.POST or None, request.FILES or None, instance=it, user=user)
    formset = ItineraryStopFormSet(request.POST or None, instance=it, prefix="stops")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        if form.cleaned_data.get("community") and not user.can_manage_community(form.cleaned_data["community"]):
            raise PermissionDenied
        with transaction.atomic():
            obj = form.save(commit=False)
            if not obj.pk:
                obj.created_by = user
            if user.is_platform_admin:
                action = request.POST.get("action", "publish")
                if action == "publish":
                    obj.mark_published()
                else:
                    obj.status = ReviewStatus.DRAFT
            elif not obj.is_published:
                obj.status = ReviewStatus.PENDING if request.POST.get("action") == "submit" else ReviewStatus.DRAFT
            obj.save()
            formset.instance = obj
            formset.save()
            # Normaliza el orden 1..n respetando el orden indicado
            for i, s in enumerate(obj.stops.order_by("order", "id"), start=1):
                if s.order != i:
                    s.order = i
                    s.save(update_fields=["order"])
        log_action(user, "itinerario_guardado", obj)
        if obj.status == ReviewStatus.PENDING:
            notify_admins(f"Itinerario pendiente de revisión: {obj.name}", "/panel/administracion/moderacion/")
        messages.success(request, f"Itinerario guardado ({obj.get_status_display()}).")
        return redirect(obj.get_absolute_url())
    return render(request, "itineraries/manage.html", {"form": form, "formset": formset, "it": it})


# ----------------------------------------------------------------------------------------------
# Recorridos personalizados del turista
# ----------------------------------------------------------------------------------------------
def _own_trip(request, pk):
    trip = get_object_or_404(CustomTrip, pk=pk)
    if trip.user_id != request.user.id:
        raise PermissionDenied
    return trip


@login_required
def trip_list(request):
    trips = request.user.custom_trips.annotate(num_stops=Count("stops"))
    form = CustomTripForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        trip = form.save(commit=False)
        trip.user = request.user
        trip.save()
        messages.success(request, "Recorrido creado. Ahora agrega tus paradas.")
        return redirect(trip.get_absolute_url())
    return render(request, "itineraries/trip_list.html", {"trips": trips, "form": form})


@login_required
@require_POST
def trip_from_itinerary(request, slug):
    it = get_object_or_404(Itinerary.objects.published(), slug=slug)
    with transaction.atomic():
        trip = CustomTrip.objects.create(user=request.user, name=f"Mi versión de {it.name}"[:150], based_on=it)
        CustomTripStop.objects.bulk_create([
            CustomTripStop(trip=trip, place=s.place, community=s.community, order=i, notes=s.notes)
            for i, s in enumerate(it.stops.all(), start=1)])
    messages.success(request, "Copiamos el itinerario a tus recorridos. Personalízalo a tu gusto.")
    return redirect(trip.get_absolute_url())


@login_required
def trip_detail(request, pk):
    trip = _own_trip(request, pk)
    form = CustomTripForm(request.POST or None, instance=trip, prefix="trip")
    if request.method == "POST" and "save_trip" in request.POST and form.is_valid():
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect(trip.get_absolute_url())
    stops = list(trip.stops.select_related("place__community", "community"))
    return render(request, "itineraries/trip_detail.html", {
        "trip": trip, "form": form, "add_form": AddTripStopForm(prefix="add"), "stops": stops,
        "stop_forms": [(s, TripStopDateForm(instance=s, prefix=f"s{s.pk}")) for s in stops],
        "points": _stop_points(stops), "route_url": trip.route_url(),
    })


@login_required
@require_POST
def trip_add_stop(request, pk):
    trip = _own_trip(request, pk)
    form = AddTripStopForm(request.POST, prefix="add")
    if form.is_valid():
        d = form.cleaned_data
        next_order = (trip.stops.aggregate(m=Max("order"))["m"] or 0) + 1
        CustomTripStop.objects.create(trip=trip, place=d.get("place"), community=d.get("community"),
                                      visit_date=d.get("visit_date"), notes=d.get("notes", ""), order=next_order)
        trip.save(update_fields=["updated_at"])
        messages.success(request, "Parada agregada.")
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect(trip.get_absolute_url())


@login_required
@require_POST
def trip_stop_action(request, pk, stop_id, action):
    trip = _own_trip(request, pk)
    stop = get_object_or_404(CustomTripStop, pk=stop_id, trip=trip)
    if action == "eliminar":
        stop.delete()
        trip.normalize_order()
        messages.success(request, "Parada eliminada.")
    elif action in {"subir", "bajar"}:
        trip.normalize_order()
        stop.refresh_from_db()
        neighbor_order = stop.order - 1 if action == "subir" else stop.order + 1
        neighbor = trip.stops.filter(order=neighbor_order).first()
        if neighbor:
            with transaction.atomic():
                neighbor.order, stop.order = stop.order, neighbor.order
                neighbor.save(update_fields=["order"])
                stop.save(update_fields=["order"])
    elif action == "actualizar":
        form = TripStopDateForm(request.POST, instance=stop, prefix=f"s{stop.pk}")
        if form.is_valid():
            form.save()
            messages.success(request, "Parada actualizada.")
        else:
            messages.error(request, "Fecha no válida.")
    else:
        raise Http404
    trip.save(update_fields=["updated_at"])
    return redirect(trip.get_absolute_url() + "#paradas")


@login_required
@require_POST
def trip_reorder(request, pk):
    """Reordenamiento completo (arrastrar y soltar): recibe ids en el nuevo orden."""
    trip = _own_trip(request, pk)
    ids = [int(x) for x in request.POST.getlist("stop") if x.isdigit()]
    own_ids = set(trip.stops.values_list("id", flat=True))
    if set(ids) != own_ids:
        return JsonResponse({"ok": False, "error": "Lista de paradas inválida."}, status=400)
    with transaction.atomic():
        for i, sid in enumerate(ids, start=1):
            CustomTripStop.objects.filter(pk=sid, trip=trip).update(order=i)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def trip_delete(request, pk):
    trip = _own_trip(request, pk)
    trip.delete()
    messages.success(request, "Recorrido eliminado.")
    return redirect("itineraries:trips")
