from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.tests import factories as f

from .models import Review


class ReviewTests(TestCase):
    def setUp(self):
        self.c = f.community("Otavalo")
        self.u = f.user("tur")
        self.admin = f.user("adm", User.Role.ADMIN)

    def test_publish_average_and_moderation(self):
        self.client.force_login(self.u)
        url = reverse("reviews:create", args=["pueblo", "otavalo"])
        self.client.post(url, {"rating": 4, "comment": "Muy bonito lugar, gente amable"})
        self.client.post(url, {"rating": 1, "comment": "Segundo intento duplicado"})
        self.assertEqual(Review.objects.count(), 1)  # una reseña por usuario y lugar
        other = f.user("otro")
        self.client.force_login(other)
        self.client.post(url, {"rating": 2, "comment": "Experiencia regular en general"})
        self.assertEqual(self.c.rating_summary()["avg"], 3)
        review = Review.objects.get(user=other)
        self.client.force_login(self.admin)
        self.client.post(reverse("core:review_action", args=[review.pk, "ocultar"]), {"note": "Lenguaje"})
        self.assertEqual(self.c.rating_summary()["avg"], 4)
        r = self.client.get(self.c.get_absolute_url())
        self.assertNotContains(r, "Experiencia regular")

    def test_validation_and_ownership(self):
        self.client.force_login(self.u)
        self.client.post(reverse("reviews:create", args=["pueblo", "otavalo"]), {"rating": 9, "comment": "corto"})
        self.assertFalse(Review.objects.exists())
        review = Review.objects.create(user=self.u, community=self.c, rating=5, comment="Excelente visita guiada")
        self.client.force_login(f.user("intruso"))
        self.assertEqual(self.client.post(reverse("reviews:delete", args=[review.pk])).status_code, 403)
        self.client.force_login(self.u)
        self.client.post(reverse("reviews:edit", args=[review.pk]), {"rating": 3, "comment": "Cambié de opinión"})
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)

    def test_anonymous_cannot_review(self):
        r = self.client.post(reverse("reviews:create", args=["pueblo", "otavalo"]), {"rating": 5, "comment": "x" * 20})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Review.objects.exists())
