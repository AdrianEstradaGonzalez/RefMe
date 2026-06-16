"""Representación de una solución y análisis de desplazamientos (coche compartido).

Una solución es un dict `{(partido_idx, rol): arbitro_idx}`.

`analizar` reconstruye, de forma cronológica, el recorrido de cada árbitro:
parte de su domicilio y, si encadena partidos, del polideportivo anterior. En
cada partido, los árbitros disponibles "con transporte" pueden recoger a los que
van "sin transporte y lejos" (tipo 'lejos'), contabilizando el desvío. Los
kilómetros totales y los itinerarios individuales se derivan de este análisis.
"""
from statistics import pstdev

from . import datos
from .distancias import haversine


def cargas(inst, sol):
    c = [0] * len(inst.arbitros)
    for a_idx in sol.values():
        c[a_idx] += 1
    return c


def roles_totales(inst) -> int:
    return sum(len(p.roles) for p in inst.partidos)


def roles_cubribles(inst) -> int:
    n = 0
    for p in inst.partidos:
        for rol, _ in p.roles:
            if p.candidatos.get(rol):
                n += 1
    return n


def emparejamientos_repetidos(inst, sol) -> int:
    vistos = {}
    for (p_idx, _rol), a_idx in sol.items():
        p = inst.partidos[p_idx]
        for equipo in (p.local, p.visitante):
            vistos[(a_idx, equipo)] = vistos.get((a_idx, equipo), 0) + 1
    return sum(v - 1 for v in vistos.values() if v > 1)


def resumen_cargas(inst, sol):
    c = cargas(inst, sol)
    activos = [x for x in c if x > 0]
    if not activos:
        return {"min": 0, "max": 0, "media": 0.0, "desv": 0.0, "arbitros_usados": 0}
    return {
        "min": min(activos), "max": max(activos),
        "media": round(sum(activos) / len(activos), 2),
        "desv": round(pstdev(c), 2), "arbitros_usados": len(activos),
    }


def _km(a, b):
    if not a or not b:
        return 0.0
    return haversine(a[0], a[1], b[0], b[1])


def _ruta_km(origen, paradas, destino):
    """Longitud (km) de origen → paradas (orden vecino más próximo) → destino."""
    if origen is None or destino is None:
        # Sin coordenadas fiables: al menos cuenta el tramo medible.
        return _km(origen, destino)
    actual = origen
    pendientes = [p for p in paradas if p]
    total = 0.0
    orden = []
    while pendientes:
        nxt = min(pendientes, key=lambda p: _km(actual, p))
        total += _km(actual, nxt)
        actual = nxt
        orden.append(nxt)
        pendientes.remove(nxt)
    total += _km(actual, destino)
    return total


def _tipo(inst, p_idx, rol, a_idx):
    return inst.partidos[p_idx].cand_tipo.get(rol, {}).get(a_idx)


def analizar(inst, sol):
    """Reconstruye recorridos y coche compartido. Devuelve un dict con:
       km_total, tramos {(a_idx,p_idx): info}, y orden cronológico por árbitro."""
    # Partidos por árbitro, en orden cronológico.
    por_arb = {}
    for (p_idx, rol), a_idx in sol.items():
        por_arb.setdefault(a_idx, []).append((inst.partidos[p_idx].inicio_min or 0, p_idx, rol))
    for a_idx in por_arb:
        por_arb[a_idx].sort()

    # Origen de cada árbitro en cada partido: domicilio (inicio del día) o la
    # sede del partido anterior si lo encadena el MISMO día y con poca espera
    # (≤ MAX_ESPERA_ENCADENADO_MIN entre comienzos); si la espera es mayor, se
    # supone que vuelve a su domicilio antes de ir otra vez. El 'tipo' distingue
    # en la UI: domicilio | otra sede | misma sede (ya estaba).
    origen = {}  # (a_idx, p_idx) -> (coords, etiqueta, tipo)
    for a_idx, lst in por_arb.items():
        prev, prev_fecha, prev_inicio = None, None, None
        for _t, p_idx, _rol in lst:
            p = inst.partidos[p_idx]
            espera = (
                p.inicio_min - prev_inicio
                if p.inicio_min is not None and prev_inicio is not None
                else None
            )
            encadena = (
                prev is not None and p.fecha == prev_fecha
                and espera is not None and espera <= datos.MAX_ESPERA_ENCADENADO_MIN
            )
            if not encadena:
                origen[(a_idx, p_idx)] = (inst.arbitros[a_idx].casa, "su domicilio", "domicilio")
            else:
                pp = inst.partidos[prev]
                tipo = "mismo_poli" if (pp.sede and p.sede and pp.sede == p.sede) else "sede_anterior"
                origen[(a_idx, p_idx)] = (pp.sede, pp.sede_nombre or "sede anterior", tipo)
            prev, prev_fecha, prev_inicio = p_idx, p.fecha, p.inicio_min

    # Asignados por partido (con su tipo de transporte).
    asign_por_part = {}
    for (p_idx, rol), a_idx in sol.items():
        asign_por_part.setdefault(p_idx, []).append((rol, a_idx, _tipo(inst, p_idx, rol, a_idx)))

    tramos = {}      # (a_idx, p_idx) -> {km, modo, ...}
    for p_idx, asign in asign_por_part.items():
        p = inst.partidos[p_idx]
        conductores = [a for _r, a, t in asign if t == "con"]
        pasajeros = [a for _r, a, t in asign if t == "lejos"]
        # 'cerca' o tipo desconocido (designaciones manuales) → van por su cuenta.
        propios = [a for _r, a, t in asign if t not in ("con", "lejos")]

        # Asignar cada pasajero al conductor cercano con menor desvío de recogida.
        recoge = {c: [] for c in conductores}
        for pa in pasajeros:
            o_pa = origen[(pa, p_idx)][0]
            cercanos = [c for c in conductores
                        if datos.pueden_compartir(inst.arbitros[c], inst.arbitros[pa])]
            if cercanos:
                mejor = min(
                    cercanos,
                    key=lambda c: _km(origen[(c, p_idx)][0], o_pa) + _km(o_pa, p.sede),
                )
                recoge[mejor].append(pa)
            else:
                # Sin conductor cercano (no debería ocurrir): viaja por su cuenta.
                tramos[(pa, p_idx)] = {
                    "km": _km(o_pa, p.sede), "modo": "propio",
                    "origen": origen[(pa, p_idx)][1],
                    "origen_tipo": origen[(pa, p_idx)][2],
                }

        for c in conductores:
            o_c = origen[(c, p_idx)][0]
            paradas = [origen[(pa, p_idx)][0] for pa in recoge[c]]
            km = _ruta_km(o_c, paradas, p.sede)
            tramos[(c, p_idx)] = {
                "km": km, "modo": "conduce" if recoge[c] else "propio",
                "origen": origen[(c, p_idx)][1],
                "origen_tipo": origen[(c, p_idx)][2],
                "recoge": [inst.arbitros[pa].nombre for pa in recoge[c]],
            }
            for pa in recoge[c]:
                tramos[(pa, p_idx)] = {
                    "km": 0.0, "modo": "pasajero",
                    "origen": origen[(pa, p_idx)][1],
                    "origen_tipo": origen[(pa, p_idx)][2],
                    "conductor": inst.arbitros[c].nombre,
                }
        for c in propios:
            o_c = origen[(c, p_idx)][0]
            tramos[(c, p_idx)] = {
                "km": _km(o_c, p.sede), "modo": "propio",
                "origen": origen[(c, p_idx)][1],
                "origen_tipo": origen[(c, p_idx)][2],
            }

    # Etiqueta de transporte para mostrar junto al árbitro:
    #   'con'      → va con su propio vehículo (conduzca o no a otros).
    #   'llevan'   → sin transporte: le recoge un compañero (ver 'conductor').
    #   'andando'  → sin transporte y el trayecto (desde domicilio u otra sede)
    #                está dentro del límite andable (UMBRAL_SIN_TRANSPORTE_KM).
    #   'necesita' → sin transporte pero el trayecto supera ese límite: no puede
    #                ir andando y no tiene quien le lleve → requiere solución.
    for (a_idx, p_idx), tr in tramos.items():
        if tr["modo"] == "pasajero":
            tr["transporte"] = "llevan"
        elif tr["modo"] == "conduce":
            tr["transporte"] = "con"
        else:  # 'propio'
            estado = inst.arbitros[a_idx].disp.get(
                (inst.partidos[p_idx].fecha, inst.partidos[p_idx].franja)
            )
            if estado == "sin_transporte":
                tr["transporte"] = (
                    "andando" if tr["km"] <= datos.UMBRAL_SIN_TRANSPORTE_KM else "necesita"
                )
            else:
                tr["transporte"] = "con"

    km_total = sum(t["km"] for t in tramos.values())
    return {"km_total": km_total, "tramos": tramos, "por_arbitro": por_arb}


def transportes_por_asignacion(inst, sol):
    """{(arbitro_id, partido_id): {detalle del desplazamiento}} para la UI.

    Resume, por árbitro y partido: cómo se desplaza (vehículo propio, le llevan
    y quién, o andando), cuántos km recorre y desde dónde sale (domicilio, otra
    sede o la misma sede si ya estaba allí). Modela el coche compartido global.
    """
    info = analizar(inst, sol)
    out = {}
    for (a_idx, p_idx), tr in info["tramos"].items():
        out[(inst.arbitros[a_idx].id, inst.partidos[p_idx].id)] = {
            "transporte": tr.get("transporte", "con"),
            "conductor": tr.get("conductor"),
            "recoge": tr.get("recoge", []),
            "km": round(tr.get("km", 0.0), 1),
            "desde": tr.get("origen"),
            "desde_tipo": tr.get("origen_tipo", "domicilio"),
        }
    return out


def km_total(inst, sol) -> float:
    return analizar(inst, sol)["km_total"]


# ----- Coste por partido (para la búsqueda local, con origen = domicilio) -----
def km_partido(inst, p_idx, asignados):
    """Km del partido asumiendo que cada árbitro sale de su domicilio.

    `asignados` = lista de (rol, a_idx). Modela el coche compartido del partido.
    """
    p = inst.partidos[p_idx]
    casa = lambda a: inst.arbitros[a].casa
    conductores = [a for r, a in asignados if _tipo(inst, p_idx, r, a) == "con"]
    pasajeros = [a for r, a in asignados if _tipo(inst, p_idx, r, a) == "lejos"]
    propios = [a for r, a in asignados if _tipo(inst, p_idx, r, a) not in ("con", "lejos")]

    recoge = {c: [] for c in conductores}
    sin_coche = []
    for pa in pasajeros:
        cercanos = [c for c in conductores
                    if datos.pueden_compartir(inst.arbitros[c], inst.arbitros[pa])]
        if cercanos:
            mejor = min(cercanos,
                        key=lambda c: _km(casa(c), casa(pa)) + _km(casa(pa), p.sede))
            recoge[mejor].append(pa)
        else:
            sin_coche.append(pa)
    total = 0.0
    for c in conductores:
        total += _ruta_km(casa(c), [casa(pa) for pa in recoge[c]], p.sede)
    for c in propios:
        total += _km(casa(c), p.sede)
    # Pasajeros sin conductor cercano: viajan por su cuenta (penalización implícita).
    for pa in sin_coche:
        total += _km(casa(pa), p.sede)
    return total


def _hhmm(absmin):
    if absmin is None:
        return None
    m = absmin % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def itinerario(inst, sol, arbitro_id):
    """Resumen cronológico de desplazamientos de un árbitro (coche compartido)."""
    a_idx = next((a.idx for a in inst.arbitros if a.id == arbitro_id), None)
    if a_idx is None:
        return None
    info = analizar(inst, sol)
    tramos = info["tramos"]
    salida = []
    for _t, p_idx, rol in info["por_arbitro"].get(a_idx, []):
        p = inst.partidos[p_idx]
        tr = tramos.get((a_idx, p_idx), {})
        salida.append({
            "partido_id": p.id,
            "fecha": str(p.fecha),
            "hora": _hhmm(p.inicio_min),
            "llegada": _hhmm(p.ini_ocup),
            "rol": rol,
            "sede": p.sede_nombre,
            "local": p.local,
            "visitante": p.visitante,
            "origen": tr.get("origen"),
            "origen_tipo": tr.get("origen_tipo", "domicilio"),
            "modo": tr.get("modo", "propio"),
            "transporte": tr.get("transporte", "con"),
            "recoge": tr.get("recoge", []),
            "conductor": tr.get("conductor"),
            "km": round(tr.get("km", 0.0), 1),
        })
    return {
        "arbitro_id": arbitro_id,
        "arbitro": inst.arbitros[a_idx].nombre,
        "km_total": round(sum(s["km"] for s in salida), 1),
        "tramos": salida,
    }

