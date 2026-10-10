"""Carga datos iniciales de demostración (idempotente: no duplica registros).

Uso:
    python manage.py cargar_datos_demo
    python manage.py cargar_datos_demo --con-usuarios     # crea usuarios de prueba con contraseñas aleatorias
    python manage.py cargar_datos_demo --sin-imagenes     # no genera imágenes marcadoras

Todos los registros quedan marcados como «dato de demostración» (is_demo=True) y con la fuente
«Pendiente de verificación». Las ubicaciones se guardan como NO verificadas. No se crean reseñas
ni donaciones: esos datos solo pueden provenir de usuarios reales.
"""
import secrets
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from chatbot.models import FAQ
from communities.models import (Canton, Category, Community, Photo, Province, Region,
                                RepresentativeAssignment)
from core.models import ReviewStatus
from culture.models import Craft, CulturalContent, Dish, Festivity
from donations.models import Project
from itineraries.models import Itinerary, ItineraryStop
from tourism.models import Place

PENDING = "Pendiente de verificación con la comunidad y fuentes oficiales"

PROVINCES = {
    Region.COSTA: ["Esmeraldas", "Manabí", "Santa Elena", "Guayas", "Los Ríos", "El Oro",
                   "Santo Domingo de los Tsáchilas"],
    Region.SIERRA: ["Carchi", "Imbabura", "Pichincha", "Cotopaxi", "Tungurahua", "Bolívar", "Chimborazo", "Cañar",
                    "Azuay", "Loja"],
    Region.AMAZONIA: ["Sucumbíos", "Orellana", "Napo", "Pastaza", "Morona Santiago", "Zamora Chinchipe"],
    Region.INSULAR: ["Galápagos"],
}

CANTONS = [("Imbabura", "Otavalo"), ("Loja", "Saraguro"), ("Tungurahua", "San Pedro de Pelileo"),
           ("Azuay", "Cuenca"), ("Manabí", "Manta"), ("Manabí", "Montecristi"), ("Carchi", "Tulcán"),
           ("Napo", "Tena"), ("Pichincha", "Quito"), ("Guayas", "Guayaquil")]

CATEGORIES = [
    ("Cultura viva", "bi-people", "Identidad, idioma y costumbres"),
    ("Artesanías", "bi-palette", "Tejidos, cerámica, sombreros y más"),
    ("Gastronomía", "bi-egg-fried", "Sabores tradicionales"),
    ("Patrimonio", "bi-bank2", "Iglesias, museos y sitios históricos"),
    ("Naturaleza", "bi-tree", "Cascadas, miradores y senderos"),
    ("Festividades", "bi-calendar-heart", "Celebraciones y fiestas tradicionales"),
    ("Turismo comunitario", "bi-house-heart", "Experiencias gestionadas por comunidades"),
]

# Coordenadas de referencia del centro poblado (aproximadas, guardadas como NO verificadas).
# None = ubicación pendiente de validación (se muestra así en la interfaz).
COMMUNITIES = [
    dict(name="Otavalo", province="Imbabura", canton="Otavalo", lat="0.234300", lng="-78.261100", photos=3,
         cats=["Artesanías", "Cultura viva", "Festividades"], featured=1,
         short="Ciudad andina de Imbabura conocida por su tradición textil, su plaza artesanal y la cultura del pueblo kichwa Otavalo."),
    dict(name="Cuenca", province="Azuay", canton="Cuenca", lat="-2.900100", lng="-79.005900", photos=3,
         cats=["Patrimonio", "Gastronomía", "Artesanías"], featured=2,
         short="Ciudad de la Sierra sur cuyo centro histórico integra la lista de Patrimonio Mundial de la UNESCO."),
    dict(name="Saraguro", province="Loja", canton="Saraguro", lat="-3.620600", lng="-79.237300", photos=3,
         cats=["Cultura viva", "Artesanías", "Turismo comunitario"], featured=3,
         short="Territorio del pueblo kichwa Saraguro en la provincia de Loja, reconocido por su vestimenta y su bisutería tradicional."),
    dict(name="Montecristi", province="Manabí", canton="Montecristi", lat="-1.045900", lng="-80.658700", photos=2,
         cats=["Artesanías", "Patrimonio"], featured=4,
         short="Cantón manabita asociado al tejido tradicional del sombrero de paja toquilla."),
    dict(name="Salasaca", province="Tungurahua", canton="San Pedro de Pelileo", parish="Salasaca", lat=None, lng=None,
         photos=2, cats=["Artesanías", "Cultura viva"],
         short="Comunidad kichwa de Tungurahua conocida por sus tapices elaborados en telar."),
    dict(name="Ligüiqui", province="Manabí", canton="Manta", lat=None, lng=None, photos=1,
         cats=["Turismo comunitario", "Naturaleza"],
         short="Comunidad costera de Manabí. Su historia y atractivos están pendientes de documentación por la propia comunidad."),
    dict(name="Tulcán", province="Carchi", canton="Tulcán", lat="0.811800", lng="-77.717300", photos=3,
         cats=["Patrimonio"],
         short="Ciudad fronteriza del norte del país, conocida por las figuras de ciprés podadas de su cementerio."),
    dict(name="Puerto Misahuallí", province="Napo", canton="Tena", parish="Misahuallí", lat="-1.035300",
         lng="-77.665800", photos=0, cats=["Naturaleza", "Turismo comunitario"],
         short="Parroquia amazónica a orillas del río Napo, punto de partida hacia comunidades kichwa de la Amazonía."),
]

PLACES = [
    dict(c="Otavalo", name="Plaza de los Ponchos", kind=Place.Kind.MARKET, lat="0.235300", lng="-78.262200",
         desc="Plaza central de comercio artesanal de Otavalo, con textiles, bisutería y otras artesanías."),
    dict(c="Otavalo", name="Cascada de Peguche", kind=Place.Kind.WATERFALL, lat="0.244800", lng="-78.238400",
         desc="Cascada cercana a Otavalo, rodeada de un bosque protector y vinculada a celebraciones tradicionales."),
    dict(c="Cuenca", name="Catedral de la Inmaculada Concepción", kind=Place.Kind.CHURCH, lat="-2.897500",
         lng="-79.004900", desc="Conocida como Catedral Nueva, frente al Parque Calderón; sus cúpulas son un símbolo de la ciudad.",
         rules="Respeta los horarios de culto y guarda silencio en el interior."),
    dict(c="Cuenca", name="Museo Pumapungo", kind=Place.Kind.MUSEUM, lat=None, lng=None,
         desc="Museo con salas de etnografía, arqueología y arte. Ubicación exacta pendiente de validación en la plataforma."),
    dict(c="Tulcán", name="Cementerio José María Azael Franco", kind=Place.Kind.CEMETERY, lat="0.816700",
         lng="-77.720300", desc="Cementerio con figuras talladas en arbustos de ciprés, considerado un atractivo patrimonial de Tulcán.",
         rules="Es un espacio de memoria: camina por los senderos señalizados y respeta a las familias visitantes."),
    dict(c="Puerto Misahuallí", name="Malecón de Puerto Misahuallí", kind=Place.Kind.ATTRACTION, lat=None, lng=None,
         desc="Paseo junto al río. Información y ubicación pendientes de validación por la comunidad."),
]

DISHES = [
    dict(c="Cuenca", name="Mote pillo", ingredients="Mote, huevo, cebolla blanca, leche y achiote (por confirmar con fuentes locales).",
         desc="Preparación tradicional de la Sierra sur a base de mote salteado con huevo."),
    dict(c="Montecristi", name="Corviche", ingredients="Masa de plátano verde con relleno de pescado y maní (por confirmar).",
         desc="Bocado frito típico de la gastronomía manabita."),
]

CRAFTS = [
    dict(c="Otavalo", name="Tejidos de Otavalo", kind=Craft.Kind.TEXTILE, materials="Lana y fibras sintéticas (por confirmar).",
         desc="Tejidos en telar y prendas comercializadas en la plaza artesanal."),
    dict(c="Montecristi", name="Sombrero de paja toquilla", kind=Craft.Kind.HAT, materials="Fibra de paja toquilla.",
         desc="Tejido tradicional del sombrero de paja toquilla; la técnica figura en la lista de Patrimonio Cultural Inmaterial de la UNESCO."),
    dict(c="Salasaca", name="Tapices de Salasaca", kind=Craft.Kind.TEXTILE, materials="Lana (por confirmar).",
         desc="Tapices tejidos en telar con diseños propios de la comunidad."),
    dict(c="Saraguro", name="Bisutería de mullos", kind=Craft.Kind.JEWELRY, materials="Mullos (cuentas de vidrio o plástico).",
         desc="Collares y accesorios elaborados con mullos, parte de la vestimenta tradicional."),
]

FESTIVITIES = [
    dict(c="Otavalo", name="Inti Raymi", period="Alrededor del solsticio de junio",
         desc="Celebración andina vinculada al sol y a las cosechas, con música y danza.",
         tips="Participa con respeto: algunos rituales son comunitarios y no siempre se permite fotografiar."),
    dict(c="Cuenca", name="Pase del Niño Viajero", period="24 de diciembre",
         desc="Desfile tradicional navideño de Cuenca con carros alegóricos y personajes populares.",
         tips="Llega temprano y respeta los espacios del desfile."),
]

CONTENTS = [
    dict(c="Otavalo", kind=CulturalContent.Kind.IDENTITY, title="Identidad del pueblo kichwa Otavalo",
         desc="Texto de demostración. La comunidad debe completar esta sección con información documentada y su fuente."),
    dict(c="Saraguro", kind=CulturalContent.Kind.CLOTHING, title="Vestimenta tradicional saraguro",
         desc="Texto de demostración. La vestimenta tradicional es un elemento de identidad; detalles pendientes de documentación por la comunidad."),
]

ITINERARIES = [
    dict(name="Ruta artesanal de Otavalo", kind=Itinerary.Kind.CRAFTS, province="Imbabura", days=1, community="Otavalo",
         desc="Recorrido de un día por la plaza artesanal y la cascada de Peguche.",
         stops=[("place", "Plaza de los Ponchos"), ("place", "Cascada de Peguche")]),
    dict(name="Cuenca patrimonial", kind=Itinerary.Kind.HERITAGE, province="Azuay", days=1, community="Cuenca",
         desc="Caminata por el centro histórico de Cuenca y visita a un museo.",
         stops=[("place", "Catedral de la Inmaculada Concepción"), ("place", "Museo Pumapungo")]),
    dict(name="Recorrido textil por la Sierra", kind=Itinerary.Kind.MULTI, province=None, days=3, community=None,
         desc="Ruta de varios días para conocer pueblos con tradición textil y artesanal.",
         stops=[("community", "Otavalo"), ("community", "Salasaca"), ("community", "Saraguro")]),
    dict(name="Ruta cultural de dos días en Imbabura y Carchi", kind=Itinerary.Kind.CULTURAL, province="Imbabura",
         days=2, community=None, desc="Artesanías de Otavalo y patrimonio funerario de Tulcán.",
         stops=[("place", "Plaza de los Ponchos"), ("place", "Cementerio José María Azael Franco")]),
]

PROJECTS = [
    dict(c="Salasaca", name="Taller de telar para jóvenes", goal="1500.00",
         desc="Proyecto de demostración: no recibe aportes reales.",
         obj="Ejemplo de objetivo: transmitir la técnica de tejido en telar a nuevas generaciones."),
    dict(c="Saraguro", name="Registro de memoria oral", goal="800.00",
         desc="Proyecto de demostración: no recibe aportes reales.",
         obj="Ejemplo de objetivo: documentar relatos de personas mayores con autorización de la comunidad."),
    dict(c="Puerto Misahuallí", name="Señalética de senderos comunitarios", goal="2000.00",
         desc="Proyecto de demostración: no recibe aportes reales.",
         obj="Ejemplo de objetivo: instalar señalética informativa en senderos."),
]

FAQS = [
    ("¿Cómo puedo apoyar a una comunidad?", "apoyar,donar,aporte,ayudar,colaborar",
     "Entra a «Proyectos comunitarios», elige un proyecto y revisa su objetivo y avances. Realiza el aporte con las "
     "instrucciones publicadas y registra el monto y el comprobante en la plataforma. El administrador lo confirma "
     "cuando verifica la recepción con la comunidad.", True),
    ("¿Qué significa «dato de demostración»?", "demostracion,demo,verificado,verificacion",
     "Son registros de ejemplo que aún no han sido verificados con la comunidad ni con fuentes oficiales. Se "
     "reemplazan o confirman a medida que las comunidades publican su información.", True),
    ("¿Cómo registro mi comunidad?", "registrar,comunidad,representante,inscribir",
     "Crea una cuenta, entra a «Registrar mi comunidad» y envía la solicitud. Cuando el administrador la apruebe "
     "podrás administrar la información, fotografías y proyectos de tu comunidad.", True),
    ("¿Cómo creo mi propio recorrido?", "crear,recorrido,personalizado,mi ruta,planificar",
     "Inicia sesión y entra a «Mis recorridos». Crea un recorrido, agrega lugares o pueblos, asígnales fechas y "
     "reordénalos. También puedes copiar un itinerario recomendado y personalizarlo.", True),
    ("¿Guardan mis conversaciones con el asistente?", "historial,privacidad,conversacion,guardar",
     "Las conversaciones de visitantes no se guardan. Si tienes cuenta, puedes activar «Guardar mi historial» y "
     "eliminarlo cuando quieras desde el asistente o tu perfil.", True),
]


def placeholder_image(title, index, total, seed):
    """Imagen marcadora claramente rotulada (no es una fotografía real del lugar)."""
    w, h = 1600, 1000
    palettes = [((31, 77, 58), (127, 176, 105)), ((138, 75, 22), (217, 164, 65)), ((20, 53, 40), (79, 138, 91)),
                ((42, 98, 73), (181, 101, 29)), ((60, 90, 110), (150, 180, 160))]
    top, bottom = palettes[(seed + index) % len(palettes)]
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    shade = tuple(max(0, c - 35) for c in top)
    offset = (seed * 97 + index * 211) % 400
    draw.polygon([(0, 760), (300 + offset, 380), (620 + offset, 640), (980, 300 + offset // 3), (1600, 720),
                  (1600, 1000), (0, 1000)], fill=shade)
    draw.polygon([(0, 880), (500, 640), (900, 820), (1300, 600), (1600, 860), (1600, 1000), (0, 1000)],
                 fill=tuple(max(0, c - 60) for c in top))
    font = None
    for path in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        try:
            font = ImageFont.truetype(path, 28)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=28)
        except TypeError:  # Pillow antiguo
            font = ImageFont.load_default()
    label = f"IMAGEN DE DEMOSTRACIÓN · {title} {index}/{total}"
    box = draw.textbbox((0, 0), label, font=font)
    x, y = (w - (box[2] - box[0])) // 2, 60
    draw.rounded_rectangle([(x - 24, y - 14), (x + (box[2] - box[0]) + 24, y + (box[3] - box[1]) + 20)], radius=18,
                           fill=(255, 255, 255))
    draw.text((x, y), label, fill=(138, 75, 22), font=font)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=82)
    return ContentFile(buf.getvalue(), name=f"{slugify(title)}-demo-{index}.jpg")


class Command(BaseCommand):
    help = "Carga datos iniciales de demostración claramente identificados (sin duplicados)."

    def add_arguments(self, parser):
        parser.add_argument("--con-usuarios", action="store_true", help="Crear usuarios de prueba (contraseñas aleatorias)")
        parser.add_argument("--sin-imagenes", action="store_true", help="No generar imágenes marcadoras")

    @transaction.atomic
    def handle(self, *args, **opts):
        now = timezone.now()
        common = dict(is_demo=True, source=PENDING, status=ReviewStatus.PUBLISHED, published_at=now)

        for region, names in PROVINCES.items():
            for name in names:
                Province.objects.get_or_create(slug=slugify(name), defaults={"name": name, "region": region})
        provinces = {p.name: p for p in Province.objects.all()}
        for prov, name in CANTONS:
            Canton.objects.get_or_create(province=provinces[prov], name=name)
        for i, (name, icon, desc) in enumerate(CATEGORIES):
            Category.objects.get_or_create(slug=slugify(name), defaults={"name": name, "icon": icon,
                                                                         "description": desc, "order": i})
        cats = {c.name: c for c in Category.objects.all()}

        communities = {}
        created_photos = 0
        for seed, d in enumerate(COMMUNITIES):
            prov = provinces[d["province"]]
            canton = Canton.objects.filter(province=prov, name=d["canton"]).first()
            c, created = Community.objects.get_or_create(slug=slugify(d["name"]), defaults=dict(
                name=d["name"], province=prov, canton=canton, parish=d.get("parish", ""), short_description=d["short"],
                latitude=d["lat"], longitude=d["lng"], location_verified=False, **common))
            if created:
                c.categories.set([cats[x] for x in d["cats"]])
                if d.get("featured") and not Community.objects.filter(featured_order=d["featured"]).exists():
                    c.featured_order = d["featured"]
                    c.save(update_fields=["featured_order"])
            communities[d["name"]] = c
            if not opts["sin_imagenes"] and not c.photos.exists():
                for i in range(1, d["photos"] + 1):
                    Photo.objects.create(
                        community=c, image=placeholder_image(c.name, i, d["photos"], seed),
                        title=f"{c.name} · marcador {i}", alt_text=f"Imagen de demostración {i} para {c.name}",
                        author="Ecuador Cultural (marcador)", license="Marcador de demostración, sin fotografía real",
                        source="Generado automáticamente", is_featured=True, is_cover=(i == 1), is_placeholder=True,
                        order=i)
                    created_photos += 1

        places = {}
        for d in PLACES:
            p, _ = Place.objects.get_or_create(name=d["name"], community=communities[d["c"]], defaults=dict(
                kind=d["kind"], description=d["desc"], latitude=d["lat"], longitude=d["lng"],
                visiting_rules=d.get("rules", ""), location_verified=False, **common))
            places[d["name"]] = p

        for d in DISHES:
            Dish.objects.get_or_create(name=d["name"], community=communities[d["c"]], defaults=dict(
                description=d["desc"], ingredients=d["ingredients"], **common))
        for d in CRAFTS:
            Craft.objects.get_or_create(name=d["name"], community=communities[d["c"]], defaults=dict(
                kind=d["kind"], description=d["desc"], materials=d["materials"], **common))
        for d in FESTIVITIES:
            Festivity.objects.get_or_create(name=d["name"], community=communities[d["c"]], defaults=dict(
                description=d["desc"], period=d["period"], visitor_tips=d["tips"], **common))
        for d in CONTENTS:
            CulturalContent.objects.get_or_create(title=d["title"], community=communities[d["c"]], defaults=dict(
                kind=d["kind"], description=d["desc"], **common))

        for d in ITINERARIES:
            it, created = Itinerary.objects.get_or_create(slug=slugify(d["name"]), defaults=dict(
                name=d["name"], kind=d["kind"], description=d["desc"], duration_days=d["days"],
                province=provinces.get(d["province"]) if d["province"] else None,
                community=communities.get(d["community"]) if d["community"] else None,
                recommendations="Itinerario de demostración: confirma horarios, distancias y costos antes de viajar.",
                **common))
            if created:
                for order, (kind, name) in enumerate(d["stops"], start=1):
                    ItineraryStop.objects.create(
                        itinerary=it, order=order, day=min(order, d["days"]),
                        place=places[name] if kind == "place" else None,
                        community=communities[name] if kind == "community" else None,
                        travel_time_note="Tiempo pendiente de confirmación" if order > 1 else "")

        for d in PROJECTS:
            Project.objects.get_or_create(slug=slugify(d["name"]), defaults=dict(
                name=d["name"], community=communities[d["c"]], description=d["desc"], objective=d["obj"],
                goal_amount=Decimal(d["goal"]), start_date=date.today(), responsible_name="Por designar por la comunidad",
                **common))

        for i, (q, kw, a, verified) in enumerate(FAQS):
            FAQ.objects.get_or_create(question=q, defaults=dict(keywords=kw, answer=a, is_verified=verified, order=i,
                                                                show_as_suggestion=i < 2,
                                                                source="Equipo Ecuador Cultural"))

        self.stdout.write(self.style.SUCCESS(
            f"Datos de demostración listos: {Community.objects.count()} comunidades, {Place.objects.count()} lugares, "
            f"{Itinerary.objects.count()} itinerarios, {Project.objects.count()} proyectos, "
            f"{created_photos} imágenes marcadoras nuevas."))

        if opts["con_usuarios"]:
            self._demo_users(communities)

    def _demo_users(self, communities):
        User = get_user_model()
        specs = [("admin_demo", User.Role.ADMIN, True), ("representante_demo", User.Role.REPRESENTATIVE, False),
                 ("turista_demo", User.Role.TOURIST, False)]
        self.stdout.write("\nUsuarios de prueba (guarda estas contraseñas; no se vuelven a mostrar):")
        for username, role, staff in specs:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  {username}: ya existía (contraseña sin cambios)")
                continue
            password = secrets.token_urlsafe(10)
            user = User.objects.create_user(username=username, email=f"{username}@ejemplo.local", password=password,
                                            role=role, is_staff=staff, is_superuser=staff,
                                            first_name=username.split("_")[0].capitalize())
            if role == User.Role.REPRESENTATIVE:
                for name in ("Otavalo", "Saraguro"):
                    RepresentativeAssignment.objects.get_or_create(user=user, community=communities[name])
            self.stdout.write(f"  {username} ({user.get_role_display()}): {password}")
