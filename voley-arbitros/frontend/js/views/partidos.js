import { api } from "../api.js";
import { el, icon, spinner, escapeHtml, fechaLarga, pillEstado } from "../ui.js";

const ROL_ETIQUETA = { primero: "1º", segundo: "2º", anotador: "Anot." };

export async function render(root) {
  root.appendChild(spinner());
  const [fechas, categorias] = await Promise.all([api.fechasPartidos(), api.categorias()]);
  root.innerHTML = "";

  const primera = fechas[0] || "";
  const ultima = fechas[fechas.length - 1] || "";
  // Rango por defecto: primera fecha + ~2 semanas.
  const porDefectoHasta = fechas[Math.min(fechas.length - 1, 13)] || ultima;

  const wrap = el('<div class="fade-in"></div>');
  wrap.appendChild(
    el(`<div class="toolbar" style="align-items:flex-end">
          <div><label>Desde</label><input id="desde" type="date" value="${primera}" min="${primera}" max="${ultima}"></div>
          <div><label>Hasta</label><input id="hasta" type="date" value="${porDefectoHasta}" min="${primera}" max="${ultima}"></div>
          <div><label>Categoría</label>
            <select id="cat" style="min-width:220px">
              <option value="">Todas las categorías</option>
              ${categorias.map((c) => `<option value="${c.id}">${escapeHtml(c.nombre)}</option>`).join("")}
            </select>
          </div>
          <div><label>Estado</label>
            <select id="estado">
              <option value="">Cualquier estado</option>
              <option value="asignado">Asignados</option>
              <option value="pendiente">Pendientes</option>
              <option value="por_determinar">Por determinar</option>
            </select>
          </div>
        </div>`)
  );
  const cont = el('<div id="lista"></div>');
  wrap.appendChild(cont);
  root.appendChild(wrap);

  async function cargar() {
    const desde = wrap.querySelector("#desde").value;
    const hasta = wrap.querySelector("#hasta").value;
    const params = {
      categoria_id: wrap.querySelector("#cat").value,
      estado: wrap.querySelector("#estado").value,
      limite: 1500,
    };
    if (desde) params.desde = desde;
    if (hasta) params.hasta = hasta;
    cont.innerHTML = "";
    cont.appendChild(spinner());
    const partidos = await api.partidos(params);
    cont.innerHTML = "";

    if (!partidos.length) {
      cont.appendChild(
        el(`<div class="card"><div class="empty-state">${icon("calendar")}<div>No hay partidos con estos filtros.</div></div></div>`)
      );
      return;
    }

    // Agrupar por fecha
    const grupos = {};
    partidos.forEach((p) => (grupos[p.fecha] = grupos[p.fecha] || []).push(p));

    Object.entries(grupos).forEach(([f, lista]) => {
      const g = el(`<div class="day-group">
        <div class="day-head"><span class="d">${fechaLarga(f)}</span><span class="c">${lista.length} partido(s)</span></div>
      </div>`);
      lista.forEach((p) => g.appendChild(tarjetaPartido(p)));
      cont.appendChild(g);
    });
  }

  wrap.querySelector("#desde").onchange = cargar;
  wrap.querySelector("#hasta").onchange = cargar;
  wrap.querySelector("#cat").onchange = cargar;
  wrap.querySelector("#estado").onchange = cargar;
  cargar();
}

function tarjetaPartido(p) {
  const refs = (p.asignaciones || [])
    .map(
      (a) =>
        `<span class="ref-chip">${ROL_ETIQUETA[a.rol] || ""} · ${escapeHtml(a.arbitro.nombre)}</span>`
    )
    .join("");
  const min = p.categoria ? p.categoria.min_arbitros : 1;
  const faltan = Math.max(0, min - (p.asignaciones || []).length);
  const placeholder = faltan
    ? `<span class="ref-chip empty">faltan ${faltan} árbitro(s)</span>`
    : "";

  return el(`<div class="match">
    <div class="time">${p.hora && p.hora !== "00:00" ? p.hora : "—"}</div>
    <div>
      <div class="teams">${escapeHtml(p.local)}<span class="vs">vs</span>${escapeHtml(p.visitante)}</div>
      <div class="meta">${escapeHtml(p.categoria ? p.categoria.nombre : "")} · ${
        p.campo ? icon("pin", 'style="width:12px;height:12px;vertical-align:-1px"') + " " + escapeHtml(p.campo) : "sede por determinar"
      } ${pillEstado(p.estado)}</div>
    </div>
    <div class="refs">${refs}${placeholder}</div>
  </div>`);
}
