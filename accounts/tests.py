from django.core import mail
from django.test import TestCase
from django.urls import reverse

from core.tests import factories as f

from .models import User


class AuthTests(TestCase):
    def test_signup_creates_tourist_with_hashed_password(self):
        r = self.client.post(reverse("accounts:signup"), {
            "username": "nuevo", "first_name": "Ana", "last_name": "Paz", "email": "ana@test.ec",
            "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026", "accept_terms": "on",
            "role": "admin"})  # intento de elevar el rol: debe ignorarse
        self.assertRedirects(r, reverse("accounts:profile"))
        u = User.objects.get(username="nuevo")
        self.assertEqual(u.role, User.Role.TOURIST)
        self.assertNotEqual(u.password, "Clave-Segura-2026")
        self.assertTrue(u.check_password("Clave-Segura-2026"))

    def test_signup_validation_errors(self):
        f.user("ana")
        r = self.client.post(reverse("accounts:signup"), {"username": "otra", "email": "ana@test.ec",
                                                          "password1": "123", "password2": "456"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="otra").exists())
        self.assertContains(r, "Ya existe una cuenta con este correo")

    def test_login_redirects_by_role(self):
        f.user("admin1", User.Role.ADMIN)
        f.user("rep1", User.Role.REPRESENTATIVE)
        f.user("tur1")
        for name, target in [("admin1", "core:admin_dashboard"), ("rep1", "core:rep_dashboard"), ("tur1", "core:home")]:
            r = self.client.post(reverse("accounts:login"), {"username": name, "password": "Clave-Segura-2026"})
            self.assertRedirects(r, reverse(target), fetch_redirect_response=False)
            self.client.post(reverse("accounts:logout"))

    def test_login_rejects_external_next(self):
        f.user("tur1")
        r = self.client.post(reverse("accounts:login") + "?next=https://malicioso.com",
                             {"username": "tur1", "password": "Clave-Segura-2026"})
        self.assertRedirects(r, reverse("core:home"), fetch_redirect_response=False)

    def test_password_reset_sends_email(self):
        f.user("tur1")
        self.client.post(reverse("accounts:password_reset"), {"email": "tur1@test.ec"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/cuenta/recuperar/", mail.outbox[0].body)

    def test_csrf_enforced(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("accounts:login"), {"username": "x", "password": "y"})
        self.assertEqual(r.status_code, 403)
