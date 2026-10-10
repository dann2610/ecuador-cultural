from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import ReviewStatus
from core.tests import factories as f

from .models import Donation, Project


class DonationTests(TestCase):
    def setUp(self):
        self.c = f.community("Saraguro")
        self.project = f.project(self.c)
        self.u = f.user("tur")
        self.admin = f.user("adm", User.Role.ADMIN)
        self.rep = f.user("rep", User.Role.REPRESENTATIVE)
        f.assign(self.rep, self.c)

    def test_rep_creates_project_pending(self):
        self.client.force_login(self.rep)
        self.client.post(reverse("core:item_create", args=[self.c.slug, "proyecto"]), {
            "name": "Taller", "description": "d", "objective": "o", "goal_amount": "500", "start_date": "2026-10-01",
            "phase": "fundraising", "responsible_name": "Rosa", "action": "submit"})
        p = Project.objects.get(name="Taller")
        self.assertEqual(p.status, ReviewStatus.PENDING)
        self.assertEqual(p.responsible, self.rep)

    def test_donation_never_auto_confirmed(self):
        self.client.force_login(self.u)
        r = self.client.post(reverse("donations:donate"), {
            "project": self.project.pk, "amount": "25.50", "method": "transfer", "transaction_reference": "TRX-001"})
        self.assertRedirects(r, reverse("donations:mine"))
        d = Donation.objects.get()
        self.assertEqual(d.status, Donation.Status.UNDER_REVIEW)
        self.assertEqual(self.project.confirmed_amount, Decimal("0"))
        self.client.force_login(self.admin)
        self.client.post(reverse("core:donation_action", args=[d.pk, "confirmar"]))
        d.refresh_from_db()
        self.assertEqual(d.status, Donation.Status.CONFIRMED)
        self.assertEqual(d.verified_by, self.admin)
        self.assertEqual(self.project.confirmed_amount, Decimal("25.50"))
        self.assertTrue(self.u.notifications.filter(message__icontains="confirmado").exists())
        self.client.force_login(self.u)
        self.assertContains(self.client.get(reverse("donations:mine")), "Confirmada")

    def test_card_numbers_rejected(self):
        self.client.force_login(self.u)
        r = self.client.post(reverse("donations:donate"), {
            "project": self.project.pk, "amount": "10", "method": "transfer",
            "transaction_reference": "4111 1111 1111 1111"})
        self.assertContains(r, "no ingreses números de tarjeta")
        self.assertFalse(Donation.objects.exists())

    def test_db_constraint_blocks_unverified_confirmation(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Donation.objects.create(project=self.project, amount=5, status=Donation.Status.CONFIRMED)

    def test_only_admin_confirms_and_rep_sees_project_donations(self):
        d = Donation.objects.create(project=self.project, user=self.u, amount=10, donor_name="Ana Secreta")
        self.client.force_login(self.rep)
        self.assertEqual(self.client.post(reverse("core:donation_action", args=[d.pk, "confirmar"])).status_code, 403)
        r = self.client.get(reverse("donations:project_donations", args=[self.project.slug]))
        self.assertContains(r, "Aporte anónimo")
        self.assertNotContains(r, "Ana Secreta")
        self.assertNotContains(r, "tur@test.ec")

    def test_minimum_amount(self):
        self.client.force_login(self.u)
        self.client.post(reverse("donations:donate"), {"project": self.project.pk, "amount": "0.5", "method": "transfer"})
        self.assertFalse(Donation.objects.exists())
