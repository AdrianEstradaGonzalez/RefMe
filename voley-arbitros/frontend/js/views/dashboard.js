import { api } from "../api.js";
import { el, icon, spinner } from "../ui.js";

export async function render(root) {
  root.appendChild(spinner());
  const st = await api.estadisticas();
  root.innerHTML = "";

  const tarjetas = [
    ["Árbitros", st.arbitros, "users"],
    ["Partidos", st.partidos, "calendar"],
    ["Categorías", st.categorias, "layers"],
    ["Asignaciones", st.asignaciones, "whistle"],
  ];

  const wrap = el('<div class="fade-in"></div>');

  const cards = el('<div class="cards grid-4" style="margin-bottom:18px"></div>');
  tarjetas.forEach(([label, value, ic]) => {
    cards.appendChild(
      el(`<div class="card stat">
            <div class="ico">${icon(ic)}</div>
            <div class="label">${label}</div>
            <div class="value">${value.toLocaleString("es-ES")}</div>
          </div>`)
    );
  });
  wrap.appendChild(cards);

  // Estado de las designaciones
  const est = st.partidos_por_estado || {};
  const total = st.partidos || 1;
  const filas = [
    ["Asignados", est.asignado || 0, "var(--green)"],
    ["Pendientes", est.pendiente || 0, "var(--amber)"],
    ["Por determinar", est.por_determinar || 0, "var(--grey)"],
  ];
  const pct = Math.round(((est.asignado || 0) / total) * 100);

  const cols = el('<div class="cards grid-2"></div>');
  const prog = el(`
    <div class="card card-pad">
      <h3>Estado de las designaciones</h3>
      <p class="sub">${pct}% de los partidos tienen el mínimo de árbitros cubierto</p>
      <div style="margin-top:18px"></div>
    </div>`);
  filas.forEach(([n, v, c]) => {
    prog.appendChild(
      el(`<div class="bar-row">
            <span class="name">${n}</span>
            <span class="bar-track"><span class="bar-fill" style="width:${Math.round((v/total)*100)}%;background:${c}"></span></span>
            <span class="num">${v.toLocaleString("es-ES")}</span>
          </div>`)
    );
  });
  cols.appendChild(prog);

  const info = el(`
    <div class="card card-pad">
      <h3>Sobre el sistema</h3>
      <p class="sub" style="margin-top:6px;line-height:1.6">
        Plataforma de gestión y designación arbitral de la Federación de Voleibol
        del Principado de Asturias. Esta versión incluye la base de la aplicación:
        gestión de árbitros, disponibilidad, calendario, categorías y asignaciones manuales.
      </p>
      <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
        <span class="tag">${st.equipos.toLocaleString("es-ES")} equipos</span>
        <span class="tag">Datos cargados de Excel</span>
        <span class="tag">Algoritmo IA · próximamente</span>
      </div>
      <a href="#/asignaciones" class="btn btn-gold" style="margin-top:18px">
        ${icon("sparkles")} Ir a asignación automática
      </a>
    </div>`);
  cols.appendChild(info);
  wrap.appendChild(cols);

  root.appendChild(wrap);
}
