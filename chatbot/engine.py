"""Motor del Asistente Turístico Ecuador Cultural.

Responde únicamente con información registrada en PostgreSQL (vía ORM). Si hay una API de IA
configurada, solo la usa para redactar la respuesta a partir de esos mismos datos; nunca para
inventar historia, horarios, precios ni coordenadas.
"""
import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request

from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from communities.models import Community, Province
from culture.models import Craft, CulturalContent, Dish, Festivity
from donations.models import Project
from itineraries.models import Itinerary
from tourism.models import Place

from .models import FAQ

logger = logging.getLogger("ecuador.chatbot")

NUMBER_WORDS = {"un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5}
DEFAULT_SUGGESTIONS = [
    "¿Qué pueblos puedo visitar en Imbabura?",
    "Quiero una ruta cultural de dos días",
    "¿Dónde puedo encontrar artesanías tradicionales?",
    "¿Qué lugares patrimoniales hay en Cuenca?",
    "¿Cómo llego a Otavalo desde Quito?",
    "¿Qué proyectos comunitarios puedo apoyar?",
]


def normalize(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9ñ\s]", " ", text)


def has_any(text, words):
    return any(w in text for w in words)


def _demo(obj):
    return " · dato de demostración" if getattr(obj, "is_demo", False) else ""


class Answer:
    def __init__(self, reply, items=None, intent="fallback"):
        self.reply = reply
        self.items = items or []
        self.intent = intent

    def as_dict(self):
        return {"reply": self.reply, "items": self.items[:6], "intent": self.intent,
                "suggestions": DEFAULT_SUGGESTIONS[:3] if self.intent == "fallback" else []}


def _item(title, url, subtitle="", maps=""):
    return {"title": title, "url": url, "subtitle": subtitle, "maps": maps}


class TourismAssistant:
    def __init__(self, message):
        self.raw = message.strip()[:500]
        self.text = f" {normalize(self.raw)} "
        self.provinces = [p for p in Province.objects.all() if f" {normalize(p.name)} " in self.text]
        communities = Community.objects.published().select_related("province")
        self.communities = [c for c in communities if f" {normalize(c.name)} " in self.text]
        self.places = [p for p in Place.objects.published().select_related("community")
                       if len(p.name) > 4 and normalize(p.name).strip() in self.text]

    # ---------------------------------------------------------------- utilidades de filtro
    def _scope(self, qs, community_field="community"):
        if self.communities:
            return qs.filter(**{f"{community_field}__in": self.communities})
        if self.provinces:
            return qs.filter(**{f"{community_field}__province__in": self.provinces})
        return qs

    def _where(self):
        if self.communities:
            return " en " + ", ".join(c.name for c in self.communities)
        if self.provinces:
            return " en " + ", ".join(p.name for p in self.provinces)
        return ""

    # ---------------------------------------------------------------- intenciones
    def answer(self):
        faq = self.match_faq(strong=True)
        if faq:
            return faq
        t = self.text
        if has_any(t, [" como llego", " como llegar", " llegar a ", " ubicacion", " donde queda", " direccion",
                       " google maps", " gps"]):
            return self.directions()
        if has_any(t, ["proyecto", "donar", "donacion", "apoyar", "aporte", "aportar", "colaborar"]):
            return self.projects()
        if has_any(t, ["ruta", "itinerario", "recorrido", " tour", " dias", " dia "]):
            return self.itineraries()
        if has_any(t, ["comida", "plato", "gastronom", "comer", "tipic", "receta"]):
            return self.dishes()
        if has_any(t, ["artesan", "tejido", "sombrero", "ceramica", "tallado", "joyeria", "bisuteria"]):
            return self.crafts()
        if has_any(t, ["tradicion", "fiesta", "festividad", "costumbre", "celebra", "musica", "danza",
                       "vestimenta"]):
            return self.traditions()
        if has_any(t, ["iglesia", "museo", "cementerio", "patrimon", "historic", "templo", "catedral"]):
            return self.heritage()
        if has_any(t, ["cascada", "parque", "mirador", "naturaleza", "aventura", "sendero"]):
            return self.places_of(Place.NATURE_KINDS, "espacios naturales")
        if has_any(t, ["hotel", "hosped", "dormir", "alojamiento", "restaurante", "donde comer"]):
            return self.places_of(Place.SERVICE_KINDS, "restaurantes y hospedajes")
        if self.provinces or has_any(t, ["pueblo", "comunidad", "visitar", "conocer", "destino"]):
            if self.communities and not self.provinces:
                return self.community_summary()
            return self.towns()
        if self.communities:
            return self.community_summary()
        return self.match_faq(strong=False) or self.fallback()

    def match_faq(self, strong):
        best, best_score = None, 0
        for faq in FAQ.objects.filter(is_active=True):
            score = sum(1 for k in faq.keyword_list() if f"{k}" in self.text)
            if score > best_score:
                best, best_score = faq, score
        if best and best_score >= (2 if strong else 1):
            note = "" if best.is_verified else "\n\n(Respuesta pendiente de verificación por el equipo.)"
            return Answer(best.answer + note, intent="faq")
        return None

    def towns(self):
        qs = Community.objects.published().select_related("province")
        if self.provinces:
            qs = qs.filter(province__in=self.provinces)
        elif self.communities:
            qs = qs.filter(pk__in=[c.pk for c in self.communities])
        items = [_item(c.name, c.get_absolute_url(), f"{c.province.name}{_demo(c)}", c.directions_url)
                 for c in qs.order_by("name")[:6]]
        if not items:
            return Answer(f"Aún no tenemos pueblos publicados{self._where()}. El catálogo crece con aportes "
                          "verificados de las comunidades. Puedes explorar otras provincias en el catálogo.",
                          [_item("Ver catálogo de pueblos", reverse("communities:list"))], "towns")
        return Answer(f"Estos son pueblos registrados{self._where()} que puedes visitar:", items, "towns")

    def community_summary(self):
        c = self.communities[0]
        items = [_item(f"Conocer {c.name}", c.get_absolute_url(), c.province.name, c.directions_url)]
        for p in Place.objects.published().filter(community=c)[:3]:
            items.append(_item(p.name, p.get_absolute_url(), p.get_kind_display(), p.directions_url))
        reply = f"{c.name} ({c.province.name}): {c.short_description}"
        if c.is_demo:
            reply += " (Información de demostración pendiente de verificación.)"
        return Answer(reply, items, "community")

    def directions(self):
        target = self.places[0] if self.places else (self.communities[0] if self.communities else None)
        if target is None:
            return Answer("¿A qué pueblo o lugar quieres llegar? Escribe su nombre, por ejemplo: "
                          "«¿Cómo llego a Otavalo?».", intent="directions")
        if not target.has_location:
            return Answer(f"La ubicación de {target.name} todavía está pendiente de validación, así que no "
                          "puedo darte una ruta precisa. Consulta su página para más detalles.",
                          [_item(target.name, target.get_absolute_url())], "directions")
        origin = ""
        m = re.search(r" desde ([a-z ñ]+?)\s*$", self.text)
        if m:
            origin = f" Google Maps calculará la ruta desde tu ubicación actual (o puedes escribir «{m.group(1).strip().title()}» como punto de partida)."
        warn = "" if target.location_verified else " Ten en cuenta que la ubicación es aproximada y está pendiente de validación."
        return Answer(f"Abre la ruta hacia {target.name} en Google Maps.{origin}{warn}",
                      [_item(f"Cómo llegar a {target.name}", target.get_absolute_url(), "Abrir en Google Maps",
                             target.directions_url)], "directions")

    def itineraries(self):
        qs = Itinerary.objects.published().select_related("province")
        days = None
        m = re.search(r"(\d+)\s*dia", self.text)
        if m:
            days = int(m.group(1))
        else:
            for w, n in NUMBER_WORDS.items():
                if re.search(rf"\b{w}\s+dias?\b", self.text):
                    days = n
        kind_map = {"cultur": "cultural", "gastronom": "gastronomic", "artesan": "crafts",
                    "patrimon": "heritage", "histor": "heritage", "natur": "nature", "aventura": "nature",
                    "iglesia": "churches"}
        kinds = {v for k, v in kind_map.items() if k in self.text}
        if kinds:
            qs = qs.filter(kind__in=kinds)
        if self.provinces:
            qs = qs.filter(Q(province__in=self.provinces) | Q(stops__community__province__in=self.provinces)
                           | Q(stops__place__community__province__in=self.provinces)).distinct()
        if days:
            exact = qs.filter(duration_days=days)
            qs = exact if exact.exists() else qs.filter(duration_days__lte=days)
        items = [_item(i.name, i.get_absolute_url(),
                       f"{i.get_kind_display()} · {i.duration_days} día(s){_demo(i)}") for i in qs[:6]]
        if not items:
            return Answer("No encontré itinerarios publicados con esos criterios. Puedes crear tu propio "
                          "recorrido con los lugares registrados.",
                          [_item("Ver todos los itinerarios", reverse("itineraries:list")),
                           _item("Crear mi recorrido", reverse("itineraries:trips"))], "itineraries")
        desc = f" de {days} día(s)" if days else ""
        return Answer(f"Te recomiendo estos itinerarios{desc}{self._where()}:", items, "itineraries")

    def dishes(self):
        qs = self._scope(Dish.objects.published().select_related("community"))
        items = [_item(d.name, d.get_absolute_url(), f"{d.community.name}{_demo(d)}") for d in qs[:6]]
        if not items:
            return Answer(f"Aún no hay platos documentados{self._where()}.",
                          [_item("Ver gastronomía", reverse("culture:gastronomy"))], "dishes")
        return Answer(f"Platos tradicionales registrados{self._where()}:", items, "dishes")

    def crafts(self):
        qs = self._scope(Craft.objects.published().select_related("community"))
        items = [_item(c.name, c.get_absolute_url(), f"{c.get_kind_display()} · {c.community.name}{_demo(c)}")
                 for c in qs[:6]]
        if not items:
            return Answer(f"Todavía no hay artesanías registradas{self._where()}.",
                          [_item("Ver artesanías", reverse("culture:crafts"))], "crafts")
        return Answer(f"Puedes encontrar estas artesanías tradicionales{self._where()}:", items, "crafts")

    def traditions(self):
        fest = self._scope(Festivity.objects.published().select_related("community"))
        cont = self._scope(CulturalContent.objects.published().select_related("community").exclude(kind="history"))
        items = [_item(f.name, f.get_absolute_url(), f"{f.period or 'Fecha por confirmar'} · {f.community.name}"
                       f"{_demo(f)}") for f in fest[:4]]
        items += [_item(c.title, c.get_absolute_url(), f"{c.get_kind_display()} · {c.community.name}{_demo(c)}")
                  for c in cont[:6 - len(items)]]
        if not items:
            return Answer(f"No hay tradiciones registradas{self._where()} todavía.",
                          [_item("Cultura y tradiciones", reverse("culture:traditions"))], "traditions")
        return Answer(f"Tradiciones y festividades{self._where()}:", items, "traditions")

    def heritage(self):
        kinds = set()
        if "iglesia" in self.text or "templo" in self.text or "catedral" in self.text:
            kinds.add(Place.Kind.CHURCH)
        if "museo" in self.text:
            kinds.add(Place.Kind.MUSEUM)
        if "cementerio" in self.text:
            kinds.add(Place.Kind.CEMETERY)
        return self.places_of(kinds or Place.HERITAGE_KINDS, "lugares patrimoniales")

    def places_of(self, kinds, label):
        qs = Place.objects.published().select_related("community").filter(kind__in=kinds)
        if self.communities:
            qs = qs.filter(Q(community__in=self.communities) | Q(community__canton__name__in=[c.name for c in self.communities]))
        elif self.provinces:
            qs = qs.filter(community__province__in=self.provinces)
        items = [_item(p.name, p.get_absolute_url(), f"{p.get_kind_display()} · {p.community.name}{_demo(p)}",
                       p.directions_url) for p in qs[:6]]
        if not items:
            return Answer(f"No encontré {label} registrados{self._where()}. Prueba en el mapa interactivo.",
                          [_item("Abrir mapa interactivo", reverse("tourism:map"))], "places")
        return Answer(f"Estos son {label}{self._where()}:", items, "places")

    def projects(self):
        qs = self._scope(Project.objects.published().select_related("community")).filter(
            phase__in=[Project.Phase.FUNDRAISING, Project.Phase.IN_PROGRESS])
        items = [_item(p.name, p.get_absolute_url(), f"{p.community.name} · meta ${p.goal_amount:,.0f}{_demo(p)}")
                 for p in qs[:5]]
        how = ("Para apoyar: entra al proyecto, revisa su objetivo y avances, y registra tu aporte con el "
               "comprobante. El aporte se marca como confirmado solo cuando el administrador lo verifica.")
        if not items:
            return Answer("Por ahora no hay proyectos activos" + self._where() + ". " + how,
                          [_item("Ver proyectos comunitarios", reverse("donations:project_list"))], "projects")
        return Answer("Proyectos comunitarios que puedes apoyar" + self._where() + ":\n" + how,
                      items + [_item("Registrar un aporte", reverse("donations:donate"))], "projects")

    def fallback(self):
        return Answer("No encontré información suficiente para responder con datos verificados. Puedo ayudarte "
                      "a buscar pueblos por provincia, platos típicos, artesanías, tradiciones, lugares "
                      "patrimoniales, itinerarios o proyectos comunitarios.",
                      [_item("Explorar pueblos", reverse("communities:list")),
                       _item("Mapa interactivo", reverse("tourism:map"))], "fallback")


def rephrase_with_ai(question, answer):
    """Redacción opcional con IA usando SOLO los datos encontrados. Falla de forma segura."""
    if not settings.CHATBOT_AI_API_KEY or answer.intent == "fallback":
        return answer.reply
    context = {"respuesta_base": answer.reply, "resultados": answer.items}
    payload = {
        "model": settings.CHATBOT_AI_MODEL,
        "max_tokens": 350,
        "system": ("Eres el Asistente Turístico Ecuador Cultural. Responde en español, en 2 a 4 frases, usando "
                   "EXCLUSIVAMENTE los datos JSON proporcionados. No inventes historia, fechas, horarios, precios, "
                   "distancias ni coordenadas. Si un dato es de demostración, dilo. No incluyas URLs."),
        "messages": [{"role": "user", "content": f"Pregunta: {question}\nDatos: {json.dumps(context, ensure_ascii=False)}"}],
    }
    req = urllib.request.Request(
        settings.CHATBOT_AI_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"content-type": "application/json", "x-api-key": settings.CHATBOT_AI_API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return text or answer.reply
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        logger.warning("Servicio de IA no disponible (%s); se usa la respuesta basada en reglas.", type(exc).__name__)
        return answer.reply


def ask(message):
    answer = TourismAssistant(message).answer()
    answer.reply = rephrase_with_ai(message, answer)
    return answer.as_dict()
