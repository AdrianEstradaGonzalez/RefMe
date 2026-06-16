// Cliente de la API REST. Todas las llamadas pasan por aquí.
const BASE = "/api";

async function req(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || `Error ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  estadisticas: () => req("GET", "/estadisticas"),
  niveles: () => req("GET", "/niveles"),

  arbitros: () => req("GET", "/arbitros"),
  crearArbitro: (d) => req("POST", "/arbitros", d),
  actualizarArbitro: (id, d) => req("PUT", `/arbitros/${id}`, d),
  borrarArbitro: (id) => req("DELETE", `/arbitros/${id}`),

  categorias: () => req("GET", "/categorias"),

  polideportivos: () => req("GET", "/polideportivos"),

  clubs: () => req("GET", "/clubs"),
  equiposSinClub: () => req("GET", "/clubs/equipos?sin_club=true"),

  partidos: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== "" && v != null)
    ).toString();
    return req("GET", "/partidos" + (q ? `?${q}` : ""));
  },
  fechasPartidos: () => req("GET", "/partidos/fechas"),

  franjas: () => req("GET", "/disponibilidad/franjas"),
  disponibilidad: (arbitro_id, fecha) => {
    const p = new URLSearchParams({ arbitro_id });
    if (fecha) p.set("fecha", fecha);
    return req("GET", `/disponibilidad?${p}`);
  },
  setDisponibilidad: (d) => req("PUT", "/disponibilidad", d),

  asignaciones: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return req("GET", "/asignaciones" + (q ? `?${q}` : ""));
  },
  crearAsignacion: (d) => req("POST", "/asignaciones", d),
  borrarAsignacion: (id) => req("DELETE", `/asignaciones/${id}`),
  partidosDesignables: (desde, hasta) => {
    const q = new URLSearchParams();
    if (desde) q.set("desde", desde);
    if (hasta) q.set("hasta", hasta);
    return req("GET", "/asignaciones/partidos" + (q.toString() ? `?${q}` : ""));
  },
  generar: (opts) => req("POST", "/asignaciones/generar", opts || {}),
  publicar: (asignaciones) => req("POST", "/asignaciones/publicar", { asignaciones }),
  limpiarAsignaciones: (opts) => req("POST", "/asignaciones/limpiar", opts || {}),
  itinerario: (arbitroId, desde, hasta) => {
    const q = new URLSearchParams();
    if (desde) q.set("desde", desde);
    if (hasta) q.set("hasta", hasta);
    return req("GET", `/asignaciones/itinerario/${arbitroId}` + (q.toString() ? `?${q}` : ""));
  },
};
