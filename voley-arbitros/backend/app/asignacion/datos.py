"""Construcción de la instancia del problema a partir de la base de datos.

Reúne árbitros (rango, coordenadas, disponibilidad) y partidos (horario real,
sede, roles exigidos) en estructuras en memoria, y precalcula los candidatos
válidos por (partido, rol). Es la entrada común para las tres fases.

Modelo temporal (RF2.1 / no solapamiento):
  - Antelación: el árbitro debe estar 1 h antes en partidos de prioridad 1 y
    30 min antes en el resto.
  - Duración media: 1 h 30 min si la prioridad de la categoría es <= 9; 1 h si > 9.
  - Ocupación = [inicio - antelación, inicio + duración]. Dos partidos solapan
    para un árbitro si sus ocupaciones se cruzan o no da tiempo a viajar entre
    sedes (a `VELOCIDAD_KMH`).

Coche compartido (RF2.3): un árbitro disponible "con transporte" puede recoger
a árbitros "sin transporte" del mismo partido. Por eso un candidato sin coche a
una sede lejana se admite como tipo "lejos" (solo válido si el partido tiene un
conductor asignado); cerca puede ir por sus medios ("cerca").
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import joinedload

from .. import models
from ..parsing import FRANJAS
from . import conflictos, distancias, niveles

# Distancia máxima (km) que un árbitro sin coche puede cubrir por sus medios
# (andando), ya sea desde su domicilio o desde otro polideportivo.
UMBRAL_SIN_TRANSPORTE_KM = 10.0
# Distancia máxima (km) entre los DOMICILIOS de dos árbitros para que uno pueda
# recoger al otro en su coche. Como el conductor sale de casa, va al partido y
# vuelve a su casa al terminar, llevar y traer de vuelta a un compañero solo es
# lógico si viven cerca. Por defecto, el mismo radio que el andable.
UMBRAL_RECOGIDA_KM = 10.0
# Velocidades medias para convertir distancia en tiempo de viaje: en coche
# (árbitro con transporte) o andando (sin transporte / va por sus medios).
VELOCIDAD_KMH = 70.0
VELOCIDAD_ANDANDO_KMH = 5.0
# Máximo (min) entre el comienzo de un partido y el del siguiente para suponer
# que el árbitro permanece en la sede/zona; si se supera, se asume que vuelve a
# su domicilio entre partidos.
MAX_ESPERA_ENCADENADO_MIN = 180


def franja_de_hora(hora):
    """Índice de franja (0..3) que contiene la hora 'HH:MM', o None."""
    m = _minutos_dia(hora)
    if m is None:
        return None
    h = m // 60
    if 9 <= h < 12:
        return 0
    if 12 <= h < 15:
        return 1
    if 15 <= h < 18:
        return 2
    if 18 <= h < 22:
        return 3
    return None


def _minutos_dia(hora):
    """Minutos desde medianoche de 'HH:MM' (None si no procede o es 00:00)."""
    if not hora:
        return None
    try:
        partes = str(hora).split(":")
        m = int(partes[0]) * 60 + (int(partes[1]) if len(partes) > 1 else 0)
    except (ValueError, IndexError):
        return None
    return m if m > 0 else None


def antelacion_de(prioridad) -> int:
    """Minutos de antelación: 60 para prioridad 1, 30 para el resto."""
    return 60 if prioridad == 1 else 30


def duracion_de(prioridad) -> int:
    """Duración media en minutos: 90 si prioridad <= 9, 60 si > 9."""
    return 90 if (prioridad or 99) <= 9 else 60


def viaje_min(sede_a, sede_b, velocidad_kmh=VELOCIDAD_KMH) -> float:
    """Minutos de viaje entre dos sedes (0 si misma sede o sin coords).

    La velocidad por defecto es la de coche; pásese la de andar para árbitros
    sin transporte (el tiempo se estima por los mismos km, a otra velocidad).
    """
    if not sede_a or not sede_b or sede_a == sede_b:
        return 0.0
    km = distancias.haversine(sede_a[0], sede_a[1], sede_b[0], sede_b[1])
    return km / velocidad_kmh * 60.0


@dataclass
class ArbitroInst:
    idx: int
    id: int
    nombre: str
    rango: int
    lat: float | None
    lon: float | None
    # (fecha, franja_idx) -> 'con_transporte'|'sin_transporte'|'no_disponible'
    disp: dict

    @property
    def casa(self):
        return (self.lat, self.lon) if self.lat is not None and self.lon is not None else None


@dataclass
class PartidoInst:
    idx: int
    id: int
    fecha: date
    franja: int | None
    categoria_id: int | None
    prioridad: int
    local: str
    visitante: str
    sede: tuple | None  # (lat, lon)
    sede_nombre: str | None
    roles: list         # [(rol, rango_min)]
    inicio_min: int | None = None  # minutos absolutos del inicio
    ini_ocup: int | None = None    # ocupación: inicio - antelación
    fin_ocup: int | None = None    # ocupación: inicio + duración
    antelacion: int = 30
    duracion: int = 60
    candidatos: dict = field(default_factory=dict)   # {rol: [(a_idx, dist|None)]}
    cand_dist: dict = field(default_factory=dict)    # {rol: {a_idx: dist|None}}
    cand_tipo: dict = field(default_factory=dict)    # {rol: {a_idx: 'con'|'cerca'|'lejos'}}


@dataclass
class Instancia:
    arbitros: list
    partidos: list
    n_sin_franja: int = 0
    n_sin_sede: int = 0
    n_excluidos: int = 0


def es_designable(partido, sede, franja) -> bool:
    """Designable = tiene categoría, franja horaria reconocible y sede."""
    return partido.categoria is not None and franja is not None and sede is not None


def conflictan(p1: PartidoInst, p2: PartidoInst, velocidad_kmh=VELOCIDAD_KMH) -> bool:
    """True si un mismo árbitro no puede hacer ambos partidos (solape o viaje).

    `velocidad_kmh` es la del medio del árbitro (coche/andando): determina cuánto
    tarda en ir de una sede a otra y, por tanto, si le da tiempo entre partidos.
    """
    if p1.ini_ocup is None or p2.ini_ocup is None:
        return False
    primero, segundo = (p1, p2) if p1.inicio_min <= p2.inicio_min else (p2, p1)
    # El segundo debe empezar (con su antelación) tras terminar el primero + viaje.
    return segundo.ini_ocup < primero.fin_ocup + viaje_min(
        primero.sede, segundo.sede, velocidad_kmh
    )


def velocidad_par(arb: ArbitroInst, p1: PartidoInst, p2: PartidoInst) -> float:
    """Velocidad (km/h) del desplazamiento del árbitro entre dos partidos: en
    coche si dispone de transporte en alguna de las dos franjas; si no, andando."""
    tiene_coche = (
        arb.disp.get((p1.fecha, p1.franja)) == "con_transporte"
        or arb.disp.get((p2.fecha, p2.franja)) == "con_transporte"
    )
    return VELOCIDAD_KMH if tiene_coche else VELOCIDAD_ANDANDO_KMH


def pueden_compartir(conductor: ArbitroInst, pasajero: ArbitroInst,
                     umbral=UMBRAL_RECOGIDA_KM) -> bool:
    """True si el conductor puede recoger al pasajero y traerlo de vuelta.

    Exige que ambos tengan domicilio conocido y vivan a no más de `umbral` km el
    uno del otro: solo así es lógico que vayan juntos al partido y regresen
    juntos a casa. No comprueba aquí horarios ni que coincidan en el partido (eso
    lo garantizan las restricciones de asignación)."""
    ca, pa = conductor.casa, pasajero.casa
    if ca is None or pa is None:
        return False
    return distancias.haversine(ca[0], ca[1], pa[0], pa[1]) <= umbral


def construir_instancia(db, fecha_desde: date, fecha_hasta: date,
                        umbral_sin_transporte=UMBRAL_SIN_TRANSPORTE_KM,
                        partido_ids=None, solo_completos=True) -> Instancia:
    # --- Árbitros ---
    arbitros_db = db.query(models.Arbitro).filter(models.Arbitro.activo.is_(True)).all()
    disp_rows = (
        db.query(models.Disponibilidad)
        .filter(models.Disponibilidad.fecha >= fecha_desde)
        .filter(models.Disponibilidad.fecha <= fecha_hasta)
        .all()
    )
    franja_idx = {f: i for i, f in enumerate(FRANJAS)}
    disp_por_arb: dict[int, dict] = {}
    for d in disp_rows:
        fi = franja_idx.get(d.franja)
        if fi is None:
            continue
        disp_por_arb.setdefault(d.arbitro_id, {})[(d.fecha, fi)] = d.estado

    arbitros = []
    for i, a in enumerate(sorted(arbitros_db, key=lambda x: x.id)):
        arbitros.append(ArbitroInst(
            idx=i, id=a.id, nombre=a.nombre, rango=niveles.rango_arbitro(a.nivel_arbitral),
            lat=a.latitud, lon=a.longitud, disp=disp_por_arb.get(a.id, {}),
        ))

    # --- Partidos ---
    partidos_db = (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.categoria).joinedload(models.Categoria.nivel_primero),
            joinedload(models.Partido.categoria).joinedload(models.Categoria.nivel_segundo),
            joinedload(models.Partido.categoria).joinedload(models.Categoria.nivel_anotador),
        )
        .filter(models.Partido.fecha >= fecha_desde)
        .filter(models.Partido.fecha <= fecha_hasta)
        .order_by(models.Partido.fecha, models.Partido.hora)
        .all()
    )
    polis = db.query(models.Polideportivo).all()
    sedes = distancias.resolver_sedes({p.campo for p in partidos_db if p.campo}, polis)

    ids_filtro = set(partido_ids) if partido_ids is not None else None
    partidos = []
    n_sin_franja = n_sin_sede = n_excluidos = 0
    for p in partidos_db:
        fr = franja_de_hora(p.hora)
        sede = sedes.get(p.campo)
        if fr is None:
            n_sin_franja += 1
        if sede is None:
            n_sin_sede += 1
        if ids_filtro is not None and p.id not in ids_filtro:
            continue
        if solo_completos and not es_designable(p, sede, fr):
            n_excluidos += 1
            continue

        prioridad = (p.categoria.prioridad if p.categoria and p.categoria.prioridad else 99)
        antel = antelacion_de(prioridad)
        dur = duracion_de(prioridad)
        md = _minutos_dia(p.hora)
        inicio = p.fecha.toordinal() * 1440 + md if md is not None else None
        partidos.append(PartidoInst(
            idx=len(partidos), id=p.id, fecha=p.fecha, franja=fr,
            categoria_id=p.categoria_id, prioridad=prioridad,
            local=p.local, visitante=p.visitante, sede=sede, sede_nombre=p.campo,
            roles=niveles.roles_requeridos(p.categoria),
            inicio_min=inicio,
            ini_ocup=(inicio - antel) if inicio is not None else None,
            fin_ocup=(inicio + dur) if inicio is not None else None,
            antelacion=antel, duracion=dur,
        ))

    _calcular_candidatos(partidos, arbitros, umbral_sin_transporte, UMBRAL_RECOGIDA_KM)
    inst = Instancia(arbitros=arbitros, partidos=partidos,
                     n_sin_franja=n_sin_franja, n_sin_sede=n_sin_sede)
    inst.n_excluidos = n_excluidos
    return inst


def _distancia(arb: ArbitroInst, sede):
    if sede is None or arb.lat is None or arb.lon is None:
        return None
    return distancias.haversine(arb.lat, arb.lon, sede[0], sede[1])


def _calcular_candidatos(partidos, arbitros, umbral, umbral_recogida=UMBRAL_RECOGIDA_KM):
    """Por cada (partido, rol): árbitros disponibles que cumplen nivel y logística.

    Tipo de candidato:
      'con'   → con transporte (puede conducir y llevar a otros).
      'cerca' → sin transporte pero la sede está a su alcance (≤ umbral).
      'lejos' → sin transporte y lejos: solo válido si en el partido hay un
                conductor que viva cerca de él (≤ umbral_recogida) y pueda
                llevarlo y traerlo. Si nadie cercano conduce en ese partido, no
                puede llegar y se descarta como candidato.
    """
    for p in partidos:
        if p.franja is None:
            p.candidatos = {rol: [] for rol, _ in p.roles}
            p.cand_dist = {rol: {} for rol, _ in p.roles}
            p.cand_tipo = {rol: {} for rol, _ in p.roles}
            continue
        for rol, rango_min in p.roles:
            lista, tipo = [], {}
            for a in arbitros:
                estado = a.disp.get((p.fecha, p.franja))
                if estado not in ("con_transporte", "sin_transporte"):
                    continue
                if not niveles.cumple_nivel(a.rango, rango_min):
                    continue
                if conflictos.hay_conflicto(a.id, p.local, p.visitante):
                    continue
                dist = _distancia(a, p.sede)
                if estado == "con_transporte":
                    t = "con"
                else:
                    if dist is None:
                        continue  # sin coords no se puede compartir coche
                    t = "cerca" if dist <= umbral else "lejos"
                lista.append((a.idx, dist))
                tipo[a.idx] = t
            lista.sort(key=lambda t: (t[1] is None, t[1] if t[1] is not None else 0.0))
            p.candidatos[rol] = lista
            p.cand_dist[rol] = {a_idx: d for a_idx, d in lista}
            p.cand_tipo[rol] = tipo

        # Coche compartido lógico: descarta los 'lejos' que no tengan en el
        # partido ningún conductor ('con') viviendo cerca que pueda recogerlos.
        con_idxs = {a for rol, _ in p.roles
                    for a, t in p.cand_tipo[rol].items() if t == "con"}
        conductores = [arbitros[i] for i in con_idxs]
        for rol, _ in p.roles:
            fuera = {a for a, t in p.cand_tipo[rol].items()
                     if t == "lejos"
                     and not any(pueden_compartir(c, arbitros[a], umbral_recogida)
                                 for c in conductores)}
            if fuera:
                p.candidatos[rol] = [(a, d) for a, d in p.candidatos[rol] if a not in fuera]
                p.cand_dist[rol] = {a: d for a, d in p.candidatos[rol]}
                for a in fuera:
                    p.cand_tipo[rol].pop(a, None)
