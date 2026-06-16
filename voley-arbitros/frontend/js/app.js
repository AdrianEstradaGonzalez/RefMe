import { icon, toast } from "./ui.js";

import * as dashboard from "./views/dashboard.js";
import * as arbitros from "./views/arbitros.js";
import * as clubs from "./views/clubs.js";
import * as disponibilidad from "./views/disponibilidad.js";
import * as partidos from "./views/partidos.js";
import * as categorias from "./views/categorias.js";
import * as asignaciones from "./views/asignaciones.js";

const RUTAS = {
  dashboard: {
    titulo: "Panel de control",
    sub: "Resumen general del sistema de designación arbitral",
    icono: "dashboard",
    modulo: dashboard,
    grupo: "General",
    label: "Dashboard",
  },
  arbitros: {
    titulo: "Árbitros",
    sub: "Gestión del cuerpo arbitral: datos, niveles y estado",
    icono: "users",
    modulo: arbitros,
    grupo: "Datos",
    label: "Árbitros",
  },
  disponibilidad: {
    titulo: "Disponibilidad",
    sub: "Franjas horarias y transporte por árbitro y día",
    icono: "clock",
    modulo: disponibilidad,
    grupo: "Datos",
    label: "Disponibilidad",
  },
  clubs: {
    titulo: "Clubs y equipos",
    sub: "Clubs de la federación y sus equipos asociados",
    icono: "users",
    modulo: clubs,
    grupo: "Datos",
    label: "Clubs y equipos",
  },
  categorias: {
    titulo: "Categorías",
    sub: "Requisitos arbitrales y niveles exigidos por categoría",
    icono: "layers",
    modulo: categorias,
    grupo: "Datos",
    label: "Categorías",
  },
  partidos: {
    titulo: "Calendario",
    sub: "Partidos programados y sus designaciones",
    icono: "calendar",
    modulo: partidos,
    grupo: "Competición",
    label: "Calendario",
  },
  asignaciones: {
    titulo: "Asignaciones",
    sub: "Designación automática de árbitros a partidos",
    icono: "sparkles",
    modulo: asignaciones,
    grupo: "Competición",
    label: "Asignaciones",
  },
};

const ORDEN = ["dashboard", "arbitros", "disponibilidad", "clubs", "categorias", "partidos", "asignaciones"];
const POR_DEFECTO = "dashboard";

function construirShell() {
  // Navegación agrupada
  const grupos = [];
  ORDEN.forEach((clave) => {
    const r = RUTAS[clave];
    let g = grupos.find((x) => x.nombre === r.grupo);
    if (!g) {
      g = { nombre: r.grupo, items: [] };
      grupos.push(g);
    }
    g.items.push({ clave, ...r });
  });

  const navHtml = grupos
    .map(
      (g) => `
      <div class="group-label">${g.nombre}</div>
      ${g.items
        .map(
          (it) =>
            `<a href="#/${it.clave}" data-ruta="${it.clave}">${icon(it.icono)}<span>${it.label}</span></a>`
        )
        .join("")}`
    )
    .join("");

  document.body.innerHTML = `
    <div class="app">
      <aside class="sidebar">
        <div class="brand">
          <div class="logo">
            <div class="mark">${icon("whistle")}</div>
            <div>
              <h1>Designación Arbitral</h1>
              <p>FED. VOLEIBOL · ASTURIAS</p>
            </div>
          </div>
        </div>
        <nav class="nav">${navHtml}</nav>
        <div class="sidebar-foot">
          Versión base · TFG<br>
          <span class="muted">Algoritmo IA en desarrollo</span>
        </div>
      </aside>
      <div class="main">
        <header class="topbar">
          <div class="titles">
            <h2 id="tituloVista"></h2>
            <p id="subVista"></p>
          </div>
        </header>
        <main class="content" id="content"></main>
      </div>
    </div>`;
}

function rutaActual() {
  const hash = (location.hash || "").replace(/^#\/?/, "").trim();
  return RUTAS[hash] ? hash : POR_DEFECTO;
}

async function navegar() {
  const clave = rutaActual();
  const r = RUTAS[clave];

  document.getElementById("tituloVista").textContent = r.titulo;
  document.getElementById("subVista").textContent = r.sub;

  document.querySelectorAll(".nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.ruta === clave);
  });

  const content = document.getElementById("content");
  content.innerHTML = "";

  try {
    await r.modulo.render(content);
  } catch (err) {
    console.error(err);
    content.innerHTML = `<div class="empty-state">${icon("info")}
      <div>No se pudo cargar la vista.<br><span class="muted">${
        err && err.message ? err.message : "Comprueba que el servidor está en marcha."
      }</span></div></div>`;
    toast("Error al cargar los datos", "err");
  }
}

function iniciar() {
  construirShell();
  if (!location.hash) location.hash = "#/" + POR_DEFECTO;
  window.addEventListener("hashchange", navegar);
  navegar();
}

iniciar();
