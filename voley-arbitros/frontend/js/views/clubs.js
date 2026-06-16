import { api } from "../api.js";
import { el, icon, spinner, toast, escapeHtml } from "../ui.js";

// Un equipo: nombre + su categoría (si se conoce).
function equipoHtml(e, nombreBusqueda) {
  const cat = e.categoria ? e.categoria.nombre : null;
  const data = nombreBusqueda ? ` data-nombre="${escapeHtml(e.nombre.toLowerCase())}"` : "";
  return `<div class="equipo-row"${data}>
      <span class="equipo-name">${escapeHtml(e.nombre)}</span>
      ${cat ? `<span class="equipo-cat">${escapeHtml(cat)}</span>` : '<span class="equipo-cat muted">— sin categoría</span>'}
    </div>`;
}

export async function render(root) {
  root.appendChild(spinner());
  let clubs, externos;
  try {
    [clubs, externos] = await Promise.all([api.clubs(), api.equiposSinClub()]);
  } catch (e) {
    root.innerHTML = "";
    toast(e.message, "err");
    throw e;
  }
  root.innerHTML = "";

  const totalEquipos =
    clubs.reduce((n, c) => n + c.equipos.length, 0) + externos.length;

  const wrap = el('<div class="fade-in"></div>');
  wrap.appendChild(
    el(`<div class="toolbar">
          <div class="search">${icon("search")}<input id="buscar" placeholder="Buscar club o equipo..."></div>
          <div class="spacer"></div>
          <span class="pill navy">${clubs.length} clubs</span>
          <span class="pill navy">${totalEquipos} equipos</span>
        </div>`)
  );

  const grid = el('<div class="clubs-grid"></div>');
  wrap.appendChild(grid);

  // Bloque de equipos externos (sin club asociado), al final.
  const extWrap = el("<div></div>");
  if (externos.length) {
    extWrap.appendChild(
      el(`<div class="card card-pad club-card ext-card">
            <div class="club-head">
              <div class="club-mark">${icon("users")}</div>
              <div>
                <h3>Equipos externos / sin club</h3>
                <p class="sub">${externos.length} equipos (visitantes de otras federaciones)</p>
              </div>
            </div>
            <div class="equipo-list">
              ${externos.map((e) => equipoHtml(e, true)).join("")}
            </div>
          </div>`)
    );
  }
  wrap.appendChild(extWrap);
  root.appendChild(wrap);

  function pintar() {
    const q = (wrap.querySelector("#buscar").value || "").toLowerCase().trim();
    grid.innerHTML = "";
    let visibles = 0;

    clubs.forEach((c) => {
      const equiposFiltrados = q
        ? c.equipos.filter((e) => e.nombre.toLowerCase().includes(q))
        : c.equipos;
      const clubCoincide = c.nombre.toLowerCase().includes(q);
      if (q && !clubCoincide && equiposFiltrados.length === 0) return;

      const lista = clubCoincide ? c.equipos : equiposFiltrados;
      visibles++;
      grid.appendChild(
        el(`<div class="card card-pad club-card">
              <div class="club-head">
                <div class="club-mark">${icon("layers")}</div>
                <div>
                  <h3>${escapeHtml(c.nombre)}</h3>
                  <p class="sub">${c.equipos.length} equipo${c.equipos.length === 1 ? "" : "s"}</p>
                </div>
              </div>
              <div class="equipo-list">
                ${
                  lista.length
                    ? lista.map((e) => equipoHtml(e)).join("")
                    : '<span class="muted" style="font-size:.84rem">Sin equipos</span>'
                }
              </div>
            </div>`)
      );
    });

    if (!visibles) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">${icon("layers")}<div>No hay clubs ni equipos que coincidan.</div></div>`;
    }

    // Filtrar también los equipos externos.
    extWrap.querySelectorAll(".equipo-row").forEach((row) => {
      const hit = !q || (row.dataset.nombre || "").includes(q);
      row.style.display = hit ? "" : "none";
    });
  }

  wrap.querySelector("#buscar").oninput = pintar;
  pintar();
}
