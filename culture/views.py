from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from communities.models import Province

from .models import Craft, CulturalContent, Dish, Festivity


def _filter(request, qs, fields):
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q()
        for f in fields:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)
    prov = request.GET.get("provincia")
    if prov:
        qs = qs.filter(community__province__slug=prov)
    return qs.filter(community__status="published")


def _page(request, qs):
    params = request.GET.copy()
    params.pop("page", None)
    return Paginator(qs, 12).get_page(request.GET.get("page")), params.urlencode()


def gastronomy(request):
    qs = _filter(request, Dish.objects.published().select_related("community__province"),
                 ["name", "description", "ingredients", "community__name"])
    page, qstr = _page(request, qs)
    return render(request, "culture/list.html", {
        "page": page, "querystring": qstr, "kind": "gastronomia", "title": "Gastronomía tradicional",
        "icon": "bi-egg-fried", "intro": "Platos documentados por las propias comunidades y fuentes verificadas.",
        "provinces": Province.objects.all()})


def crafts(request):
    qs = _filter(request, Craft.objects.published().select_related("community__province"),
                 ["name", "description", "materials", "technique", "community__name"])
    tipo = request.GET.get("tipo")
    if tipo:
        qs = qs.filter(kind=tipo)
    page, qstr = _page(request, qs)
    return render(request, "culture/list.html", {
        "page": page, "querystring": qstr, "kind": "artesanias", "title": "Artesanías",
        "icon": "bi-palette", "intro": "Tejidos, cerámica, sombreros, tallados, joyería y otras expresiones.",
        "provinces": Province.objects.all(), "craft_kinds": Craft.Kind.choices})


def traditions(request):
    fest = _filter(request, Festivity.objects.published().select_related("community__province"),
                   ["name", "description", "period", "community__name"])
    contents = _filter(request, CulturalContent.objects.published().select_related("community__province")
                       .exclude(kind="history"), ["title", "description", "community__name"])
    return render(request, "culture/traditions.html", {
        "festivities": fest[:60], "contents": contents[:60], "provinces": Province.objects.all()})
