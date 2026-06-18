import { api } from "../api.js";
import { el, icon, spinner, toast, modal, escapeHtml, fechaLarga } from "../ui.js";

const ROL_ET = { primero: "1º", segundo: "2º", anotador: "Anot." };

// Etiqueta de cómo se desplaza el árbitro: vehículo propio, le llevan o andando.
function transporteHtml(d) {
  const t = d.transporte;
  if (!t) return "";
  if (t === "con") {
    const lleva = d.recoge && d.recoge.length;
    const txt = lleva ? `lleva a ${d.recoge.map(escapeHtml).join(", ")}` : "coche";
    const title = lleva ? `Conduce y recoge a ${d.recoge.map(escapeHtml).join(", ")}` : "Va con su vehículo";
    const cls = lleva ? "t-lleva" : "t-con";
    return `<span class="trans ${cls}" title="${title}">${icon("car", 'style="width:13px;height:13px;vertical-align:-2px"')} ${txt}</span>`;
  }
  if (t === "llevan") {
    return "";
  }
  if (t === "andando") {
    return `<span class="trans t-andando" title="Va andando (≤ 10 km)">${icon("walk", 'style="width:13px;height:13px;vertical-align:-2px"')} andando</span>`;
  }
  if (t === "necesita") {
    return `<span class="trans t-necesita" title="Sin transporte y a más de 10 km: necesita que le lleven">${icon("info", 'style="width:13px;height:13px;vertical-align:-2px"')} necesita transporte</span>`;
  }
  return "";
}

export async function render(root) {
  const estado = {
    desde: "2025-02-03",
    hasta: "2025-02-09",
    partidos: [],
    seleccion: new Set(),
    preview: null,       // resultado de /generar
    previewMap: null,    // partido_id -> [{rol, arbitro_nombre}]
  };

  root.innerHTML = "";
  const wrap = el('<div class="fade-in"></div>');

  // ---- Cabecera: descripción + controles ----
  wrap.appendChild(el(`
    <div class="card card-pad" style="margin-bottom:18px">
      <div style="display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap">
        <span class="badge" style="width:48px;height:48px;border-radius:12px;flex:none;background:var(--gold-soft);color:var(--amber);display:grid;place-items:center">${icon("sparkles")}</span>
        <div style="flex:1;min-width:240px">
          <h3 style="margin-bottom:4px">Asignación automática</h3>
          <p class="sub" style="line-height:1.6">
            Motor híbrido <strong>greedy → CP-SAT → búsqueda local</strong>. Selecciona los partidos a
            designar (solo aparecen los que tienen todos los datos: categoría, hora y sede),
            previsualiza la propuesta y publícala para que aparezca en el calendario.
          </p>
        </div>
      </div>
      <div class="toolbar" style="margin-top:18px;margin-bottom:0;align-items:flex-end">
        <div><label>Desde</label><input id="desde" type="date" value="${estado.desde}"></div>
        <div><label>Hasta</label><input id="hasta" type="date" value="${estado.hasta}"></div>
        <div class="spacer"></div>
        <button class="btn btn-danger" id="limpiar">${icon("trash")} Eliminar designaciones</button>
        <button class="btn btn-ghost" id="publicar" disabled>${icon("check")} Publicar</button>
        <button class="btn btn-gold" id="generar">${icon("sparkles")} Generar designación</button>
      </div>
    </div>`));

  const resultado = el('<div id="resultado"></div>');
  wrap.appendChild(resultado);

  const cardLista = el(`<div class="card">
      <div class="card-pad" style="padding-bottom:0">
        <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
          <label style="display:flex;align-items:center;gap:8px;margin:0;font-weight:600;color:var(--ink)">
            <input id="todos" type="checkbox" style="width:auto" checked> Seleccionar todos
          </label>
          <span class="sub" id="resumen"></span>
        </div>
      </div>
      <div id="lista" style="padding:12px 22px 22px"></div>
    </div>`);
  wrap.appendChild(cardLista);
  root.appendChild(wrap);

  // Clic en un árbitro → resumen de su desplazamiento (datos ya cargados,
  // tanto de la previsualización como de las designaciones publicadas).
  cardLista.addEventListener("click", (e) => {
    const chip = e.target.closest(".ref-chip.clic[data-arb]");
    if (chip) abrirItinerario(+chip.dataset.arb, chip.dataset.fecha);
  });

  // Reúne las designaciones de un árbitro SOLO del día del partido pulsado y abre el modal.
  function abrirItinerario(arbId, fecha) {
    let nombre = "";
    const tramos = [];
    for (const p of estado.partidos) {
      if (fecha && p.fecha !== fecha) continue;
      const desigs = estado.previewMap ? (estado.previewMap[p.id] || []) : (p.designaciones || []);
      for (const d of desigs) {
        if (d.arbitro_id !== arbId) continue;
        nombre = d.arbitro_nombre || nombre;
        tramos.push({
          fecha: p.fecha, hora: p.hora, sede: p.sede,
          local: p.local, visitante: p.visitante, rol: d.rol,
          transporte: d.transporte, conductor: d.conductor, recoge: d.recoge || [],
          km: d.km, desde: d.desde, desde_tipo: d.desde_tipo,
        });
      }
    }
    tramos.sort((a, b) => (a.hora || "").localeCompare(b.hora || ""));
    modal({
      titulo: `Desplazamiento · ${nombre || "árbitro"}${fecha ? " · " + fechaLarga(fecha) : ""}`,
      contenido: itinerarioHtml(tramos),
      textoOk: "Cerrar",
    });
  }

  const $ = (sel) => wrap.querySelector(sel);

  function limpiarPreview() {
    estado.preview = null;
    estado.previewMap = null;
    resultado.innerHTML = "";
    $("#publicar").disabled = true;
  }

  async function cargarPartidos() {
    limpiarPreview();
    const lista = $("#lista");
    lista.innerHTML = "";
    lista.appendChild(spinner());
    try {
      estado.partidos = await api.partidosDesignables(estado.desde, estado.hasta);
    } catch (e) {
      lista.innerHTML = "";
      toast(e.message, "err");
      return;
    }
    estado.seleccion = new Set(estado.partidos.map((p) => p.id));
    $("#todos").checked = true;
    pintarLista();
  }

  function pintarLista() {
    const lista = $("#lista");
    lista.innerHTML = "";
    if (!estado.partidos.length) {
      lista.innerHTML = `<div class="empty-state">${icon("calendar")}<div>No hay partidos designables en este rango.<br><span class="muted">Solo aparecen los partidos con categoría, hora y sede conocidas.</span></div></div>`;
      actualizarResumen();
      return;
    }
    const grupos = {};
    estado.partidos.forEach((p) => (grupos[p.fecha] = grupos[p.fecha] || []).push(p));
    Object.entries(grupos).forEach(([f, ps]) => {
      const g = el(`<div class="day-group">
        <div class="day-head"><span class="d">${fechaLarga(f)}</span><span class="c">${ps.length} partido(s)</span></div>
      </div>`);
      ps.forEach((p) => g.appendChild(filaPartido(p)));
      lista.appendChild(g);
    });
    actualizarResumen();
  }

  function filaPartido(p) {
    const sel = estado.seleccion.has(p.id);
    const propuesta = estado.previewMap && estado.previewMap[p.id];
    let chips;
    if (propuesta) {
      chips = propuesta
        .map((d) => `<span class="ref-chip propuesto clic" data-arb="${d.arbitro_id}" data-fecha="${p.fecha}" title="Ver desplazamiento">${ROL_ET[d.rol] || d.rol} · ${escapeHtml(d.arbitro_nombre)}${transporteHtml(d)}</span>`)
        .join("");
    } else {
      chips = (p.designaciones || [])
        .map((d) => `<span class="ref-chip clic" data-arb="${d.arbitro_id}" data-fecha="${p.fecha}" title="Ver desplazamiento">${ROL_ET[d.rol] || d.rol} · ${escapeHtml(d.arbitro_nombre)}${transporteHtml(d)}</span>`)
        .join("");
      const faltan = Math.max(0, p.min_arbitros - (p.designaciones || []).length);
      if (faltan) chips += `<span class="ref-chip empty">faltan ${faltan}</span>`;
    }

    const fila = el(`<div class="asig-row${sel ? " sel" : ""}">
      <input type="checkbox" class="asig-check" ${sel ? "checked" : ""}>
      <div class="time">${p.hora && p.hora !== "00:00" ? p.hora : "—"}</div>
      <div class="asig-info">
        <div class="teams">${escapeHtml(p.local)}<span class="vs">vs</span>${escapeHtml(p.visitante)}</div>
        <div class="meta">${escapeHtml(p.categoria || "")} · ${icon("pin", 'style="width:12px;height:12px;vertical-align:-1px"')} ${escapeHtml(p.sede || "")}</div>
      </div>
      <div class="refs">${chips}</div>
    </div>`);

    const chk = fila.querySelector(".asig-check");
    chk.onchange = () => {
      if (chk.checked) estado.seleccion.add(p.id);
      else estado.seleccion.delete(p.id);
      fila.classList.toggle("sel", chk.checked);
      limpiarPreview();
      actualizarResumen();
    };
    return fila;
  }

  function actualizarResumen() {
    $("#resumen").textContent =
      `${estado.partidos.length} designables · ${estado.seleccion.size} seleccionados`;
    $("#generar").disabled = estado.seleccion.size === 0;
  }

  // ---- Acciones ----
  $("#desde").onchange = (e) => { estado.desde = e.target.value; cargarPartidos(); };
  $("#hasta").onchange = (e) => { estado.hasta = e.target.value; cargarPartidos(); };

  $("#todos").onchange = (e) => {
    const on = e.target.checked;
    estado.seleccion = on ? new Set(estado.partidos.map((p) => p.id)) : new Set();
    limpiarPreview();
    pintarLista();
  };

  $("#generar").onclick = async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    const txt = btn.innerHTML;
    btn.innerHTML = "Optimizando…";
    resultado.innerHTML = "";
    resultado.appendChild(spinner());
    try {
      const r = await api.generar({
        fecha_desde: estado.desde,
        fecha_hasta: estado.hasta,
        segundos_max: 15,
        partido_ids: [...estado.seleccion],
      });
      estado.preview = r;
      estado.previewMap = {};
      r.asignaciones.forEach((a) => {
        (estado.previewMap[a.partido_id] = estado.previewMap[a.partido_id] || []).push(a);
      });
      resultado.innerHTML = "";
      resultado.appendChild(panelMetricas(r));
      $("#publicar").disabled = r.asignaciones.length === 0;
      pintarLista();
      toast("Previsualización generada");
    } catch (err) {
      resultado.innerHTML = "";
      toast(err.message || "Error al generar", "err");
    } finally {
      btn.disabled = false;
      btn.innerHTML = txt;
    }
  };

  $("#publicar").onclick = async (e) => {
    if (!estado.preview) return;
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const asigs = estado.preview.asignaciones.map((a) => ({
        partido_id: a.partido_id, arbitro_id: a.arbitro_id, rol: a.rol,
      }));
      const r = await api.publicar(asigs);
      toast(`Publicadas ${r.publicadas} designaciones`);
      await cargarPartidos();
    } catch (err) {
      toast(err.message || "Error al publicar", "err");
      btn.disabled = false;
    }
  };

  $("#limpiar").onclick = async () => {
    const ok = await modal({
      titulo: "Eliminar designaciones",
      contenido: `<p>¿Eliminar <strong>todas las designaciones</strong> del rango
        ${fechaLarga(estado.desde)} → ${fechaLarga(estado.hasta)}? Esta acción no se puede deshacer.</p>`,
      textoOk: "Eliminar",
      onSubmit: async () => {
        await api.limpiarAsignaciones({ fecha_desde: estado.desde, fecha_hasta: estado.hasta });
        return true;
      },
    });
    if (ok) { toast("Designaciones eliminadas"); cargarPartidos(); }
  };

  await cargarPartidos();
}

// ---------------------------------------------------------------- Itinerario
// De dónde viene el árbitro a la sede del partido.
function origenHtml(t) {
  if (t.desde_tipo === "mismo_poli") return `Ya estaba en el polideportivo`;
  if (t.desde_tipo === "sede_anterior") return `Viene de <strong>${escapeHtml(t.desde || "otra sede")}</strong>`;
  return `Sale de su domicilio`;
}

// Cómo se desplaza.
function modoHtml(t) {
  if (t.transporte === "llevan") {
    return `<span class="pill amber">le trae ${escapeHtml(t.conductor || "un compañero")}</span>`;
  }
  if (t.transporte === "andando") {
    return `<span class="pill green">andando</span>`;
  }
  if (t.transporte === "necesita") {
    return `<span class="pill amber">necesita transporte</span> (a más de 10 km sin coche)`;
  }
  if (t.recoge && t.recoge.length) {
    return `<span class="pill navy">con su vehículo</span> y recoge a ${t.recoge.map(escapeHtml).join(", ")}`;
  }
  return `<span class="pill navy">con su vehículo</span>`;
}

function itinerarioHtml(tramos) {
  if (!tramos.length) {
    return `<p class="sub">Sin partidos asignados este día.</p>`;
  }
  const total = tramos.reduce((s, t) => s + (t.km || 0), 0);
  const filas = tramos.map((t) => {
    // Para copilotos los km los asume el conductor: se muestra "—".
    const km = t.transporte === "llevan" ? "—" : `${(t.km ?? 0).toLocaleString("es-ES")} km`;
    return `<div class="itin-row">
      <div class="itin-time">${t.hora && t.hora !== "00:00" ? t.hora : "—"}</div>
      <div class="itin-main">
        <div><strong>${escapeHtml(t.sede || "")}</strong> · ${ROL_ET[t.rol] || t.rol}</div>
        <div class="sub">${escapeHtml(t.local)} vs ${escapeHtml(t.visitante)}</div>
        <div class="sub">${origenHtml(t)} · ${modoHtml(t)}</div>
      </div>
      <div class="itin-km">${km}</div>
    </div>`;
  }).join("");
  return `<div class="itin">${filas}</div>
    <p class="sub" style="margin-top:12px;text-align:right">Recorrido total del día: <strong>${total.toLocaleString("es-ES")} km</strong></p>`;
}

// ---------------------------------------------------------------- Métricas
function panelMetricas(r) {
  const m = r.metricas;
  const c = m.carga || {};
  const stat = (label, value, sub) => `
    <div class="card stat">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      ${sub ? `<div class="sub" style="margin-top:6px">${sub}</div>` : ""}
    </div>`;

  return el(`
    <div class="fade-in" style="margin-bottom:18px">
      <div class="cards grid-4" style="margin-bottom:16px">
        ${stat("Cobertura", `${m.cobertura_pct}%`, `${m.roles_cubiertos}/${m.roles_totales} roles`)}
        ${stat("Km totales", m.km_total.toLocaleString("es-ES"), `${m.km_medio} km/asignación`)}
        ${stat("Árbitros usados", c.arbitros_usados ?? 0, `carga ${c.min}–${c.max} · media ${c.media}`)}
      </div>
      <div class="card card-pad">
        <h3>Detalle de la optimización</h3>
        <p class="sub">Rango ${r.fecha_desde} → ${r.fecha_hasta} · ${m.partidos_total} partidos
          (${m.partidos_cubiertos} con todos sus roles cubiertos)</p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin:14px 0">
          ${(m.fases || []).map((f) => `<span class="pill navy">${f}</span>`).join("")}
          <span class="tag">CP-SAT: ${m.cpsat?.estado || "—"}</span>
          ${m.cpsat?.variables ? `<span class="tag">${m.cpsat.variables} variables</span>` : ""}
        </div>
        <div class="bar-row"><span class="name">Greedy</span>
          <span class="bar-track"><span class="bar-fill" style="width:${barW(m.tiempos_s,"greedy")}%;background:var(--navy-600)"></span></span>
          <span class="num">${m.tiempos_s?.greedy ?? 0}s</span></div>
        <div class="bar-row"><span class="name">CP-SAT</span>
          <span class="bar-track"><span class="bar-fill" style="width:${barW(m.tiempos_s,"cpsat")}%;background:var(--gold)"></span></span>
          <span class="num">${m.tiempos_s?.cpsat ?? 0}s</span></div>
        <div class="bar-row"><span class="name">Búsqueda local</span>
          <span class="bar-track"><span class="bar-fill" style="width:${barW(m.tiempos_s,"local")}%;background:var(--green)"></span></span>
          <span class="num">${m.tiempos_s?.local ?? 0}s</span></div>
        <p class="sub" style="margin-top:14px">
          Desviación de carga: <strong>${c.desv ?? 0}</strong> ·
          Emparejamientos repetidos: <strong>${m.emparejamientos_repetidos ?? 0}</strong>
        </p>
        <p class="sub" style="margin-top:6px">Previsualización (no guardada). Pulsa <strong>Publicar</strong> para aplicarlas al calendario.</p>
      </div>
    </div>`);
}

function barW(t, fase) {
  if (!t) return 0;
  const max = Math.max(0.001, ...Object.values(t));
  return Math.round(((t[fase] || 0) / max) * 100);
}
