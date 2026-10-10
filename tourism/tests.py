from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

from core.services import google_maps_directions_url, google_maps_route_url
from core.tests import factories as f


class MapTests(TestCase):
    def setUp(self):
        self.c = f.community("Otavalo")
        self.p = f.place(self.c)
        self.nocoords = f.community("Ligüiqui", f.province("Manabí", "costa"), lat=None, lng=None)

    def test_map_data_comes_from_database(self):
        data = self.client.get(reverse("tourism:map_data")).json()["features"]
        names = {x["name"] for x in data}
        self.assertEqual(names, {"Otavalo", "Cascada de prueba"})  # sin coordenadas = no se inventa ubicación
        self.assertTrue(all(x["directions"].startswith("https://www.google.com/maps/dir/?api=1") for x in data))
        self.assertEqual(self.client.get(reverse("tourism:map")).status_code, 200)

    def test_google_maps_links(self):
        url = google_maps_directions_url("0.2343", "-78.2611")
        q = parse_qs(urlparse(url).query)
        self.assertEqual(q["api"], ["1"])
        self.assertEqual(q["destination"], ["0.234300,-78.261100"])
        self.assertEqual(google_maps_directions_url("95", "0"), "")  # coordenada inválida
        self.assertEqual(google_maps_directions_url(None, None), "")
        route = parse_qs(urlparse(google_maps_route_url([(0, -78), (1, -78), (2, -78)])).query)
        self.assertEqual(route["origin"], ["0.000000,-78.000000"])
        self.assertEqual(route["waypoints"], ["1.000000,-78.000000"])

    def test_detail_shows_pending_location(self):
        r = self.client.get(self.nocoords.get_absolute_url())
        self.assertContains(r, "Ubicación pendiente de validación")
        r = self.client.get(self.c.get_absolute_url())
        self.assertContains(r, "https://www.google.com/maps/dir/?api=1&amp;destination=0.234300%2C-78.261100")
        self.assertContains(r, "aproximada")  # no verificada

    def test_place_detail(self):
        r = self.client.get(self.p.get_absolute_url())
        self.assertContains(r, "Cómo llegar")
