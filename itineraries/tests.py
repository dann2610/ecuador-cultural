from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import ReviewStatus
from core.tests import factories as f

from .models import CustomTrip, Itinerary


class ItineraryTests(TestCase):
    def setUp(self):
        self.c = f.community("Otavalo")
        self.p1 = f.place(self.c, "Plaza", lat="0.235", lng="-78.262")
        self.p2 = f.place(self.c, "Cascada")
        self.p3 = f.place(self.c, "Mirador", lat=None, lng=None)
        self.tourist = f.user("tur")
        self.rep = f.user("rep", User.Role.REPRESENTATIVE)
        f.assign(self.rep, self.c)

    def _formset(self, stops):
        data = {"stops-TOTAL_FORMS": str(len(stops)), "stops-INITIAL_FORMS": "0", "stops-MIN_NUM_FORMS": "1",
                "stops-MAX_NUM_FORMS": "1000"}
        for i, (order, place) in enumerate(stops):
            data.update({f"stops-{i}-order": order, f"stops-{i}-day": 1, f"stops-{i}-place": place.pk})
        return data

    def test_rep_creates_public_itinerary_pending_review(self):
        self.client.force_login(self.rep)
        data = {"name": "Ruta textil", "kind": "crafts", "description": "Ruta", "community": self.c.pk,
                "duration_days": 1, "action": "submit", **self._formset([(2, self.p2), (1, self.p1)])}
        r = self.client.post(reverse("itineraries:create"), data)
        it = Itinerary.objects.get(name="Ruta textil")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(it.status, ReviewStatus.PENDING)
        self.assertEqual([s.place for s in it.stops.all()], [self.p1, self.p2])
        self.assertEqual([s.order for s in it.stops.all()], [1, 2])

    def test_tourist_cannot_create_public_itinerary(self):
        self.client.force_login(self.tourist)
        self.assertEqual(self.client.get(reverse("itineraries:create")).status_code, 403)

    def test_filters(self):
        Itinerary.objects.create(name="A", kind="crafts", description="d", duration_days=1,
                                 province=self.c.province, status=ReviewStatus.PUBLISHED)
        Itinerary.objects.create(name="B", kind="nature", description="d", duration_days=3,
                                 status=ReviewStatus.PUBLISHED, budget_estimate=50)
        r = self.client.get(reverse("itineraries:list"), {"duration": "3"})
        self.assertEqual([i.name for i in r.context["page"]], ["B"])
        r = self.client.get(reverse("itineraries:list"), {"max_budget": "60"})
        self.assertEqual([i.name for i in r.context["page"]], ["B"])
        r = self.client.get(reverse("itineraries:list"), {"province": "imbabura"})
        self.assertEqual([i.name for i in r.context["page"]], ["A"])

    def test_custom_trip_add_reorder_dates_delete(self):
        self.client.force_login(self.tourist)
        self.client.post(reverse("itineraries:trips"), {"name": "Mi viaje", "start_date": "2026-11-01",
                                                        "end_date": "2026-11-03"})
        trip = CustomTrip.objects.get(user=self.tourist)
        for p in (self.p1, self.p2, self.p3):
            self.client.post(reverse("itineraries:trip_add_stop", args=[trip.pk]), {"add-place": p.pk})
        self.assertEqual([s.place for s in trip.stops.all()], [self.p1, self.p2, self.p3])
        s3 = trip.stops.get(place=self.p3)
        self.client.post(reverse("itineraries:trip_stop_action", args=[trip.pk, s3.pk, "subir"]))
        self.assertEqual([s.place for s in trip.stops.all()], [self.p1, self.p3, self.p2])
        ids = [str(s.pk) for s in trip.stops.order_by("-order")]
        r = self.client.post(reverse("itineraries:trip_reorder", args=[trip.pk]), {"stop": ids})
        self.assertTrue(r.json()["ok"])
        self.assertEqual([s.place for s in trip.stops.all()], [self.p2, self.p3, self.p1])
        self.client.post(reverse("itineraries:trip_stop_action", args=[trip.pk, s3.pk, "actualizar"]),
                         {f"s{s3.pk}-visit_date": "2026-11-02", f"s{s3.pk}-notes": "Llevar abrigo"})
        s3.refresh_from_db()
        self.assertEqual(str(s3.visit_date), "2026-11-02")
        self.client.post(reverse("itineraries:trip_stop_action", args=[trip.pk, s3.pk, "eliminar"]))
        self.assertEqual([s.order for s in trip.stops.all()], [1, 2])
        r = self.client.get(trip.get_absolute_url())
        self.assertEqual(len(r.context["points"]), 2)  # mapa del recorrido con paradas geolocalizadas

    def test_trip_is_private(self):
        trip = CustomTrip.objects.create(user=self.tourist, name="Privado")
        other = f.user("otro")
        self.client.force_login(other)
        self.assertEqual(self.client.get(trip.get_absolute_url()).status_code, 403)
        r = self.client.post(reverse("itineraries:trip_reorder", args=[trip.pk]), {"stop": []})
        self.assertEqual(r.status_code, 403)

    def test_end_date_validation(self):
        self.client.force_login(self.tourist)
        r = self.client.post(reverse("itineraries:trips"), {"name": "X", "start_date": "2026-11-05",
                                                            "end_date": "2026-11-01"})
        self.assertContains(r, "no puede ser anterior")
