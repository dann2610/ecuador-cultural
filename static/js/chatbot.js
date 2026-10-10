/* Asistente Turístico Ecuador Cultural (widget flotante) */
(function () {
  "use strict";
  const root = document.getElementById("chatbot");
  if (!root) return;
  const toggle = root.querySelector(".chatbot__toggle");
  const panel = root.querySelector(".chatbot__panel");
  const list = root.querySelector(".chatbot__messages");
  const form = root.querySelector(".chatbot__form");
  const input = form.querySelector("#chatInput");
  const suggestBox = root.querySelector(".chatbot__suggestions");
  const saveBox = root.querySelector("[data-save-history]");
  const delBtn = root.querySelector("[data-delete-history]");
  const csrf = () => (window.ecCsrf && window.ecCsrf()) || (form.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
  let loaded = false;
  let busy = false;

  try { if (saveBox) saveBox.checked = localStorage.getItem("ec-chat-save") === "1"; } catch (e) { /* sin almacenamiento */ }
  if (saveBox) saveBox.addEventListener("change", () => { try { localStorage.setItem("ec-chat-save", saveBox.checked ? "1" : "0"); } catch (e) {} });

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function addMessage(role, text, items) {
    const m = el("div", "msg msg--" + role, text);
    if (items && items.length) {
      const box = el("div", "msg__items");
      items.forEach((it) => {
        const a = el("a", "msg__item");
        a.href = it.url;
        a.append(el("strong", null, it.title));
        if (it.subtitle) a.append(el("small", null, it.subtitle));
        box.append(a);
        if (it.maps) {
          const g = el("a", "maps", "↗ Abrir en Google Maps");
          g.href = it.maps; g.target = "_blank"; g.rel = "noopener";
          box.append(g);
        }
      });
      m.append(box);
    }
    list.append(m);
    list.scrollTop = list.scrollHeight;
    return m;
  }

  function renderSuggestions(arr) {
    suggestBox.innerHTML = "";
    arr.forEach((q) => {
      const b = el("button", null, q);
      b.type = "button";
      b.addEventListener("click", () => send(q));
      suggestBox.append(b);
    });
  }

  async function loadInitial() {
    if (loaded) return;
    loaded = true;
    try {
      const r = await fetch(root.dataset.suggestUrl, { headers: { Accept: "application/json" } });
      const data = await r.json();
      (data.history || []).forEach((m) => addMessage(m.role === "user" ? "user" : "bot", m.text));
      renderSuggestions(data.suggestions || []);
    } catch (e) { /* las sugerencias son opcionales */ }
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    addMessage("user", text);
    input.value = "";
    const typing = el("div", "msg msg--bot");
    typing.innerHTML = '<span class="typing" aria-label="Escribiendo"><span></span><span></span><span></span></span>';
    list.append(typing);
    list.scrollTop = list.scrollHeight;
    try {
      const resp = await fetch(root.dataset.askUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify({ message: text, save_history: !!(saveBox && saveBox.checked) }),
      });
      const data = await resp.json().catch(() => ({}));
      typing.remove();
      if (!resp.ok) { addMessage("error", data.error || "No pude responder en este momento."); return; }
      addMessage("bot", data.reply, data.items);
      if (data.suggestions && data.suggestions.length) renderSuggestions(data.suggestions);
    } catch (e) {
      typing.remove();
      addMessage("error", "Sin conexión con el asistente. Revisa tu internet e inténtalo de nuevo.");
    } finally {
      busy = false;
      input.focus();
    }
  }

  function open(state) {
    panel.hidden = !state;
    toggle.setAttribute("aria-expanded", String(state));
    if (state) { loadInitial(); input.focus(); }
  }
  toggle.addEventListener("click", () => open(panel.hidden));
  root.querySelector("[data-chat-close]").addEventListener("click", () => open(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) open(false); });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  if (delBtn) {
    delBtn.addEventListener("click", async () => {
      if (!confirm("¿Eliminar tu historial del asistente?")) return;
      await fetch(root.dataset.deleteUrl, { method: "POST", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" } });
      list.querySelectorAll(".msg").forEach((m, i) => { if (i > 0) m.remove(); });
    });
  }
})();
