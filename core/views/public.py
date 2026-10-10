from django.db.models import Count, Q, Sum
from django.shortcuts import render

from communities.models import Category, Community, Favorite, Province
from communities.selectors import carousel_slides, published_communities
from culture.models import Craft, Dish, Festivity
from donations.models import Donation, Project
from itineraries.models import Itinerary
from reviews.models import Review
from tourism.models import Place


def home(request):
    places = Place.objects.published().select_related("community__province").prefetch_related("photos")
    fav_ids = set()
    if request.user.is_authenticated:
        fav_ids = set(Favorite.objects.filter(user=request.user, community__isnull=False)
                      .values_list("community_id", flat=True))
    return render(request, "core/home.html", {
        "slides": carousel_slides(),
        "categories": Category.objects.all()[:8],
        "communities": published_communities().order_by("-published_at", "name")[:8],
        "provinces": (Province.objects.annotate(num=Count("communities", filter=Q(communities__status="published")))
                      .filter(num__gt=0).order_by("-num", "name")[:12]),
        "itineraries": Itinerary.objects.published().select_related("province")[:3],
        "dishes": Dish.objects.published().select_related("community")[:4],
        "crafts": Craft.objects.published().select_related("community")[:4],
        "festivities": Festivity.objects.published().select_related("community")[:4],
        "churches": places.filter(kind__in=[Place.Kind.CHURCH, Place.Kind.HISTORIC, Place.Kind.MUSEUM])[:4],
        "cemeteries": places.filter(kind=Place.Kind.CEMETERY)[:4],
        "nature": places.filter(kind__in=list(Place.NATURE_KINDS))[:4],
        "projects": (Project.objects.published().filter(phase=Project.Phase.FUNDRAISING)
                     .select_related("community")
                     .annotate(confirmed_total=Sum("donations__amount",
                                                   filter=Q(donations__status=Donation.Status.CONFIRMED)))[:3]),
        "reviews": Review.objects.visible().select_related("user", "community", "place")[:4],
        "fav_ids": fav_ids,
    })


def search(request):
    q = request.GET.get("q", "").strip()[:100]
    results = {}
    if len(q) >= 2:
        results = {
            "Pueblos y comunidades": [
                (c.name, c.province.name, c.get_absolute_url()) for c in published_communities().filter(
                    Q(name__icontains=q) | Q(short_description__icontains=q) | Q(canton__name__icontains=q))[:10]],
            "Lugares": [(p.name, f"{p.get_kind_display()} · {p.community.name}", p.get_absolute_url())
                        for p in Place.objects.published().select_related("community").filter(
                    Q(name__icontains=q) | Q(description__icontains=q))[:10]],
            "Gastronomía": [(d.name, d.community.name, d.get_absolute_url()) for d in Dish.objects.published()
                            .select_related("community").filter(Q(name__icontains=q) | Q(ingredients__icontains=q))[:10]],
            "Artesanías": [(c.name, c.community.name, c.get_absolute_url()) for c in Craft.objects.published()
                           .select_related("community").filter(Q(name__icontains=q) | Q(materials__icontains=q))[:10]],
            "Tradiciones y festividades": [
                (f.name, f.community.name, f.get_absolute_url()) for f in Festivity.objects.published()
                .select_related("community").filter(Q(name__icontains=q) | Q(description__icontains=q))[:10]],
            "Itinerarios": [(i.name, i.get_kind_display(), i.get_absolute_url()) for i in
                            Itinerary.objects.published().filter(Q(name__icontains=q) | Q(description__icontains=q))[:10]],
            "Proyectos comunitarios": [(p.name, p.community.name, p.get_absolute_url()) for p in
                                       Project.objects.published().select_related("community").filter(
                                           Q(name__icontains=q) | Q(description__icontains=q))[:10]],
        }
    total = sum(len(v) for v in results.values())
    return render(request, "core/search.html", {"q": q, "results": results, "total": total})


def privacy(request):
    return render(request, "core/privacy.html")


def terms(request):
    return render(request, "core/terms.html")


def about(request):
    stats = {"communities": Community.objects.published().count(),
             "places": Place.objects.published().count(),
             "itineraries": Itinerary.objects.published().count()}
    return render(request, "core/about.html", {"stats": stats})
