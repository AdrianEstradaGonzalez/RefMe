import { api } from "../api.js";
import { el, icon, spinner, toast, modal, escapeHtml } from "../ui.js";

let cache = { arbitros: [], sedes: [] };

// Límites aproximados del Principado de Asturias para encuadrar el mapa.
const ASTURIAS_BOUNDS = [
  [42.85, -7.25],
  [43.70, -4.45],
];

// Orden de presentación de los niveles arbitrales (de menor a mayor).
const ORDEN_NIVEL = [
  "CURSO NIVEL II", "CURSO ARBITRO NIVEL II",
  "NIVEL I", "NIVEL I - HABILITADO NIVEL II",
  "NIVEL II", "NIVEL II - HABILITADO NIVEL III",
  "NIVEL III - C", "NIVEL III - B", "NIVEL III - A",
  "ANOTADOR TERRITORIAL", "ANOTADOR NACIONAL B", "UNIFORME NACIONAL",
];

function nivelesPresentes(arbitros) {
  const set = new Set(arbitros.map((a) => a.nivel_arbitral).filter(Boolean));
  return [...set].sort((x, y) => {
    const ix = ORDEN_NIVEL.indexOf(x), iy = ORDEN_NIVEL.indexOf(y);
    if (ix !== -1 && iy !== -1) return ix - iy;
    if (ix !== -1) return -1;
    if (iy !== -1) return 1;
    return x.localeCompare(y);
  });
}

export async function render(root) {
  root.appendChild(spinner());
  const [arbitros, sedes] = await Promise.all([
    api.arbitros(),
    api.polideportivos(),
  ]);
  cache = { arbitros, sedes };
  root.innerHTML = "";

  const niveles = nivelesPresentes(arbitros);

  const wrap = el('<div class="fade-in"></div>');
  wrap.appendChild(
    el(`<div class="toolbar">
          <div class="search">${icon("search")}<input id="buscar" placeholder="Buscar por nombre o código..."></div>
          <select id="filtroNivel"><option value="">Todos los niveles</option>
            ${niveles.map((n) => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`).join("")}
          </select>
          <div class="spacer"></div>
          <button class="btn btn-primary" id="nuevo">${icon("plus")} Nuevo árbitro</button>
        </div>`)
  );

  // Mapa interactivo del Principado con la ubicación de árbitros y sedes.
  const cardMapa = el(`<div class="card map-card">
      <div class="map-head">
        <div>
          <h3>Mapa del cuerpo arbitral</h3>
          <p class="sub">Domicilios de los árbitros y polideportivos · pulsa un punto para ver el detalle</p>
        </div>
        <div class="map-legend">
          <button class="leg-item on" id="legArb"><span class="leg-dot arb"></span>Árbitros <b id="mapCount"></b></button>
          <button class="leg-item on" id="legSede"><span class="leg-dot sede"></span>Polideportivos <b>${sedes.length}</b></button>
        </div>
      </div>
      <div id="mapa" class="map-box"></div>
    </div>`);
  wrap.appendChild(cardMapa);

  const cardTabla = el(`<div class="card"><div class="table-wrap"><table>
      <thead><tr>
        <th>Árbitro</th><th>Código</th><th>Nivel</th><th>Localidad</th><th>Estado</th><th></th>
      </tr></thead><tbody id="cuerpo"></tbody></table></div></div>`);
  wrap.appendChild(cardTabla);
  root.appendChild(wrap);

  // Inicialización de Leaflet (debe ir tras insertar el contenedor en el DOM).
  const mapa = L.map("mapa", { scrollWheelZoom: false }).fitBounds(ASTURIAS_BOUNDS);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(mapa);
  const capaPines = L.layerGroup().addTo(mapa);
  const capaSedes = L.layerGroup().addTo(mapa);
  setTimeout(() => mapa.invalidateSize(), 0);

  // Marcadores fijos de polideportivos (sedes de competición).
  cache.sedes.forEach((s) => {
    L.marker([s.latitud, s.longitud], {
      icon: L.divIcon({
        className: "",
        html: `<div class="map-sede">${icon("calendar")}</div>`,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
        popupAnchor: [0, -12],
      }),
      title: s.nombre,
    })
      .bindPopup(`<div class="map-pop"><strong>${escapeHtml(s.nombre)}</strong>
        <div class="map-pop-sub">Polideportivo · sede de competición</div></div>`)
      .addTo(capaSedes);
  });

  // Toggles de la leyenda para mostrar/ocultar cada capa.
  const legArb = wrap.querySelector("#legArb");
  const legSede = wrap.querySelector("#legSede");
  legArb.onclick = () => {
    legArb.classList.toggle("on");
    if (legArb.classList.contains("on")) mapa.addLayer(capaPines);
    else mapa.removeLayer(capaPines);
  };
  legSede.onclick = () => {
    legSede.classList.toggle("on");
    if (legSede.classList.contains("on")) mapa.addLayer(capaSedes);
    else mapa.removeLayer(capaSedes);
  };

  const pintarMapa = (lista) => {
    capaPines.clearLayers();
    const conCoords = lista.filter((a) => a.latitud != null && a.longitud != null);
    const puntos = [];
    conCoords.forEach((a) => {
      // Si la dirección está geocodificada con precisión, posición exacta;
      // si es una aproximación por concejo, se dispersa para no solapar.
      const [dlat, dlon] = a.geocodificado ? [0, 0] : jitter(a.codigo);
      const lat = a.latitud + dlat;
      const lon = a.longitud + dlon;
      puntos.push([lat, lon]);
      const inicial = (a.nombre.trim()[0] || "·").toUpperCase();
      const marca = L.marker([lat, lon], {
        icon: L.divIcon({
          className: "",
          html: `<div class="map-pin"><span>${escapeHtml(inicial)}</span></div>`,
          iconSize: [30, 38],
          iconAnchor: [15, 38],
          popupAnchor: [0, -34],
        }),
        title: a.nombre,
      });
      marca.bindPopup(
        `<div class="map-pop">
           <strong>${escapeHtml(a.nombre)}</strong>
           <div class="map-pop-sub">${a.localidad ? escapeHtml(a.localidad) : "—"}${
          a.nivel_arbitral ? ` · ${escapeHtml(a.nivel_arbitral)}` : ""
        }</div>
           ${a.direccion ? `<div class="map-pop-dir">${escapeHtml(a.direccion.replace(/\n/g, ", "))}</div>` : ""}
         </div>`
      );
      capaPines.addLayer(marca);
    });

    wrap.querySelector("#mapCount").textContent = conCoords.length;
    if (puntos.length) {
      mapa.fitBounds(puntos, { padding: [40, 40], maxZoom: 12 });
    } else {
      mapa.fitBounds(ASTURIAS_BOUNDS);
    }
  };

  const pintar = () => {
    const txt = (wrap.querySelector("#buscar").value || "").toLowerCase();
    const nivel = wrap.querySelector("#filtroNivel").value;
    const cuerpo = wrap.querySelector("#cuerpo");
    const filtrados = cache.arbitros.filter(
      (a) =>
        (a.nombre.toLowerCase().includes(txt) || String(a.codigo).includes(txt)) &&
        (!nivel || a.nivel_arbitral === nivel)
    );

    pintarMapa(filtrados);

    if (!filtrados.length) {
      cuerpo.innerHTML = `<tr><td colspan="6"><div class="empty-state">${icon("users")}<div>No hay árbitros que coincidan.</div></div></td></tr>`;
      return;
    }
    cuerpo.innerHTML = filtrados
      .map(
        (a) => `<tr>
          <td><strong>${escapeHtml(a.nombre)}</strong></td>
          <td class="mono muted">${a.codigo}</td>
          <td>${a.nivel_arbitral ? `<span class="tag">${escapeHtml(a.nivel_arbitral)}</span>` : '<span class="muted">— sin asignar</span>'}</td>
          <td>${a.localidad ? escapeHtml(a.localidad) : '<span class="muted">—</span>'}</td>
          <td>${a.activo ? '<span class="pill green">Activo</span>' : '<span class="pill grey">Inactivo</span>'}</td>
          <td><div style="display:flex;gap:6px;justify-content:flex-end">
            <button class="icon-btn" data-edit="${a.id}" title="Editar">${icon("edit")}</button>
            <button class="icon-btn" data-del="${a.id}" title="Eliminar">${icon("trash")}</button>
          </div></td>
        </tr>`
      )
      .join("");
    cuerpo.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => formulario(root, +b.dataset.edit)));
    cuerpo.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => borrar(root, +b.dataset.del)));
  };

  wrap.querySelector("#buscar").oninput = pintar;
  wrap.querySelector("#filtroNivel").onchange = pintar;
  wrap.querySelector("#nuevo").onclick = () => formulario(root, null);
  pintar();
}

// Desplazamiento determinista (a partir del código) para separar visualmente a
// los árbitros que comparten concejo sin que los pines se solapen.
function jitter(codigo) {
  const h = (Math.abs(codigo | 0) * 2654435761) % 2147483647;
  const ang = ((h % 360) * Math.PI) / 180;
  const rad = 0.004 + ((h % 1000) / 1000) * 0.014; // ~0.4–2 km
  return [Math.sin(ang) * rad, Math.cos(ang) * rad];
}

async function formulario(root, id) {
  const a = id ? cache.arbitros.find((x) => x.id === id) : {};
  const opcionesNiv = nivelesPresentes(cache.arbitros)
    .map((n) => `<option value="${escapeHtml(n)}"></option>`)
    .join("");
  const r = await modal({
    titulo: id ? "Editar árbitro" : "Nuevo árbitro",
    contenido: `
      <div><label>Nombre completo</label><input name="nombre" value="${escapeHtml(a.nombre || "")}" required></div>
      <div class="row-2">
        <div><label>Código</label><input name="codigo" type="number" value="${a.codigo ?? ""}" required></div>
        <div><label>Nivel arbitral</label>
          <input name="nivel_arbitral" list="niveles-arb" value="${escapeHtml(a.nivel_arbitral || "")}" placeholder="NIVEL I, NIVEL II...">
          <datalist id="niveles-arb">${opcionesNiv}</datalist>
        </div>
      </div>
      <div><label>Dirección</label><input name="direccion" value="${escapeHtml(a.direccion || "")}"></div>
      <div class="row-2">
        <div><label>Código postal</label><input name="codigo_postal" value="${escapeHtml(a.codigo_postal || "")}"></div>
        <div><label>Localidad (concejo)</label><input name="localidad" value="${escapeHtml(a.localidad || "")}"></div>
      </div>`,
    onSubmit: async (form) => {
      const datos = {
        nombre: form.nombre.value.trim(),
        codigo: parseInt(form.codigo.value, 10),
        nivel_arbitral: form.nivel_arbitral.value.trim() || null,
        localidad: form.localidad.value.trim() || null,
        direccion: form.direccion.value.trim() || null,
        codigo_postal: form.codigo_postal.value.trim() || null,
      };
      if (!datos.nombre || Number.isNaN(datos.codigo)) throw new Error("Nombre y código son obligatorios");
      if (id) await api.actualizarArbitro(id, datos);
      else await api.crearArbitro(datos);
      return true;
    },
  });
  if (r) {
    toast(id ? "Árbitro actualizado" : "Árbitro creado");
    render(root);
  }
}

async function borrar(root, id) {
  const a = cache.arbitros.find((x) => x.id === id);
  const r = await modal({
    titulo: "Eliminar árbitro",
    contenido: `<p>¿Seguro que quieres eliminar a <strong>${escapeHtml(a.nombre)}</strong>? Se borrarán también sus disponibilidades y asignaciones.</p>`,
    textoOk: "Eliminar",
    onSubmit: async () => { await api.borrarArbitro(id); return true; },
  });
  if (r) { toast("Árbitro eliminado"); render(root); }
}
