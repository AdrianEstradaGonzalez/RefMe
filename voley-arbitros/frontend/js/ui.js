// Utilidades de interfaz: iconos SVG, helpers de DOM, toast y modal.

export const icons = {
  dashboard: '<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>',
  whistle: '<path d="M3 12a6 6 0 0 0 11.3 2.7L22 12l-2-3h-6.8A6 6 0 0 0 3 12z" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="7" cy="12" r="2"/>',
  users: '<path d="M16 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm-8 1a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.7 0-6 1.3-6 4v2h8v-2c0-1 .4-1.9 1.1-2.6A9 9 0 0 0 8 14zm8 0c-2.7 0-8 1.3-8 4v2h16v-2c0-2.7-5.3-4-8-4z"/>',
  calendar: '<path d="M7 2v2H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zm12 7v10H5V9h14z"/>',
  clock: '<path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 11h-2V6h2v5l4 2-1 1.7L13 13z"/>',
  layers: '<path d="M12 2 2 7l10 5 10-5-10-5zM2 12l10 5 10-5M2 17l10 5 10-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
  sparkles: '<path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2zM19 14l.9 2.6L22 17.5l-2.1.9L19 21l-.9-2.6L16 17.5l2.1-.9L19 14z"/>',
  plus: '<path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5z"/>',
  edit: '<path d="M3 17.25V21h3.75L17.8 9.94l-3.75-3.75L3 17.25zM20.7 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>',
  trash: '<path d="M6 7v13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7H6zm3-3V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1h5v2H4V4h5z"/>',
  search: '<path d="M21 20l-5.6-5.6a7 7 0 1 0-1.4 1.4L20 21l1-1zM5 10a5 5 0 1 1 5 5 5 5 0 0 1-5-5z"/>',
  pin: '<path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 14.5 9 2.5 2.5 0 0 1 12 11.5z"/>',
  info: '<path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>',
  check: '<path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/>',
  car: '<path d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v3h2m14-5a2 2 0 0 1 2 2v3h-2m-2 0H7m10 0v2m-10-2v2M7 16H5m14 0h-2" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="14.5" r="1"/><circle cx="16.5" cy="14.5" r="1"/>',
  walk: '<path d="M13 4a2 2 0 1 1-2-2 2 2 0 0 1 2 2zm-2 3.5L7.5 10l1 5L7 22m4-14.5 2.5 2 2.5 1m-5-3-1 5 3 2 1 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  handoff: '<path d="M3 13h6l2-2 4 4 6-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="6" r="2"/>',
};

export function icon(name, attrs = "") {
  return `<svg viewBox="0 0 24 24" fill="currentColor" ${attrs}>${icons[name] || ""}</svg>`;
}

// Crea un nodo a partir de HTML.
export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function spinner() {
  return el('<div class="spinner"></div>');
}

export function toast(msg, tipo = "ok") {
  const t = el(`<div class="toast ${tipo === "err" ? "err" : ""}">${msg}</div>`);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}

const MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
const DIAS = ["domingo","lunes","martes","miércoles","jueves","viernes","sábado"];

export function fechaLarga(iso) {
  const d = new Date(iso + "T00:00:00");
  return `${DIAS[d.getDay()]}, ${d.getDate()} de ${MESES[d.getMonth()]} de ${d.getFullYear()}`;
}

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// Modal sencillo. `campos` se renderiza dentro; devuelve una promesa con
// el resultado de `onSubmit(form)` o null si se cancela.
export function modal({ titulo, contenido, textoOk = "Guardar", onSubmit }) {
  return new Promise((resolve) => {
    const back = el('<div class="modal-back"></div>');
    back.innerHTML = `
      <div class="modal">
        <div class="modal-head"><h3>${escapeHtml(titulo)}</h3></div>
        <form class="modal-body">${contenido}</form>
        <div class="modal-foot">
          <button type="button" class="btn btn-ghost" data-cancel>Cancelar</button>
          <button type="button" class="btn btn-primary" data-ok>${escapeHtml(textoOk)}</button>
        </div>
      </div>`;
    const cerrar = (v) => { back.remove(); resolve(v); };
    back.querySelector("[data-cancel]").onclick = () => cerrar(null);
    back.addEventListener("click", (e) => { if (e.target === back) cerrar(null); });
    back.querySelector("[data-ok]").onclick = async () => {
      const form = back.querySelector("form");
      try {
        const r = onSubmit ? await onSubmit(form) : true;
        if (r !== false) cerrar(r);
      } catch (err) { toast(err.message, "err"); }
    };
    document.body.appendChild(back);
  });
}

export function pillEstado(estado) {
  const map = {
    asignado: ["green", "Asignado"],
    pendiente: ["amber", "Pendiente"],
    por_determinar: ["grey", "Por determinar"],
  };
  const [clase, txt] = map[estado] || ["grey", estado];
  return `<span class="pill ${clase}">${txt}</span>`;
}
