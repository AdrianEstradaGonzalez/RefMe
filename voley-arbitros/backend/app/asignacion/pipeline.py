"""Orquestación del pipeline de asignación (las 3 fases) y cálculo de métricas."""
import time
from dataclasses import dataclass
from datetime import date

from .. import models
from . import comun, cpsat, datos, distancias, greedy, local


@dataclass
class OpcionesAsignacion:
    fecha_desde: date
    fecha_hasta: date
    segundos_max: float = 20.0
    usar_cpsat: bool = True
    umbral_sin_transporte: float = datos.UMBRAL_SIN_TRANSPORTE_KM
    partido_ids: list | None = None


def _clave_calidad(inst, sol):
    """Mayor cobertura y, a igualdad, menor km. (para comparar soluciones)"""
    return (len(sol), -comun.km_total(inst, sol))


def _mejor(inst, a, b):
    return a if _clave_calidad(inst, a) >= _clave_calidad(inst, b) else b


def generar(db, opciones: OpcionesAsignacion) -> dict:
    inst = datos.construir_instancia(
        db, opciones.fecha_desde, opciones.fecha_hasta, opciones.umbral_sin_transporte,
        partido_ids=opciones.partido_ids, solo_completos=True,
    )

    tiempos = {}

    t = time.monotonic()
    sol = greedy.resolver(inst)
    tiempos["greedy"] = round(time.monotonic() - t, 3)
    fases = ["greedy"]

    cpsat_info = {"estado": "omitido"}
    if opciones.usar_cpsat and cpsat.DISPONIBLE:
        t = time.monotonic()
        sol_cp, cpsat_info = cpsat.resolver(inst, opciones.segundos_max, semilla=sol)
        tiempos["cpsat"] = round(time.monotonic() - t, 3)
        if sol_cp is not None:
            sol = _mejor(inst, sol, sol_cp)
            fases.append("cpsat")
    elif opciones.usar_cpsat:
        cpsat_info = {"estado": "ortools_no_disponible"}

    t = time.monotonic()
    sol_local, _ = local.mejorar(inst, sol, segundos_max=max(3.0, opciones.segundos_max / 4))
    tiempos["local"] = round(time.monotonic() - t, 3)
    sol = _mejor(inst, sol, sol_local)
    fases.append("local")

    transportes = comun.transportes_por_asignacion(inst, sol)
    asignaciones = []
    for (p_idx, rol), a_idx in sol.items():
        partido_id = inst.partidos[p_idx].id
        arbitro_id = inst.arbitros[a_idx].id
        t = transportes.get((arbitro_id, partido_id), {})
        asignaciones.append({
            "partido_id": partido_id,
            "arbitro_id": arbitro_id,
            "arbitro_nombre": inst.arbitros[a_idx].nombre,
            "rol": rol,
            "transporte": t.get("transporte", "con"),
            "conductor": t.get("conductor"),
            "recoge": t.get("recoge", []),
            "km": t.get("km", 0.0),
            "desde": t.get("desde"),
            "desde_tipo": t.get("desde_tipo", "domicilio"),
        })

    metricas = _metricas(inst, sol, tiempos, fases, cpsat_info)
    metricas["manual"] = _baseline_manual(db, inst)
    return {"asignaciones": asignaciones, "metricas": metricas}


def _baseline_manual(db, inst) -> dict:
    """Métricas de las designaciones existentes (método manual) para comparar."""
    ids = [p.id for p in inst.partidos]
    if not ids:
        return {"roles_cubiertos": 0, "km_total": 0.0, "km_medio": 0.0}
    arb = {a.id: a for a in inst.arbitros}
    part = {p.id: p for p in inst.partidos}
    rows = (
        db.query(models.Asignacion)
        .filter(models.Asignacion.partido_id.in_(ids))
        .all()
    )
    km = 0.0
    medibles = 0
    for r in rows:
        a = arb.get(r.arbitro_id)
        p = part.get(r.partido_id)
        if a and p and p.sede and a.lat is not None and a.lon is not None:
            km += distancias.haversine(a.lat, a.lon, p.sede[0], p.sede[1])
            medibles += 1
    return {
        "roles_cubiertos": len(rows),
        "km_total": round(km, 1),
        "km_medio": round(km / medibles, 2) if medibles else 0.0,
    }


def _metricas(inst, sol, tiempos, fases, cpsat_info):
    roles_tot = comun.roles_totales(inst)
    roles_cubribles = comun.roles_cubribles(inst)
    roles_cub = len(sol)

    # Partidos con todos sus roles requeridos cubiertos.
    partidos_cub = 0
    for p in inst.partidos:
        if p.roles and all((p.idx, rol) in sol for rol, _ in p.roles):
            partidos_cub += 1

    km = comun.km_total(inst, sol)
    return {
        "partidos_total": len(inst.partidos),
        "partidos_sin_franja": inst.n_sin_franja,
        "partidos_sin_sede": inst.n_sin_sede,
        "partidos_cubiertos": partidos_cub,
        "roles_totales": roles_tot,
        "roles_cubribles": roles_cubribles,
        "roles_cubiertos": roles_cub,
        "cobertura_pct": round(100 * roles_cub / roles_tot, 1) if roles_tot else 0.0,
        "km_total": round(km, 1),
        "km_medio": round(km / roles_cub, 2) if roles_cub else 0.0,
        "carga": comun.resumen_cargas(inst, sol),
        "emparejamientos_repetidos": comun.emparejamientos_repetidos(inst, sol),
        "tiempos_s": tiempos,
        "fases": fases,
        "cpsat": cpsat_info,
    }
