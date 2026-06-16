"""Fase 2 — Optimización con el solver CP-SAT (Google OR-Tools).

Restricciones duras:
  - Cada rol requerido se cubre con un árbitro (o queda sin cubrir, penalizado).
  - Un árbitro, a lo sumo un rol por partido.
  - Sin solapamiento horario: para cada árbitro, partidos que se cruzan en el
    tiempo (ocupación + viaje) son mutuamente excluyentes.
  - Coche compartido: un árbitro "sin transporte y lejos" solo puede asignarse a
    un partido que tenga asignado un conductor ("con transporte") que viva cerca
    de su domicilio (≤ umbral de recogida) y pueda llevarlo y traerlo.

Objetivo: minimizar Σ km + penalización(no cubiertos) + carga máxima (equidad).
La penalización por falta de cobertura es escalonada por prioridad de categoría:
  - Prioridad 1: todos los roles (casi) obligatorios.
  - Prioridad 2..9: prioriza que el partido tenga AL MENOS un árbitro.
  - Prioridad > 9: best-effort.
Se siembra con la solución greedy (`AddHint`).
"""
try:
    from ortools.sat.python import cp_model
    DISPONIBLE = True
except ImportError:  # pragma: no cover
    DISPONIBLE = False

from . import datos

# Penalización por falta de cobertura, escalonada por prioridad de la categoría.
# El orden de magnitud garantiza la jerarquía frente a los km (≤ unos cientos):
#   prioridad 1 (cada rol)  ≫  partido 2..9 vacío  ≫  cualquier otro rol  >  km.
W_P1_ROL = 1_000_000     # cada rol sin cubrir de una categoría de prioridad 1
W_VACIO_2_9 = 100_000    # un partido de prioridad 2..9 sin NINGÚN árbitro
W_ROL_RESTO = 2_000      # cualquier otro rol sin cubrir
W_EQUIDAD = 5
COSTE_DESCONOCIDO = 15


def resolver(inst, segundos_max=20.0, semilla=None):
    if not DISPONIBLE:
        return None, {"estado": "ortools_no_disponible"}

    modelo = cp_model.CpModel()
    x = {}                  # (p_idx, rol, a_idx) -> var
    no_cubierto = {}        # (p_idx, rol) -> var
    por_arbitro = {}        # a_idx -> [vars]  (carga)
    por_arb_part = {}       # (a_idx, p_idx) -> [vars]
    por_part_arb = {}       # (p_idx, a_idx) -> [vars]
    con_por_part = {}       # p_idx -> [(a_idx, var 'con')]
    vars_por_part = {}      # p_idx -> [todas las vars del partido]
    lejos_vars = []         # (p_idx, a_idx, var)
    terminos = []           # (var, coste)

    for p in inst.partidos:
        if p.franja is None:
            continue
        for rol, _rango in p.roles:
            vars_rol = []
            for a_idx, dist in p.candidatos.get(rol, []):
                v = modelo.NewBoolVar(f"x_{p.idx}_{rol}_{a_idx}")
                x[(p.idx, rol, a_idx)] = v
                vars_rol.append(v)
                vars_por_part.setdefault(p.idx, []).append(v)
                terminos.append((v, int(round(dist)) if dist is not None else COSTE_DESCONOCIDO))
                por_arbitro.setdefault(a_idx, []).append(v)
                por_arb_part.setdefault((a_idx, p.idx), []).append(v)
                por_part_arb.setdefault((p.idx, a_idx), []).append(v)
                tipo = p.cand_tipo[rol].get(a_idx)
                if tipo == "con":
                    con_por_part.setdefault(p.idx, []).append((a_idx, v))
                elif tipo == "lejos":
                    lejos_vars.append((p.idx, a_idx, v))
            u = modelo.NewBoolVar(f"u_{p.idx}_{rol}")
            no_cubierto[(p.idx, rol)] = u
            modelo.Add(sum(vars_rol) + u == 1)

    # Un árbitro, a lo sumo un rol por partido.
    for vs in por_part_arb.values():
        if len(vs) > 1:
            modelo.Add(sum(vs) <= 1)

    # Sin solapamiento horario (por árbitro, partidos que conflictan).
    cand_part = {}
    for (a_idx, p_idx) in por_arb_part:
        cand_part.setdefault(a_idx, []).append(p_idx)
    for a_idx, plist in cand_part.items():
        arb = inst.arbitros[a_idx]
        plist = sorted(set(plist), key=lambda pi: inst.partidos[pi].inicio_min or 0)
        for i in range(len(plist)):
            p1 = inst.partidos[plist[i]]
            for j in range(i + 1, len(plist)):
                p2 = inst.partidos[plist[j]]
                if p1.fecha != p2.fecha:
                    continue
                if datos.conflictan(p1, p2, datos.velocidad_par(arb, p1, p2)):
                    modelo.Add(
                        sum(por_arb_part[(a_idx, p1.idx)]) +
                        sum(por_arb_part[(a_idx, p2.idx)]) <= 1
                    )

    # Coche compartido: un 'lejos' exige que se asigne en el mismo partido un
    # conductor ('con') que viva cerca de su domicilio (≤ umbral de recogida),
    # para que pueda llevarlo y traerlo de vuelta.
    for p_idx, a_idx, v in lejos_vars:
        pasajero = inst.arbitros[a_idx]
        cercanos = [cv for ca, cv in con_por_part.get(p_idx, [])
                    if datos.pueden_compartir(inst.arbitros[ca], pasajero)]
        if cercanos:
            modelo.Add(v <= sum(cercanos))
        else:
            modelo.Add(v == 0)  # sin conductor cercano posible

    # Penalización por falta de cobertura, escalonada por prioridad de categoría.
    pen = []
    for p in inst.partidos:
        if p.franja is None:
            continue
        if p.prioridad == 1:
            # Todos los roles (casi) obligatorios.
            for rol, _ in p.roles:
                u = no_cubierto.get((p.idx, rol))
                if u is not None:
                    pen.append((u, W_P1_ROL))
            continue
        # Prioridad 2..9 y > 9: los roles sin cubrir penalizan moderadamente...
        for rol, _ in p.roles:
            u = no_cubierto.get((p.idx, rol))
            if u is not None:
                pen.append((u, W_ROL_RESTO))
        # ...y, para 2..9, se castiga con fuerza que el partido quede SIN nadie.
        if p.prioridad <= 9:
            vars_p = vars_por_part.get(p.idx, [])
            if vars_p:
                vacio = modelo.NewBoolVar(f"vacio_{p.idx}")
                modelo.Add(sum(vars_p) + vacio >= 1)
                pen.append((vacio, W_VACIO_2_9))

    # Equidad: minimizar la carga máxima.
    carga_max = modelo.NewIntVar(0, len(inst.partidos), "carga_max")
    for vs in por_arbitro.values():
        modelo.Add(carga_max >= sum(vs))

    modelo.Minimize(
        sum(c * v for v, c in terminos)
        + sum(w * v for v, w in pen)
        + W_EQUIDAD * carga_max
    )

    if semilla:
        asignados = set()
        for (p_idx, rol), a_idx in semilla.items():
            v = x.get((p_idx, rol, a_idx))
            if v is not None:
                modelo.AddHint(v, 1)
                asignados.add((p_idx, rol))
        for clave, u in no_cubierto.items():
            modelo.AddHint(u, 0 if clave in asignados else 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(segundos_max)
    solver.parameters.num_search_workers = 8
    estado = solver.Solve(modelo)

    if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, {"estado": "sin_solucion", "codigo": int(estado)}

    sol = {}
    for (p_idx, rol, a_idx), v in x.items():
        if solver.Value(v) == 1:
            sol[(p_idx, rol)] = a_idx

    info = {
        "estado": "optimo" if estado == cp_model.OPTIMAL else "factible",
        "objetivo": solver.ObjectiveValue(),
        "variables": len(x),
        "segundos": round(solver.WallTime(), 2),
    }
    return sol, info
