import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.models import ReviewStatus
from core.tests import factories as f

from .models import Community, Photo

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class CommunityTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.admin = f.user("admin", User.Role.ADMIN)
        self.rep = f.user("rep", User.Role.REPRESENTATIVE)
        self.tourist = f.user("tur")
        self.otavalo = f.community("Otavalo")
        self.cuenca = f.community("Cuenca", f.province("Azuay"))
        f.assign(self.rep, self.otavalo)

    # --- Permisos por rol y por comunidad asignada -------------------------------------
    def test_role_access_matrix(self):
        url = reverse("core:manage_community", args=["otavalo"])
        self.assertEqual(self.client.get(url).status_code, 302)  # visitante → login
        self.client.force_login(self.tourist)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.rep)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("core:manage_community", args=["cuenca"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:admin_dashboard")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("core:manage_community", args=["cuenca"])).status_code, 200)

    def test_rep_cannot_edit_unassigned_community_via_post(self):
        self.client.force_login(self.rep)
        r = self.client.post(reverse("core:edit_community", args=["cuenca"]), {"name": "Hackeado"})
        self.assertEqual(r.status_code, 403)
        self.cuenca.refresh_from_db()
        self.assertEqual(self.cuenca.name, "Cuenca")

    # --- Creación y edición de comunidades ---------------------------------------------
    def test_admin_creates_community_as_draft(self):
        self.client.force_login(self.admin)
        prov = f.province("Loja")
        r = self.client.post(reverse("core:community_create"), {
            "name": "Saraguro", "province": prov.pk, "short_description": "Pueblo kichwa", "latitude": "",
            "longitude": ""})
        c = Community.objects.get(name="Saraguro")
        self.assertRedirects(r, reverse("core:manage_community", args=[c.slug]))
        self.assertEqual(c.status, ReviewStatus.DRAFT)
        self.assertEqual(self.client.get(c.get_absolute_url()).status_code, 200)  # admin ve vista previa
        self.client.logout()
        self.assertEqual(self.client.get(c.get_absolute_url()).status_code, 404)  # público no

    def test_rep_edit_resets_location_verification(self):
        self.otavalo.location_verified = True
        self.otavalo.save()
        self.client.force_login(self.rep)
        r = self.client.post(reverse("core:edit_community", args=["otavalo"]), {
            "name": "Otavalo", "province": self.otavalo.province.pk, "short_description": "Nueva descripción",
            "latitude": "0.235000", "longitude": "-78.260000"})
        self.assertEqual(r.status_code, 302)
        self.otavalo.refresh_from_db()
        self.assertEqual(self.otavalo.short_description, "Nueva descripción")
        self.assertFalse(self.otavalo.location_verified)

    def test_coordinates_must_come_in_pairs(self):
        self.client.force_login(self.rep)
        r = self.client.post(reverse("core:edit_community", args=["otavalo"]), {
            "name": "Otavalo", "province": self.otavalo.province.pk, "short_description": "x", "latitude": "1.0"})
        self.assertContains(r, "latitud y longitud juntas")

    def test_rep_content_goes_to_review_and_admin_publishes(self):
        self.client.force_login(self.rep)
        self.client.post(reverse("core:item_create", args=["otavalo", "plato"]),
                         {"name": "Plato X", "description": "Desc", "action": "submit"})
        from culture.models import Dish
        dish = Dish.objects.get(name="Plato X")
        self.assertEqual(dish.status, ReviewStatus.PENDING)
        self.client.force_login(self.admin)
        self.client.post(reverse("core:moderate", args=["plato", dish.pk, "aprobar"]))
        dish.refresh_from_db()
        self.assertEqual(dish.status, ReviewStatus.PUBLISHED)
        self.assertTrue(self.rep.notifications.filter(message__icontains="aprobado").exists())

    # --- Fotografías ---------------------------------------------------------------------
    def test_photo_upload_creates_optimized_card_version(self):
        self.client.force_login(self.rep)
        r = self.client.post(reverse("core:item_create", args=["otavalo", "foto"]), {
            "image": f.image_file(size=(2600, 1700)), "title": "Plaza", "kind": "landscape", "alt_text": "Plaza",
            "author": "Comunidad", "license": "Permiso escrito", "is_featured": "on", "order": 1})
        self.assertEqual(r.status_code, 302)
        p = Photo.objects.get(title="Plaza")
        self.assertTrue(p.card_image)
        self.assertLessEqual(p.card_image.width, Photo.CARD_WIDTH)
        self.assertLessEqual(p.image.width, Photo.MAX_WIDTH)

    def test_photo_rejects_fake_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.rep)
        bad = SimpleUploadedFile("virus.jpg", b"<?php echo 'x'; ?>", content_type="image/jpeg")
        r = self.client.post(reverse("core:item_create", args=["otavalo", "foto"]), {
            "image": bad, "title": "Malo", "kind": "other", "alt_text": "x", "author": "x", "license": "x", "order": 0})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Photo.objects.filter(title="Malo").exists())

    def test_max_three_featured_photos(self):
        for i in range(3):
            Photo.objects.create(community=self.otavalo, image=f.image_file(f"f{i}.jpg"), title=f"F{i}",
                                 alt_text="a", author="a", license="l", is_featured=True, order=i)
        self.client.force_login(self.rep)
        r = self.client.post(reverse("core:item_create", args=["otavalo", "foto"]), {
            "image": f.image_file("f4.jpg"), "title": "F4", "kind": "other", "alt_text": "a", "author": "a",
            "license": "l", "is_featured": "on", "order": 4})
        self.assertContains(r, "ya tiene 3 fotografías destacadas")

    def test_single_cover_photo(self):
        a = Photo.objects.create(community=self.otavalo, image=f.image_file("a.jpg"), title="A", alt_text="a",
                                 author="a", license="l", is_cover=True)
        b = Photo.objects.create(community=self.otavalo, image=f.image_file("b.jpg"), title="B", alt_text="b",
                                 author="a", license="l", is_cover=True)
        a.refresh_from_db()
        self.assertFalse(a.is_cover)
        self.assertTrue(b.is_cover)

    # --- Carrusel de 4 destinos y tarjetas rotativas ------------------------------------
    def test_home_carousel_has_four_slides_without_repeated_photos(self):
        for i, name in enumerate(["Saraguro", "Montecristi"]):
            f.community(name, f.province("Loja") if i == 0 else f.province("Manabí", "costa"), is_demo=True)
        for c in Community.objects.all():
            Photo.objects.create(community=c, image=f.image_file(f"{c.slug}.jpg"), title=c.name, alt_text=c.name,
                                 author="a", license="l", is_cover=True)
        self.client.force_login(self.admin)
        self.client.post(reverse("core:admin_featured"), {"slot_1": self.cuenca.pk, "slot_2": self.otavalo.pk})
        self.assertEqual(Community.objects.get(featured_order=1), self.cuenca)
        r = self.client.get(reverse("core:home"))
        slides = r.context["slides"]
        self.assertEqual(len(slides), 4)
        self.assertEqual(slides[0]["community"], self.cuenca)
        self.assertTrue(slides[2]["is_demo"])  # completado con destinos de demostración identificados
        names = [s["photo"].image.name for s in slides]
        self.assertEqual(len(names), len(set(names)))
        self.assertContains(r, 'data-interval="5000"')
        self.assertContains(r, "data-carousel-toggle")

    def test_featured_form_rejects_duplicates(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("core:admin_featured"), {"slot_1": self.cuenca.pk, "slot_2": self.cuenca.pk})
        self.assertContains(r, "No repita")

    def test_card_rotator_markup(self):
        for i in range(3):
            Photo.objects.create(community=self.otavalo, image=f.image_file(f"r{i}.jpg"), title=f"R{i}", alt_text="r",
                                 author="a", license="l", is_featured=True, order=i)
        Photo.objects.create(community=self.cuenca, image=f.image_file("c.jpg"), title="C", alt_text="c",
                             author="a", license="l", is_featured=True)
        r = self.client.get(reverse("communities:list"))
        html = r.content.decode()
        self.assertEqual(html.count("data-rotator"), 1)  # solo la tarjeta con más de una foto rota
        self.assertEqual(html.count('class="rotator__img'), 4)
        self.assertEqual(html.count("data-src="), 2)  # carga diferida de la 2.ª y 3.ª foto
        from django.contrib.staticfiles import finders
        js = open(finders.find("js/ecuador.js"), encoding="utf-8").read()
        self.assertIn("ROTATE_MS = 3000", js)
        self.assertIn("IntersectionObserver", js)
        self.assertIn("visibilitychange", js)
        self.assertIn("prefers-reduced-motion", js)

    # --- Búsqueda, filtros y favoritos ---------------------------------------------------
    def test_search_and_filters(self):
        r = self.client.get(reverse("communities:list"), {"q": "otav"})
        self.assertEqual([c.name for c in r.context["page"]], ["Otavalo"])
        r = self.client.get(reverse("communities:list"), {"province": "azuay"})
        self.assertEqual([c.name for c in r.context["page"]], ["Cuenca"])
        cat = f.category()
        self.cuenca.categories.add(cat)
        r = self.client.get(reverse("communities:list"), {"category": cat.slug})
        self.assertEqual([c.name for c in r.context["page"]], ["Cuenca"])
        r = self.client.get(reverse("core:search"), {"q": "cuen"})
        self.assertEqual(r.context["total"], 1)

    def test_favorite_toggle(self):
        self.client.force_login(self.tourist)
        url = reverse("communities:favorite", args=["otavalo"])
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json(), {"favorite": True})
        r = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.json(), {"favorite": False})

    def test_community_request_flow(self):
        self.client.force_login(self.tourist)
        self.client.post(reverse("communities:request"), {
            "community_name": "Peguche", "province": self.otavalo.province.pk, "canton": "Otavalo",
            "role_in_community": "Presidente", "message": "Queremos registrarnos"})
        req = self.tourist.community_requests.get()
        self.client.force_login(self.admin)
        self.client.post(reverse("core:request_action", args=[req.pk, "aprobar"]))
        self.tourist.refresh_from_db()
        self.assertEqual(self.tourist.role, User.Role.REPRESENTATIVE)
        self.assertTrue(self.tourist.can_manage_community(Community.objects.get(name="Peguche")))
