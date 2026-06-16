import { api } from "../api.js";
import { el, icon, spinner, escapeHtml } from "../ui.js";

let cache = [];

export async function render(root) {
  root.appendChild(spinner());
  cache = await api.categorias();
  root.innerHTML = "";

  const wrap = el('<div class="fade-in"></div>');

  wrap.appendChild(
    el(`<div class="toolbar">
          <div class="search">${icon("search")}<input id="buscar" placeholder="Buscar categoría..."></div>
          <div class="spacer"></div>
          <span class="muted">${cache.length} categorías</span>
        </div>`)
  );

  wrap.appendChild(
    el(`<div class="notice" style="margin-bottom:16px">
          <span class="badge">${icon("info")}</span>
          <div><p>Cada categoría define qué roles arbitrales requiere (primer árbitro, segundo y anotador),
          el nivel mínimo exigido en cada rol y su prioridad de cobertura. Estos requisitos guiarán
          al algoritmo de asignación automática.</p></div>
        </div>`)
  );

  const cardTabla = el(`<div class="card"><div class="table-wrap"><table>
      <thead><tr>
        <th>Categoría</th>
        <th>Primer árbitro</th>
        <th>Segundo árbitro</th>
        <th>Anotador</th>
        <th style="text-align:center">Mínimo</th>
        <th style="text-align:center">Prioridad</th>
      </tr></thead><tbody id="cuerpo"></tbody></table></div></div>`);
  wrap.appendChild(cardTabla);
  root.appendChild(wrap);

  const celdaRol = (requiere, nivel) => {
    if (!requiere) return '<span class="muted">— no requiere</span>';
    if (nivel) return `<span class="tag">${escapeHtml(nivel.nombre)}</span>`;
    return '<span class="pill green">Requerido</span>';
  };

  const pintar = () => {
    const txt = (wrap.querySelector("#buscar").value || "").toLowerCase();
    const cuerpo = wrap.querySelector("#cuerpo");
    const filtradas = cache.filter((c) => c.nombre.toLowerCase().includes(txt));

    if (!filtradas.length) {
      cuerpo.innerHTML = `<tr><td colspan="6"><div class="empty-state">${icon("layers")}<div>No hay categorías que coincidan.</div></div></td></tr>`;
      return;
    }

    cuerpo.innerHTML = filtradas
      .map(
        (c) => `<tr>
          <td><strong>${escapeHtml(c.nombre)}</strong></td>
          <td>${celdaRol(c.requiere_primero, c.nivel_primero)}</td>
          <td>${celdaRol(c.requiere_segundo, c.nivel_segundo)}</td>
          <td>${celdaRol(c.requiere_anotador, c.nivel_anotador)}</td>
          <td style="text-align:center"><strong>${c.min_arbitros}</strong></td>
          <td style="text-align:center">${
            c.prioridad != null ? `<span class="mono muted">${c.prioridad}</span>` : '<span class="muted">—</span>'
          }</td>
        </tr>`
      )
      .join("");
  };

  wrap.querySelector("#buscar").oninput = pintar;
  pintar();
}
