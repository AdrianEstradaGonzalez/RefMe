import { api } from "../api.js";
import { el, spinner, toast, escapeHtml } from "../ui.js";

const ESTADOS = [
  { val: "con_transporte", cls: "con", label: "Con transporte" },
  { val: "sin_transporte", cls: "sin", label: "Sin transporte" },
  { val: "no_disponible",  cls: "no",  label: "No disponible"  },
];

const DIAS  = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const MESES = [
  "Enero","Febrero","Marzo","Abril","Mayo","Junio",
  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
];

export async function render(root) {
  root.appendChild(spinner());
  const [arbitros, franjas] = await Promise.all([api.arbitros(), api.franjas()]);
  root.innerHTML = "";

  const hoy = new Date();
  let viewYear  = hoy.getFullYear();
  let viewMonth = hoy.getMonth();
  let arbId     = arbitros[0]?.id;
  let disponMap = {};   // "YYYY-MM-DD_franja" → estado
  let selDay    = null; // "YYYY-MM-DD"

  /* ── DOM skeleton ── */
  const wrap = el('<div class="fade-in"></div>');

  wrap.appendChild(el(`
    <div class="toolbar">
      <label style="display:flex;align-items:center;gap:8px;margin:0">
        <span style="font-size:.78rem;font-weight:600;color:var(--ink-soft);white-space:nowrap">Árbitro</span>
        <select id="arb" style="min-width:260px">
          ${arbitros.map(a => `<option value="${a.id}">${escapeHtml(a.nombre)}</option>`).join("")}
        </select>
      </label>
      <span style="margin-left:auto;font-size:.82rem;color:var(--ink-soft)">
        Haz clic en un día para editar las franjas horarias
      </span>
    </div>
  `));

  const calCard = el('<div class="card cal-card"></div>');
  const calNav  = el('<div class="cal-nav-row"></div>');
  const calBulk = el('<div class="cal-bulk-row"></div>');
  const calGrid = el('<div class="cal-grid-body"></div>');
  calCard.appendChild(calNav);
  calCard.appendChild(calBulk);
  calCard.appendChild(calGrid);
  wrap.appendChild(calCard);

  const detail = el('<div class="cal-detail" style="display:none"></div>');
  wrap.appendChild(detail);

  root.appendChild(wrap);

  const arbSel = wrap.querySelector("#arb");

  /* ── helpers ── */
  const toISO = (y, m, d) =>
    `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

  const barCls = est =>
    est === "con_transporte" ? "bar-con"
    : est === "sin_transporte" ? "bar-sin"
    : est === "no_disponible"  ? "bar-no"
    : "bar-empty";

  const makeBars = fecha =>
    franjas.map(f =>
      `<div class="cal-bar ${barCls(disponMap[`${fecha}_${f}`])}" title="${f}"></div>`
    ).join("");

  /* ── bulk fill ── */
  async function rellenarMes(estado, btns) {
    btns.forEach(b => { b.disabled = true; });
    const total = new Date(viewYear, viewMonth + 1, 0).getDate();
    const tareas = [];
    for (let d = 1; d <= total; d++) {
      const fecha = toISO(viewYear, viewMonth, d);
      for (const f of franjas) {
        tareas.push(
          api.setDisponibilidad({ arbitro_id: arbId, fecha, franja: f, estado })
            .then(() => { disponMap[`${fecha}_${f}`] = estado; })
        );
      }
    }
    try {
      await Promise.all(tareas);
      selDay = null;
      detail.style.display = "none";
      renderCal();
      toast(`Mes completo marcado: ${ESTADOS.find(e => e.val === estado).label}`);
    } catch (e) {
      toast(e.message, "err");
    } finally {
      btns.forEach(b => { b.disabled = false; });
    }
  }

  /* ── calendar render ── */
  function renderCal() {
    calNav.innerHTML = `
      <button class="icon-btn" id="cal-prev">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M10 4l-4 4 4 4"/>
        </svg>
      </button>
      <span class="cal-month-title">${MESES[viewMonth]} ${viewYear}</span>
      <button class="icon-btn" id="cal-next">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M6 4l4 4-4 4"/>
        </svg>
      </button>
    `;
    calNav.querySelector("#cal-prev").onclick = () => {
      if (--viewMonth < 0) { viewMonth = 11; viewYear--; }
      selDay = null; detail.style.display = "none"; renderCal();
    };
    calNav.querySelector("#cal-next").onclick = () => {
      if (++viewMonth > 11) { viewMonth = 0; viewYear++; }
      selDay = null; detail.style.display = "none"; renderCal();
    };

    calBulk.innerHTML = `
      <span class="bulk-label">Rellenar mes completo:</span>
      ${ESTADOS.map(({ val, cls, label }) =>
        `<button class="bulk-btn bulk-${cls}" data-estado="${val}">${label}</button>`
      ).join("")}
    `;
    const bulkBtns = [...calBulk.querySelectorAll(".bulk-btn")];
    bulkBtns.forEach(btn => {
      btn.onclick = () => rellenarMes(btn.dataset.estado, bulkBtns);
    });

    calGrid.innerHTML = DIAS.map(d => `<div class="cal-col-hd">${d}</div>`).join("");

    const offset = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7;
    calGrid.insertAdjacentHTML("beforeend",
      Array(offset).fill('<div class="cal-cell cal-empty"></div>').join(""));

    const total  = new Date(viewYear, viewMonth + 1, 0).getDate();
    const todISO = toISO(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());

    for (let d = 1; d <= total; d++) {
      const fecha = toISO(viewYear, viewMonth, d);
      const cls   = ["cal-cell",
        fecha === todISO ? "cal-today" : "",
        fecha === selDay ? "cal-sel"   : "",
      ].filter(Boolean).join(" ");

      const cell = el(`<div class="${cls}" data-fecha="${fecha}">
        <span class="cal-num">${d}</span>
        <div class="cal-bars">${makeBars(fecha)}</div>
      </div>`);
      cell.onclick = () => selectDay(fecha);
      calGrid.appendChild(cell);
    }
  }

  /* ── detail panel ── */
  function selectDay(fecha) {
    selDay = fecha;
    renderCal();

    const label = new Date(fecha + "T12:00:00").toLocaleDateString("es-ES", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    });

    detail.style.display = "";
    detail.innerHTML = `
      <div class="card card-pad">
        <div class="det-head">
          <div>
            <h3 style="text-transform:capitalize">${label}</h3>
            <p class="sub">Selecciona la disponibilidad para cada franja horaria</p>
          </div>
          <button class="icon-btn" id="det-close" title="Cerrar">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M4 4l8 8M12 4l-8 8"/>
            </svg>
          </button>
        </div>
        <div class="det-franjas">
          ${franjas.map(f => {
            const est = disponMap[`${fecha}_${f}`] || null;
            return `<div class="det-row" data-franja="${f}">
              <span class="det-label">${f}</span>
              <div class="slot slot-lg">
                ${ESTADOS.map(({ val, cls, label: lbl }) =>
                  `<button data-estado="${val}" class="${cls}${est === val ? " on" : ""}">${lbl}</button>`
                ).join("")}
              </div>
            </div>`;
          }).join("")}
        </div>
        <p class="sub" style="margin-top:16px">
          <span class="pill green">Con transporte</span>
          <span class="pill amber" style="margin-left:6px">Sin transporte</span>
          <span class="pill grey"  style="margin-left:6px">No disponible</span>
        </p>
      </div>`;

    detail.querySelector("#det-close").onclick = () => {
      selDay = null; detail.style.display = "none"; renderCal();
    };

    detail.querySelectorAll(".det-row").forEach(row => {
      const franja = row.dataset.franja;
      row.querySelectorAll("button[data-estado]").forEach(btn => {
        btn.onclick = async () => {
          const estado = btn.dataset.estado;
          try {
            await api.setDisponibilidad({ arbitro_id: arbId, fecha, franja, estado });
            disponMap[`${fecha}_${franja}`] = estado;
            row.querySelectorAll("button[data-estado]").forEach(x => x.classList.remove("on"));
            btn.classList.add("on");
            const cell = calGrid.querySelector(`[data-fecha="${fecha}"]`);
            if (cell) cell.querySelector(".cal-bars").innerHTML = makeBars(fecha);
          } catch (e) {
            toast(e.message, "err");
          }
        };
      });
    });
  }

  /* ── data load ── */
  async function cargarDisp() {
    const all = await api.disponibilidad(arbId, null);
    disponMap = {};
    all.forEach(d => { disponMap[`${d.fecha}_${d.franja}`] = d.estado; });
  }

  // Sitúa el calendario en el primer mes con datos del árbitro (la
  // disponibilidad cargada es de la temporada, no del mes actual).
  function irAlMesConDatos() {
    const fechas = Object.keys(disponMap).map(k => k.slice(0, 7)).sort();
    if (!fechas.length) return;
    const [y, m] = fechas[0].split("-");
    viewYear = +y;
    viewMonth = +m - 1;
  }

  arbSel.onchange = async () => {
    arbId = +arbSel.value;
    selDay = null;
    detail.style.display = "none";
    await cargarDisp();
    irAlMesConDatos();
    renderCal();
  };

  await cargarDisp();
  irAlMesConDatos();
  renderCal();
}
