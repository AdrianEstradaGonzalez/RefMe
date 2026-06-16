"""Fase 1 — Generación inicial (greedy constructivo).

Asigna árbitros válidos respetando disponibilidad, nivel y horarios sin solape
(ocupación = antelación + duración + viaje entre sedes). El orden respeta la
prioridad de la categoría:
  1) los partidos de prioridad 1 se cubren por completo (todos sus roles);
  2) después se garantiza AL MENOS un árbitro en cada partido restante, en orden
     de prioridad (así, si faltan árbitros, los que quedan sin cubrir son los de
     menor prioridad);
  3) por último se completan los roles que falten.
Dentro de cada partido se asignan primero los árbitros que van por sus medios
(con coche o cercanos) y luego los que van 'sin transporte y lejos', que solo se
aceptan si ya hay en el partido un conductor que viva cerca y pueda recogerlos.
"""
from . import datos


def _en_conflicto(inst, asig_arb, a_idx, p):
    """True si asignar `a_idx` a `p` solapa con alguno de sus partidos.

    El tiempo de viaje entre sedes se calcula a la velocidad del medio del árbitro
    (coche o andando), de modo que solo se encadenan partidos si da tiempo real.
    """
    arb = inst.arbitros[a_idx]
    for q_idx in asig_arb.get(a_idx, ()):
        q = inst.partidos[q_idx]
        if datos.conflictan(q, p, datos.velocidad_par(arb, q, p)):
            return True
    return False


def _hay_conductor_cercano(inst, conductores, a_idx):
    """True si algún conductor ya asignado vive cerca del árbitro y podría llevarlo."""
    arb = inst.arbitros[a_idx]
    return any(datos.pueden_compartir(inst.arbitros[c], arb) for c in conductores)


def _elegir(inst, p, rol, asignados_p, conductores_p, asig_arb, carga, permitir_lejos):
    mejor, mejor_clave = None, None
    for a_idx, dist in p.candidatos.get(rol, []):
        if a_idx in asignados_p:
            continue
        tipo = p.cand_tipo[rol].get(a_idx)
        if tipo == "lejos":
            if not permitir_lejos or not _hay_conductor_cercano(inst, conductores_p, a_idx):
                continue
        if _en_conflicto(inst, asig_arb, a_idx, p):
            continue
        d = dist if dist is not None else 9999.0
        clave = (d + 0.5 * carga[a_idx], carga[a_idx], d)  # distancia + equidad
        if mejor_clave is None or clave < mejor_clave:
            mejor_clave, mejor = clave, a_idx
    return mejor


def resolver(inst) -> dict:
    sol = {}
    asig_arb = {}                       # a_idx -> [p_idx]
    carga = [0] * len(inst.arbitros)
    asignados = {}                      # p_idx -> [a_idx]
    conductores = {}                    # p_idx -> [a_idx con coche]

    def asignar(p, rol, a_idx):
        sol[(p.idx, rol)] = a_idx
        asignados.setdefault(p.idx, []).append(a_idx)
        if p.cand_tipo[rol].get(a_idx) == "con":
            conductores.setdefault(p.idx, []).append(a_idx)
        asig_arb.setdefault(a_idx, []).append(p.idx)
        carga[a_idx] += 1

    def completar(p):
        asignados_p = asignados.setdefault(p.idx, [])
        conductores_p = conductores.setdefault(p.idx, [])
        roles_ord = sorted(p.roles, key=lambda r: -r[1])
        # Pase 1: árbitros con coche o cercanos.
        pendientes = []
        for rol, _ in roles_ord:
            if (p.idx, rol) in sol:
                continue
            a = _elegir(inst, p, rol, asignados_p, conductores_p, asig_arb, carga,
                        permitir_lejos=False)
            if a is None:
                pendientes.append(rol)
            else:
                asignar(p, rol, a)
        # Pase 2: árbitros sin transporte y lejos (necesitan conductor cercano).
        for rol in pendientes:
            if (p.idx, rol) in sol:
                continue
            a = _elegir(inst, p, rol, asignados_p, conductores_p, asig_arb, carga,
                        permitir_lejos=True)
            if a is not None:
                asignar(p, rol, a)

    def garantizar_uno(p):
        if asignados.get(p.idx):
            return
        asignados_p = asignados.setdefault(p.idx, [])
        conductores_p = conductores.setdefault(p.idx, [])
        for rol, _ in sorted(p.roles, key=lambda r: -r[1]):
            if (p.idx, rol) in sol:
                continue
            a = _elegir(inst, p, rol, asignados_p, conductores_p, asig_arb, carga,
                        permitir_lejos=False)
            if a is not None:
                asignar(p, rol, a)
                return

    activos = [p for p in inst.partidos if p.franja is not None]
    activos.sort(key=lambda p: (
        p.prioridad, p.fecha, p.inicio_min if p.inicio_min is not None else 0,
    ))
    prio1 = [p for p in activos if p.prioridad == 1]
    resto = [p for p in activos if p.prioridad != 1]

    # 1) Prioridad 1: cobertura completa (todos los roles, obligatorios).
    for p in prio1:
        completar(p)
    # 2) Resto: al menos un árbitro por partido, en orden de prioridad.
    for p in resto:
        garantizar_uno(p)
    # 3) Resto: completar los roles que falten.
    for p in resto:
        completar(p)
    return sol
