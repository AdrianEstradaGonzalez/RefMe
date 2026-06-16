"""Fase 3 — Mejora heurística (búsqueda local).

Sobre la mejor solución, aplica iterativamente RELLENO, MOVE y SWAP que reduzcan
el coste por partido (considerando el coche compartido) sin romper restricciones:
horarios sin solape y, en cada partido, todo "lejos" con un conductor presente.
"""
import time

from . import comun, datos


def _conflicto(inst, asig_arb, a_idx, p_target, excluir):
    arb = inst.arbitros[a_idx]
    for q in asig_arb.get(a_idx, ()):
        if q == excluir:
            continue
        qp = inst.partidos[q]
        if datos.conflictan(qp, p_target, datos.velocidad_par(arb, qp, p_target)):
            return True
    return False


def _factible_match(inst, p_idx, asignados):
    """Cada 'lejos' del partido debe tener un conductor ('con') que viva cerca
    (≤ umbral de recogida) y pueda llevarlo y traerlo."""
    ct = inst.partidos[p_idx].cand_tipo
    drivers = [a for rol, a in asignados if ct[rol].get(a) == "con"]
    for rol, a in asignados:
        if ct[rol].get(a) == "lejos":
            pasajero = inst.arbitros[a]
            if not any(datos.pueden_compartir(inst.arbitros[c], pasajero) for c in drivers):
                return False
    return True


def _asignados(sol, p_idx):
    return [(rol, a) for (pi, rol), a in sol.items() if pi == p_idx]


def mejorar(inst, sol, segundos_max=5.0):
    sol = dict(sol)
    asig_arb = {}
    for (p_idx, _rol), a in sol.items():
        asig_arb.setdefault(a, []).append(p_idx)

    t0 = time.monotonic()
    pasos = 0
    while time.monotonic() - t0 < segundos_max:
        cambio = _rellenar(inst, sol, asig_arb)
        cambio |= _mover(inst, sol, asig_arb)
        cambio |= _intercambiar(inst, sol, asig_arb)
        if cambio:
            pasos += 1
        else:
            break
    return sol, {"pasos": pasos}


def _rellenar(inst, sol, asig_arb):
    cambio = False
    for p in inst.partidos:
        if p.franja is None:
            continue
        asign = _asignados(sol, p.idx)
        ocupados = {a for _r, a in asign}
        drivers = [a for r, a in asign if p.cand_tipo[r].get(a) == "con"]
        for rol, _ in p.roles:
            if (p.idx, rol) in sol:
                continue
            for a_idx, _d in p.candidatos.get(rol, []):
                if a_idx in ocupados:
                    continue
                tipo = p.cand_tipo[rol].get(a_idx)
                if tipo == "lejos" and not any(
                    datos.pueden_compartir(inst.arbitros[c], inst.arbitros[a_idx])
                    for c in drivers
                ):
                    continue
                if _conflicto(inst, asig_arb, a_idx, p, excluir=None):
                    continue
                sol[(p.idx, rol)] = a_idx
                asig_arb.setdefault(a_idx, []).append(p.idx)
                ocupados.add(a_idx)
                if tipo == "con":
                    drivers.append(a_idx)
                cambio = True
                break
    return cambio


def _mover(inst, sol, asig_arb):
    cambio = False
    for (p_idx, rol), a in list(sol.items()):
        p = inst.partidos[p_idx]
        asign = _asignados(sol, p_idx)
        ocupados = {x for _r, x in asign}
        km_act = comun.km_partido(inst, p_idx, asign)
        for a2, _d in p.candidatos.get(rol, []):
            if a2 == a or a2 in ocupados:
                continue
            if _conflicto(inst, asig_arb, a2, p, excluir=None):
                continue
            nuevos = [(r, (a2 if (r, x) == (rol, a) else x)) for r, x in asign]
            if not _factible_match(inst, p_idx, nuevos):
                continue
            if comun.km_partido(inst, p_idx, nuevos) < km_act - 1e-9:
                sol[(p_idx, rol)] = a2
                asig_arb[a].remove(p_idx)
                asig_arb.setdefault(a2, []).append(p_idx)
                cambio = True
                break
    return cambio


def _intercambiar(inst, sol, asig_arb):
    cambio = False
    claves = sorted(sol.keys(),
                    key=lambda k: -comun.km_partido(inst, k[0], _asignados(sol, k[0])))
    for (p1, r1) in claves:
        a1 = sol.get((p1, r1))
        if a1 is None:
            continue
        P1 = inst.partidos[p1]
        for (p2, r2) in list(sol.keys()):
            if p2 == p1:
                continue
            a2 = sol.get((p2, r2))
            if a2 is None or a2 == a1:
                continue
            P2 = inst.partidos[p2]
            # Candidatos cruzados.
            if a2 not in P1.cand_dist.get(r1, {}) or a1 not in P2.cand_dist.get(r2, {}):
                continue
            if _conflicto(inst, asig_arb, a1, P2, excluir=p1):
                continue
            if _conflicto(inst, asig_arb, a2, P1, excluir=p2):
                continue
            asg1 = [(r, (a2 if (r, x) == (r1, a1) else x)) for r, x in _asignados(sol, p1)]
            asg2 = [(r, (a1 if (r, x) == (r2, a2) else x)) for r, x in _asignados(sol, p2)]
            if a1 in {x for _r, x in _asignados(sol, p2)} or a2 in {x for _r, x in _asignados(sol, p1)}:
                continue
            if not _factible_match(inst, p1, asg1) or not _factible_match(inst, p2, asg2):
                continue
            antes = (comun.km_partido(inst, p1, _asignados(sol, p1)) +
                     comun.km_partido(inst, p2, _asignados(sol, p2)))
            desp = comun.km_partido(inst, p1, asg1) + comun.km_partido(inst, p2, asg2)
            if desp < antes - 1e-9:
                sol[(p1, r1)] = a2
                sol[(p2, r2)] = a1
                asig_arb[a1].remove(p1); asig_arb[a1].append(p2)
                asig_arb[a2].remove(p2); asig_arb[a2].append(p1)
                cambio = True
                break
    return cambio
