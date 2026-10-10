/* Ecuador Cultural · comportamiento de la interfaz */
(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : "";
  }
  window.ecCsrf = () => getCookie("csrftoken");

  /* ------------------------------------------------------------------
     1. Carrusel principal: 4 diapositivas, cambio cada 5 s, pausa manual
     ------------------------------------------------------------------ */
  function initHeroCarousel() {
    const el = document.getElementById("heroCarousel");
    if (!el || !window.bootstrap) return;
    const interval = parseInt(el.dataset.interval || "5000", 10);
    const carousel = new bootstrap.Carousel(el, {
      interval: interval, ride: reduceMotion ? false : "carousel", pause: false, touch: true, keyboard: true,
    });
    const btn = el.querySelector("[data-carousel-toggle]");
    let playing = !reduceMotion;
    const render = () => {
      if (!btn) return;
      btn.innerHTML = playing ? '<i class="bi bi-pause-fill"></i>' : '<i class="bi bi-play-fill"></i>';
      btn.setAttribute("aria-pressed", String(!playing));
      btn.setAttribute("aria-label", playing ? "Pausar carrusel" : "Reanudar carrusel");
    };
    if (btn) {
      btn.addEventListener("click", () => {
        playing = !playing;
        playing ? carousel.cycle() : carousel.pause();
        render();
      });
    }
    if (playing) carousel.cycle();
    document.addEventListener("visibilitychange", () => {
      if (!playing) return;
      document.hidden ? carousel.pause() : carousel.cycle();
    });
    render();
  }

  /* ------------------------------------------------------------------
     2. Fotografías rotativas en tarjetas (cada 3 s, sin controles).
        Un solo temporizador compartido; solo rota tarjetas visibles;
        se pausa con la pestaña oculta; carga diferida de las siguientes.
     ------------------------------------------------------------------ */
  const ROTATE_MS = 3000;
  const visibleRotators = new Set();
  let rotateTimer = null;

  function loadImg(img) {
    if (img && img.dataset.src && !img.getAttribute("src")) {
      img.src = img.dataset.src;
      img.removeAttribute("data-src");
    }
  }

  function tick() {
    visibleRotators.forEach((rot) => {
      const imgs = rot.querySelectorAll(".rotator__img");
      if (imgs.length < 2) return;
      let idx = parseInt(rot.dataset.index || "0", 10);
      const next = (idx + 1) % imgs.length;
      const nextImg = imgs[next];
      loadImg(nextImg);
      if (!nextImg.complete) return; // espera a que la imagen esté lista: sin saltos ni solicitudes repetidas
      imgs[idx].classList.remove("is-active");
      nextImg.classList.add("is-active");
      rot.dataset.index = String(next);
      loadImg(imgs[(next + 1) % imgs.length]); // precarga la siguiente
    });
  }

  function startRotation() {
    if (!rotateTimer && visibleRotators.size && !document.hidden) rotateTimer = setInterval(tick, ROTATE_MS);
  }
  function stopRotation() {
    if (rotateTimer) { clearInterval(rotateTimer); rotateTimer = null; }
  }

  function initRotators() {
    const rotators = document.querySelectorAll("[data-rotator]");
    if (!rotators.length || reduceMotion) return; // con movimiento reducido la foto queda fija
    if (!("IntersectionObserver" in window)) {
      rotators.forEach((r) => visibleRotators.add(r));
      startRotation();
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          visibleRotators.add(e.target);
          loadImg(e.target.querySelectorAll(".rotator__img")[1]);
        } else {
          visibleRotators.delete(e.target);
        }
      });
      visibleRotators.size ? startRotation() : stopRotation();
    }, { rootMargin: "100px" });
    rotators.forEach((r) => io.observe(r));
    document.addEventListener("visibilitychange", () => (document.hidden ? stopRotation() : startRotation()));
  }

  /* ------------------------------------------------------------------
     3. Favoritos sin recargar la página
     ------------------------------------------------------------------ */
  function initFavorites() {
    document.addEventListener("submit", async (ev) => {
      const form = ev.target.closest(".js-fav");
      if (!form) return;
      ev.preventDefault();
      try {
        const resp = await fetch(form.action, {
          method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!resp.ok) throw new Error();
        const data = await resp.json();
        const btn = form.querySelector("button");
        const icon = btn.querySelector("i");
        btn.classList.toggle("is-fav", data.favorite);
        btn.setAttribute("aria-pressed", String(data.favorite));
        icon.className = data.favorite ? "bi bi-heart-fill" : "bi bi-heart";
        const label = btn.querySelector("span");
        if (label) label.textContent = data.favorite ? "En favoritos" : "Guardar en favoritos";
      } catch (e) {
        form.submit();
      }
    });
  }

  /* ------------------------------------------------------------------
     4. Compartir
     ------------------------------------------------------------------ */
  function initShare() {
    document.querySelectorAll("[data-share]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const data = { title: btn.dataset.title || document.title, text: btn.dataset.text || "", url: location.href };
        if (navigator.share) {
          try { await navigator.share(data); } catch (e) { /* cancelado */ }
        } else if (navigator.clipboard) {
          await navigator.clipboard.writeText(location.href);
          btn.innerHTML = '<i class="bi bi-check2"></i> Enlace copiado';
        }
      });
    });
  }

  /* ------------------------------------------------------------------
     5. Mapas con Leaflet + OpenStreetMap (datos desde la base de datos)
     ------------------------------------------------------------------ */
  const KIND_STYLE = {
    community: ["#1f4d3a", "bi-people-fill"], attraction: ["#4f8a5b", "bi-star-fill"],
    church: ["#7a3e9d", "bi-bank2"], cemetery: ["#5f6b63", "bi-flower1"], museum: ["#8a4b16", "bi-building"],
    historic: ["#b5651d", "bi-hourglass-split"], park: ["#2e7d32", "bi-tree-fill"], waterfall: ["#1e88e5", "bi-droplet-fill"],
    viewpoint: ["#00897b", "bi-binoculars-fill"], restaurant: ["#d84315", "bi-cup-hot-fill"],
    lodging: ["#3949ab", "bi-house-door-fill"], market: ["#c2185b", "bi-shop"], stop: ["#d9a441", "bi-signpost-split-fill"],
  };

  function markerIcon(kind, verified, label) {
    const [color, icon] = KIND_STYLE[kind] || ["#1f4d3a", "bi-geo-alt-fill"];
    const inner = label ? `<b>${label}</b>` : `<i class="bi ${icon}"></i>`;
    return L.divIcon({
      className: "", iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -28],
      html: `<div class="map-marker${verified ? "" : " unverified"}" style="background:${color}">${inner}</div>`,
    });
  }

  function baseMap(el, opts) {
    const map = L.map(el, Object.assign({ scrollWheelZoom: false }, opts || {})).setView([-1.5, -78.4], 6);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    return map;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function popupHtml(p) {
    let html = `<strong>${esc(p.name)}</strong>`;
    if (p.kind_label) html += `<br><small>${esc(p.kind_label)}${p.province ? " · " + esc(p.province) : ""}</small>`;
    if (p.summary) html += `<p class="small mb-1 mt-1">${esc(p.summary)}</p>`;
    if (!p.verified) html += `<div class="small text-warning-emphasis">Ubicación aproximada, pendiente de validación</div>`;
    const links = [];
    if (p.url) links.push(`<a href="${esc(p.url)}">Ver detalle</a>`);
    if (p.directions) links.push(`<a href="${esc(p.directions)}" target="_blank" rel="noopener">Cómo llegar</a>`);
    if (links.length) html += `<div class="mt-1">${links.join(" · ")}</div>`;
    return html;
  }

  function initSmallMaps() {
    if (!window.L) return;
    document.querySelectorAll("[data-map-points]").forEach((el) => {
      const src = document.getElementById(el.dataset.mapPoints);
      const points = src ? JSON.parse(src.textContent) : [];
      if (!points.length) {
        el.innerHTML = '<div class="photo-placeholder"><i class="bi bi-map"></i><span>Sin ubicaciones validadas para mostrar</span></div>';
        return;
      }
      const map = baseMap(el);
      const isRoute = el.dataset.route === "true";
      const latlngs = points.map((p) => [p.lat, p.lng]);
      points.forEach((p, i) => {
        L.marker([p.lat, p.lng], { icon: markerIcon(isRoute ? "stop" : p.kind, p.verified, isRoute ? (p.order || i + 1) : null) })
          .addTo(map).bindPopup(popupHtml(p));
      });
      if (isRoute && latlngs.length > 1) {
        L.polyline(latlngs, { color: "#b5651d", weight: 4, opacity: .8, dashArray: "8 8" }).addTo(map);
      }
      latlngs.length > 1 ? map.fitBounds(latlngs, { padding: [30, 30] }) : map.setView(latlngs[0], 14);
    });
  }

  function initBigMap() {
    const app = document.getElementById("mapApp");
    if (!app || !window.L) return;
    const map = baseMap(document.getElementById("bigMap"), { scrollWheelZoom: true });
    const groups = {};
    const markers = [];
    const results = document.getElementById("mapResults");
    const search = document.getElementById("mapSearch");
    const checks = app.querySelectorAll(".map-filters input");

    fetch(app.dataset.source, { headers: { Accept: "application/json" } })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data) => {
        data.features.forEach((p) => {
          groups[p.kind] = groups[p.kind] || L.layerGroup().addTo(map);
          const m = L.marker([p.lat, p.lng], { icon: markerIcon(p.kind, p.verified) }).bindPopup(popupHtml(p));
          m.feature = p;
          groups[p.kind].addLayer(m);
          markers.push(m);
        });
        app.querySelectorAll("[data-count]").forEach((c) => {
          c.textContent = markers.filter((m) => m.feature.kind === c.dataset.count).length;
        });
        if (markers.length) map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [40, 40], maxZoom: 12 });
        else results.innerHTML = '<p class="small text-muted">Aún no hay ubicaciones publicadas.</p>';
        apply();
      })
      .catch(() => { results.innerHTML = '<p class="small text-danger">No se pudo cargar el mapa. Intenta nuevamente.</p>'; });

    function apply() {
      const active = new Set([...checks].filter((c) => c.checked).map((c) => c.value));
      const q = (search.value || "").trim().toLowerCase();
      const shown = [];
      markers.forEach((m) => {
        const p = m.feature;
        const text = `${p.name} ${p.province || ""} ${p.community || ""}`.toLowerCase();
        const ok = active.has(p.kind) && (!q || text.includes(q));
        const group = groups[p.kind];
        if (ok) { group.addLayer(m); shown.push(m); } else { group.removeLayer(m); }
      });
      if (q) {
        results.innerHTML = shown.length ? shown.slice(0, 25).map((m, i) =>
          `<a href="#" data-i="${markers.indexOf(m)}"><strong>${esc(m.feature.name)}</strong><br><small class="text-muted">${esc(m.feature.kind_label)}</small></a>`).join("")
          : '<p class="small text-muted">Sin coincidencias con ubicación registrada.</p>';
      } else {
        results.innerHTML = "";
      }
    }
    checks.forEach((c) => c.addEventListener("change", apply));
    search.addEventListener("input", apply);
    results.addEventListener("click", (e) => {
      const a = e.target.closest("a[data-i]");
      if (!a) return;
      e.preventDefault();
      const m = markers[+a.dataset.i];
      map.setView(m.getLatLng(), 15);
      m.openPopup();
    });

    const locate = document.getElementById("locateMe");
    const msg = document.getElementById("locateMsg");
    locate.addEventListener("click", () => {
      if (!navigator.geolocation) { msg.textContent = "Tu navegador no permite obtener la ubicación."; return; }
      const ok = window.confirm("¿Permites que Ecuador Cultural use la ubicación GPS de tu dispositivo para centrar el mapa? No se guardará.");
      if (!ok) return;
      msg.textContent = "Obteniendo ubicación…";
      navigator.geolocation.getCurrentPosition((pos) => {
        const ll = [pos.coords.latitude, pos.coords.longitude];
        L.circleMarker(ll, { radius: 9, color: "#fff", weight: 3, fillColor: "#1e88e5", fillOpacity: 1 }).addTo(map).bindPopup("Estás aquí").openPopup();
        map.setView(ll, 11);
        msg.textContent = "Ubicación encontrada. Abre «Cómo llegar» en cualquier destino para ver la ruta.";
      }, () => { msg.textContent = "No se pudo obtener tu ubicación (permiso denegado o sin señal)."; },
      { enableHighAccuracy: true, timeout: 10000 });
    });
  }

  /* ------------------------------------------------------------------
     6. Reordenar paradas de recorridos personalizados (arrastrar y soltar)
     ------------------------------------------------------------------ */
  function initTripReorder() {
    const list = document.getElementById("tripStops");
    if (!list) return;
    let dragged = null;
    list.addEventListener("dragstart", (e) => {
      dragged = e.target.closest(".trip-stop");
      if (dragged) dragged.classList.add("dragging");
    });
    list.addEventListener("dragover", (e) => {
      e.preventDefault();
      const over = e.target.closest(".trip-stop");
      if (!dragged || !over || over === dragged) return;
      const rect = over.getBoundingClientRect();
      list.insertBefore(dragged, e.clientY > rect.top + rect.height / 2 ? over.nextSibling : over);
    });
    list.addEventListener("dragend", async () => {
      if (!dragged) return;
      dragged.classList.remove("dragging");
      dragged = null;
      const body = new URLSearchParams();
      list.querySelectorAll(".trip-stop").forEach((li) => body.append("stop", li.dataset.id));
      const resp = await fetch(list.dataset.reorderUrl, {
        method: "POST", body, headers: { "X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest" },
      });
      if (resp.ok) location.reload();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initHeroCarousel();
    initRotators();
    initFavorites();
    initShare();
    initSmallMaps();
    initBigMap();
    initTripReorder();
  });
})();
