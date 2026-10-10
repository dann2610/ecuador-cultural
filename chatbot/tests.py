import json

from django.test import TestCase
from django.urls import reverse

from core.tests import factories as f
from culture.models import Craft
from core.models import ReviewStatus

from .models import FAQ, Conversation


class ChatbotTests(TestCase):
    def setUp(self):
        self.otavalo = f.community("Otavalo")
        f.community("Cuenca", f.province("Azuay"))
        f.place(self.otavalo, "Iglesia de prueba", kind="church")
        Craft.objects.create(community=self.otavalo, name="Tejidos de prueba", description="d",
                             status=ReviewStatus.PUBLISHED)

    def ask(self, text, **extra):
        r = self.client.post(reverse("chatbot:ask"), json.dumps({"message": text, **extra}),
                             content_type="application/json")
        return r

    def test_answers_from_database(self):
        data = self.ask("¿Qué pueblos puedo visitar en Imbabura?").json()
        self.assertEqual(data["intent"], "towns")
        self.assertEqual([i["title"] for i in data["items"]], ["Otavalo"])
        data = self.ask("¿Dónde puedo encontrar artesanías tradicionales?").json()
        self.assertIn("Tejidos de prueba", [i["title"] for i in data["items"]])
        data = self.ask("¿Qué iglesias hay en Imbabura?").json()
        self.assertIn("Iglesia de prueba", [i["title"] for i in data["items"]])

    def test_directions_use_google_maps(self):
        data = self.ask("¿Cómo llego a Otavalo desde Quito?").json()
        self.assertEqual(data["intent"], "directions")
        self.assertTrue(data["items"][0]["maps"].startswith("https://www.google.com/maps/dir/?api=1"))

    def test_admits_missing_information(self):
        data = self.ask("¿Cuál es el horario del tren a la luna?").json()
        self.assertEqual(data["intent"], "fallback")
        self.assertIn("No encontré información suficiente", data["reply"])

    def test_faq_and_validation(self):
        FAQ.objects.create(question="¿Cómo registro mi comunidad?", answer="Respuesta FAQ",
                           keywords="registrar,comunidad", is_verified=True)
        self.assertEqual(self.ask("quiero registrar mi comunidad").json()["reply"], "Respuesta FAQ")
        self.assertEqual(self.ask("").status_code, 400)
        self.assertEqual(self.ask("x" * 600).status_code, 400)

    def test_history_is_optional_and_deletable(self):
        self.ask("Hola Otavalo")
        self.assertFalse(Conversation.objects.exists())  # visitantes: nunca se guarda
        u = f.user("tur")
        self.client.force_login(u)
        self.ask("Hola Otavalo", save_history=True)
        self.assertEqual(Conversation.objects.get(user=u).messages.count(), 2)
        self.client.post(reverse("chatbot:delete_history"))
        self.assertFalse(Conversation.objects.exists())
