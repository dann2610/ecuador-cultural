"""Pruebas de integración: los módulos funcionan juntos y los datos persisten en PostgreSQL."""
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from communities.models import Community
from donations.models import Donation, Project
from itineraries.models import Itinerary


class IntegrationTests(TestCase):
    def test_database_is_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

    @override_settings(MEDIA_ROOT="/tmp/ec-test-media")
    def test_demo_data_and_full_flow(self):
        call_command("cargar_datos_demo", "--sin-imagenes", stdout=open("/dev/null", "w"))
        call_command("cargar_datos_demo", "--sin-imagenes", stdout=open("/dev/null", "w"))  # idempotente
        self.assertEqual(Community.objects.filter(name="Otavalo").count(), 1)
        self.assertTrue(Community.objects.filter(is_demo=True).exists())
        self.assertFalse(Donation.objects.exists())  # nunca se inventan donaciones
        # páginas públicas principales
        for url in ["/", "/pueblos/", "/itinerarios/", "/proyectos/", "/mapa/", "/gastronomia/", "/artesanias/",
                    "/cultura-y-tradiciones/", "/buscar/?q=ota"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        # turista: favorito, recorrido desde itinerario, aporte
        u = User.objects.create_user("tur", "tur@test.ec", "Clave-Segura-2026")
        self.client.force_login(u)
        it = Itinerary.objects.get(slug="ruta-artesanal-de-otavalo")
        self.client.post(reverse("itineraries:copy", args=[it.slug]))
        self.assertEqual(u.custom_trips.get().stops.count(), it.stops.count())
        p = Project.objects.first()
        self.client.post(reverse("donations:donate"), {"project": p.pk, "amount": "15", "method": "deposit"})
        self.assertEqual(Donation.objects.get().status, Donation.Status.PLEDGED)
        # el chatbot responde con lo que hay en la base de datos
        r = self.client.post(reverse("chatbot:ask"), '{"message": "Quiero una ruta cultural de dos días"}',
                             content_type="application/json").json()
        self.assertEqual(r["intent"], "itineraries")
        self.assertTrue(r["items"])

    def test_mobile_meta_and_navigation(self):
        r = self.client.get("/")
        self.assertContains(r, 'name="viewport" content="width=device-width, initial-scale=1"')
        self.assertContains(r, 'data-bs-toggle="offcanvas"')  # menú compacto en móviles
