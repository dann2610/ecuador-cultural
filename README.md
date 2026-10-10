# Ecuador Cultural

**Descubre nuestras raíces, vive nuestras tradiciones.**

Plataforma web turística, cultural y comunitaria para visibilizar pueblos y comunidades del Ecuador. Los visitantes descubren pueblos, consultan fotografías y mapas, arman itinerarios, conversan con un asistente turístico, publican reseñas y apoyan proyectos comunitarios. Los representantes administran la información de sus comunidades y el administrador revisa y publica.

Tecnologías: Python 3.11+ · Django 5.2 · PostgreSQL 14+ · Bootstrap 5 · Leaflet + OpenStreetMap · Google Maps (enlaces de navegación).

---

## 1. Instalación en Windows (paso a paso)

### 1.1 Requisitos

1. **Python 3.11 o superior** desde https://www.python.org/downloads/ (marca «Add Python to PATH» al instalar).
2. **PostgreSQL 14 o superior** desde https://www.postgresql.org/download/windows/ (anota la contraseña del usuario `postgres`; incluye pgAdmin).
3. **Git** (opcional) y **VS Code**.

### 1.2 Crear la base de datos en PostgreSQL

Abre **SQL Shell (psql)** (o pgAdmin → Query Tool) con el usuario `postgres` y ejecuta:

```sql
CREATE USER ecuador WITH PASSWORD 'tu_contraseña_segura';
CREATE DATABASE ecuador_cultural OWNER ecuador ENCODING 'UTF8';
ALTER USER ecuador CREATEDB;  -- necesario solo para ejecutar las pruebas automatizadas
```

### 1.3 Preparar el proyecto

Abre una terminal (PowerShell) en la carpeta del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
# Si PowerShell bloquea el script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` y coloca al menos `DJANGO_SECRET_KEY` y `DB_PASSWORD`. Para generar una clave:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 1.4 Migraciones, superusuario y datos iniciales

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py cargar_datos_demo
python manage.py runserver
```

Abre http://127.0.0.1:8000/

El superusuario creado con `createsuperuser` ya tiene permisos de **Administrador** de la plataforma. Para probar los cuatro perfiles puedes generar usuarios de demostración con contraseñas aleatorias (se muestran una sola vez en la consola):

```powershell
python manage.py cargar_datos_demo --con-usuarios
```

Crea `admin_demo`, `representante_demo` (asignado a Otavalo y Saraguro) y `turista_demo`.

### 1.5 Ejecutar las pruebas

```powershell
python manage.py test
```

Las 49 pruebas se ejecutan contra PostgreSQL (Django crea y elimina una base temporal `test_ecuador_cultural`, por eso el usuario necesita `CREATEDB`).

---

## 2. Datos iniciales y política de veracidad

`cargar_datos_demo` es idempotente (no duplica registros) y carga: las 24 provincias del Ecuador con su región, cantones de ejemplo, categorías, 8 pueblos de Costa, Sierra y Amazonía (Otavalo, Cuenca, Saraguro, Montecristi, Salasaca, Ligüiqui, Tulcán, Puerto Misahuallí), lugares, platos, artesanías, festividades, 4 itinerarios, 3 proyectos y preguntas frecuentes del chatbot.

* Todo queda marcado como **«Demostración»** (`is_demo=True`) y con fuente «Pendiente de verificación».
* Las coordenadas son referencias aproximadas guardadas como **no verificadas**; algunos registros (Salasaca, Ligüiqui, Museo Pumapungo) se dejan **sin coordenadas** para mostrar el estado «Ubicación pendiente de validación».
* Las imágenes son **marcadores generados** y rotulados como «Imagen de demostración», nunca fotografías presentadas como reales. Reemplázalas desde el panel por fotografías con licencia o permiso.
* No se crean reseñas ni donaciones: solo pueden venir de usuarios reales.
* `--sin-imagenes` evita generar marcadores.

---

## 3. Roles y permisos

| Rol | Qué puede hacer |
|---|---|
| **Visitante** | Ver pueblos, fotografías, mapa, itinerarios, cultura, proyectos y reseñas; usar el chatbot. |
| **Turista registrado** | Perfil, favoritos, recorridos personalizados, reseñas, registrar y consultar sus aportes, solicitar el registro de su comunidad. |
| **Representante comunitario** | Solo en sus comunidades asignadas: editar información, subir/ordenar fotografías, contenidos culturales, lugares, servicios, proyectos, avances e itinerarios propuestos; ver donaciones de sus proyectos. Lo que crea queda en borrador o pendiente de revisión. |
| **Administrador** | Todo lo anterior en cualquier comunidad, moderación, publicación, carrusel, usuarios y roles, verificación de donaciones, reseñas, auditoría. |

Los permisos se validan en el **backend** (`accounts/permissions.py`, `User.can_manage_community`), no solo ocultando botones. Un representante que intenta editar otra comunidad recibe 403.

Flujo editorial: el representante guarda en *borrador* o *envía a revisión* → el administrador *aprueba y publica* o *rechaza con observación* → se notifica al autor. Las ediciones de un representante sobre contenido ya publicado se mantienen publicadas, quedan en la auditoría y se notifica al administrador.

---

## 4. Funcionalidades clave

* **Carrusel principal**: exactamente 4 destinos elegidos en *Panel → Carrusel*; cambia cada 5 s, flechas, indicadores, botón de pausa, se detiene con la pestaña oculta y respeta *reducir movimiento*. Si faltan destinos se completa con destinos de demostración identificados; nunca repite una fotografía.
* **Tarjetas con fotos rotativas**: hasta 3 fotografías destacadas por pueblo, fundido cada 3 s sin controles. Un solo temporizador compartido, solo rotan las tarjetas visibles (`IntersectionObserver`), pausa con la pestaña oculta, carga diferida y precarga de la siguiente imagen, versión liviana de 720 px generada al subir la foto.
* **Mapa** (`/mapa/`): marcadores desde PostgreSQL (`/api/mapa/`), filtros por categoría, búsqueda, ventanas informativas, «Cómo llegar» con `https://www.google.com/maps/dir/?api=1&destination=LAT,LNG` y GPS solo con permiso explícito.
* **Itinerarios**: búsqueda por provincia, duración, categoría y presupuesto; mapa con la ruta; ruta completa en Google Maps; recorridos personalizados con agregar, eliminar, reordenar (flechas o arrastrar y soltar), fechas y mapa.
* **Reseñas**: 1 a 5 estrellas, una por usuario y lugar, foto opcional, promedio, moderación (ocultar/publicar/eliminar).
* **Proyectos y donaciones**: total confirmado calculado solo con aportes verificados; ninguna donación se confirma sola (restricción en la base de datos); se rechazan referencias con forma de número de tarjeta; campos reservados para una futura pasarela de pagos.
* **Chatbot**: consulta la base de datos con reglas (pueblos por provincia, tradiciones, platos, artesanías, patrimonio, itinerarios por días, cómo llegar, proyectos, preguntas frecuentes). Reconoce cuando no tiene información. Historial opcional y eliminable.

---

## 5. Integraciones externas

| Integración | Uso | Configuración |
|---|---|---|
| OpenStreetMap | Teselas del mapa (Leaflet). | Sin clave. Respeta la atribución incluida. |
| Google Maps | Solo enlaces «Cómo llegar» (no usa API de pago). | Sin clave. |
| Google Fonts | Tipografías Fraunces y Source Sans 3. | Sin clave; si no hay internet se usan fuentes del sistema. |
| IA para el chatbot (opcional) | Redacta la respuesta usando **solo** los datos encontrados en la base. | `CHATBOT_AI_API_KEY`, `CHATBOT_AI_MODEL`, `CHATBOT_AI_URL` en `.env`. Sin clave funciona por reglas. La clave nunca llega al navegador. |
| Correo SMTP | Recuperación de contraseña. | Variables `EMAIL_*`. En desarrollo el correo se imprime en la consola. |

Bootstrap, Bootstrap Icons y Leaflet están incluidos en `static/vendor/`, por lo que la interfaz funciona sin CDN.

---

## 6. Estructura

```
config/          settings, urls
accounts/        usuario personalizado con roles, registro, login, perfil, permisos
communities/     provincias, cantones, categorías, pueblos, representantes, fotografías, favoritos, solicitudes
culture/         contenidos culturales, gastronomía, artesanías, festividades
tourism/         lugares (iglesias, cementerios, museos, restaurantes…), servicios, mapa
itineraries/     itinerarios, paradas, favoritos, recorridos personalizados
reviews/         reseñas y valoraciones
donations/       proyectos, avances, donaciones
chatbot/         motor del asistente, preguntas frecuentes, conversaciones
core/            inicio, búsqueda, paneles, moderación, auditoría, notificaciones, datos demo
templates/       plantillas Django
static/          css, js, vendor, img
```

Arquitectura MVT en tres capas: presentación (plantillas, Bootstrap, JS), lógica de negocio (vistas, `selectors.py`, `services.py`, `permissions.py`, formularios) y datos (modelos, ORM, PostgreSQL con claves foráneas, restricciones `CHECK`/`UNIQUE` e índices).

El panel técnico de Django (`/admin/`) sigue disponible para gestionar categorías, preguntas frecuentes y datos maestros.

---

## 7. Copias de seguridad

```powershell
# Respaldo (base de datos)
pg_dump -U ecuador -h localhost -F c -f respaldo_ecuador_%DATE:~-4%.dump ecuador_cultural
# Restauración
pg_restore -U ecuador -h localhost -d ecuador_cultural --clean respaldo_ecuador_2026.dump
```

Respalda también la carpeta `media/` (fotografías y comprobantes).

---

## 8. Producción (resumen)

`DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` con tu dominio, `DJANGO_SECURE_COOKIES=True`, `DJANGO_SSL_REDIRECT=True`, `python manage.py collectstatic`, servir con Gunicorn/Waitress detrás de Nginx o IIS y servir `media/` desde el servidor web.

## 9. Pendiente para siguientes versiones

* Integración real con una pasarela de pagos (campos `gateway_payload_id` y método `gateway` ya reservados).
* Importador CSV de comunidades y lugares verificados.
* Reemplazar los datos de demostración por información y fotografías autorizadas por cada comunidad.
* Ajustar la política de privacidad a la LOPDP antes de publicar.
