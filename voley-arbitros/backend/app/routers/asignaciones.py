"""Endpoints de asignaciones de árbitros a partidos.

Incluye el alta/baja manual de asignaciones y un punto de entrada
(`POST /api/asignaciones/generar`) reservado para el futuro algoritmo de
optimización basado en IA (RF2). De momento devuelve 501 Not Implemented.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import asignacion, models, schemas
from ..asignacion import comun, datos as asig_datos, distancias
from ..database import get_db
from ..parsing import FRANJAS

router = APIRouter(prefix="/api/asignaciones", tags=["asignaciones"])

ROLES_VALIDOS = {"primero", "segundo", "anotador"}


def _recalcular_estado(db: Session, partido: models.Partido) -> None:
    """Actualiza el estado del partido según las asignaciones que tenga."""
    n = db.query(models.Asignacion).filter_by(partido_id=partido.id).count()
    minimo = partido.categoria.min_arbitros if partido.categoria else 1
    if n == 0:
        partido.estado = "por_determinar" if not partido.campo else "pendiente"
    elif n >= minimo:
        partido.estado = "asignado"
    else:
        partido.estado = "pendiente"


@router.get("", response_model=list[schemas.AsignacionOut])
def listar_asignaciones(
    partido_id: int | None = None,
    arbitro_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Asignacion)
    if partido_id is not None:
        q = q.filter_by(partido_id=partido_id)
    if arbitro_id is not None:
        q = q.filter_by(arbitro_id=arbitro_id)
    return q.all()


@router.post("", response_model=schemas.AsignacionOut, status_code=201)
def crear_asignacion(datos: schemas.AsignacionCreate, db: Session = Depends(get_db)):
    if datos.rol not in ROLES_VALIDOS:
        raise HTTPException(422, f"Rol no válido. Use uno de: {sorted(ROLES_VALIDOS)}")
    partido = db.get(models.Partido, datos.partido_id)
    if not partido:
        raise HTTPException(404, "Partido no encontrado")
    if not db.get(models.Arbitro, datos.arbitro_id):
        raise HTTPException(404, "Árbitro no encontrado")

    # Un mismo rol sólo puede estar ocupado por un árbitro: si ya existe, se
    # sustituye. Evita también asignar el mismo árbitro dos veces al partido.
    existente_rol = (
        db.query(models.Asignacion)
        .filter_by(partido_id=datos.partido_id, rol=datos.rol)
        .first()
    )
    if existente_rol:
        db.delete(existente_rol)
        db.flush()
    duplicado = (
        db.query(models.Asignacion)
        .filter_by(partido_id=datos.partido_id, arbitro_id=datos.arbitro_id)
        .first()
    )
    if duplicado:
        raise HTTPException(409, "Ese árbitro ya está asignado a este partido")

    asig = models.Asignacion(**datos.model_dump())
    db.add(asig)
    db.flush()
    _recalcular_estado(db, partido)
    db.commit()
    db.refresh(asig)
    return asig


@router.delete("/{asignacion_id}", status_code=204)
def eliminar_asignacion(asignacion_id: int, db: Session = Depends(get_db)):
    asig = db.get(models.Asignacion, asignacion_id)
    if not asig:
        raise HTTPException(404, "Asignación no encontrada")
    partido = asig.partido
    db.delete(asig)
    db.flush()
    if partido:
        _recalcular_estado(db, partido)
    db.commit()


def _rango_por_defecto(db, desde, hasta):
    """Completa el rango con la ventana de disponibilidad si falta."""
    if desde is None or hasta is None:
        dmin, dmax = db.query(
            func.min(models.Disponibilidad.fecha), func.max(models.Disponibilidad.fecha)
        ).one()
        desde = desde or dmin
        hasta = hasta or dmax
    if desde is None or hasta is None:
        raise HTTPException(422, "No hay datos de disponibilidad para asignar.")
    if desde > hasta:
        raise HTTPException(422, "El rango de fechas es inválido.")
    return desde, hasta


@router.get("/partidos", response_model=list[schemas.PartidoDesignableOut])
def partidos_designables(
    desde: date | None = None, hasta: date | None = None,
    db: Session = Depends(get_db),
):
    """Partidos DESIGNABLES (con categoría, franja y sede) en el rango, con sus
    designaciones actuales. Los partidos sin todos los datos no se incluyen."""
    desde, hasta = _rango_por_defecto(db, desde, hasta)
    partidos = (
        db.query(models.Partido)
        .options(
            joinedload(models.Partido.categoria),
            joinedload(models.Partido.asignaciones).joinedload(models.Asignacion.arbitro),
        )
        .filter(models.Partido.fecha >= desde, models.Partido.fecha <= hasta)
        .order_by(models.Partido.fecha, models.Partido.hora)
        .all()
    )
    polis = db.query(models.Polideportivo).all()
    sedes = distancias.resolver_sedes({p.campo for p in partidos if p.campo}, polis)

    # Reconstruye la solución publicada para deducir el transporte de cada árbitro
    # (vehículo propio / le llevan / andando), considerando el coche compartido.
    transportes = _transportes_publicados(db, desde, hasta)

    salida = []
    for p in partidos:
        fr = asig_datos.franja_de_hora(p.hora)
        sede = sedes.get(p.campo)
        if not asig_datos.es_designable(p, sede, fr):
            continue
        salida.append(
            schemas.PartidoDesignableOut(
                id=p.id, fecha=p.fecha, hora=p.hora, franja=FRANJAS[fr],
                categoria=p.categoria.nombre if p.categoria else None,
                min_arbitros=p.categoria.min_arbitros if p.categoria else 1,
                local=p.local, visitante=p.visitante, sede=p.campo, estado=p.estado,
                designaciones=[
                    schemas.DesignacionMini(
                        rol=a.rol, origen=a.origen,
                        arbitro_id=a.arbitro_id, arbitro_nombre=a.arbitro.nombre,
                        **transportes.get((a.arbitro_id, p.id), {}),
                    )
                    for a in p.asignaciones
                ],
            )
        )
    return salida


def _transportes_publicados(db, desde, hasta) -> dict:
    """{(arbitro_id, partido_id): {transporte, conductor, recoge}} de las
    designaciones ya guardadas en el rango (para mostrarlas en la lista)."""
    inst = asig_datos.construir_instancia(db, desde, hasta, solo_completos=True)
    pid = {p.id: p.idx for p in inst.partidos}
    aid = {a.id: a.idx for a in inst.arbitros}
    rows = (
        db.query(models.Asignacion)
        .filter(models.Asignacion.partido_id.in_(list(pid)))
        .all()
    )
    sol = {}
    for r in rows:
        if r.partido_id in pid and r.arbitro_id in aid:
            sol[(pid[r.partido_id], r.rol)] = aid[r.arbitro_id]
    return comun.transportes_por_asignacion(inst, sol)


@router.get("/itinerario/{arbitro_id}")
def itinerario_arbitro(
    arbitro_id: int, desde: date | None = None, hasta: date | None = None,
    db: Session = Depends(get_db),
):
    """Resumen de desplazamientos de un árbitro (origen, coche compartido, km)."""
    desde, hasta = _rango_por_defecto(db, desde, hasta)
    inst = asig_datos.construir_instancia(db, desde, hasta, solo_completos=True)
    pid = {p.id: p.idx for p in inst.partidos}
    aid = {a.id: a.idx for a in inst.arbitros}
    rows = (
        db.query(models.Asignacion)
        .filter(models.Asignacion.partido_id.in_(list(pid)))
        .all()
    )
    sol = {}
    for r in rows:
        if r.partido_id in pid and r.arbitro_id in aid:
            sol[(pid[r.partido_id], r.rol)] = aid[r.arbitro_id]
    res = comun.itinerario(inst, sol, arbitro_id)
    if res is None:
        raise HTTPException(404, "Árbitro no encontrado en el rango.")
    return res


@router.post("/generar", response_model=schemas.GenerarResponse)
def generar_asignaciones(
    req: schemas.GenerarRequest | None = None, db: Session = Depends(get_db)
):
    """Genera (previsualiza) las designaciones arbitrales (RF2) sin guardarlas.

    Pipeline híbrido en 3 fases: greedy → CP-SAT → búsqueda local. Solo considera
    partidos completos (con sede y franja). Con `partido_ids` se restringe a la
    selección manual. No persiste: usar `/publicar` para guardar.
    """
    req = req or schemas.GenerarRequest()
    desde, hasta = _rango_por_defecto(db, req.fecha_desde, req.fecha_hasta)

    opciones = asignacion.OpcionesAsignacion(
        fecha_desde=desde, fecha_hasta=hasta,
        segundos_max=max(1.0, min(req.segundos_max, 120.0)),
        usar_cpsat=req.usar_cpsat, partido_ids=req.partido_ids,
    )
    resultado = asignacion.generar(db, opciones)
    return schemas.GenerarResponse(
        fecha_desde=desde, fecha_hasta=hasta,
        metricas=resultado["metricas"], asignaciones=resultado["asignaciones"],
    )


@router.post("/publicar")
def publicar_asignaciones(req: schemas.PublicarRequest, db: Session = Depends(get_db)):
    """Guarda las designaciones previsualizadas: reemplaza las de esos partidos."""
    pids = {a.partido_id for a in req.asignaciones}
    if pids:
        db.query(models.Asignacion).filter(
            models.Asignacion.partido_id.in_(pids)
        ).delete(synchronize_session=False)
        db.flush()
    for a in req.asignaciones:
        db.add(models.Asignacion(
            partido_id=a.partido_id, arbitro_id=a.arbitro_id,
            rol=a.rol, origen="automatico",
        ))
    db.flush()
    for partido in db.query(models.Partido).filter(models.Partido.id.in_(pids)).all():
        _recalcular_estado(db, partido)
    db.commit()
    return {"publicadas": len(req.asignaciones)}


@router.post("/limpiar")
def limpiar_asignaciones(req: schemas.LimpiarRequest, db: Session = Depends(get_db)):
    """Elimina designaciones: por selección de partidos, por rango o todas."""
    q = db.query(models.Asignacion)
    if req.partido_ids:
        ids = list(req.partido_ids)
        q = q.filter(models.Asignacion.partido_id.in_(ids))
    elif req.fecha_desde or req.fecha_hasta:
        pq = db.query(models.Partido.id)
        if req.fecha_desde:
            pq = pq.filter(models.Partido.fecha >= req.fecha_desde)
        if req.fecha_hasta:
            pq = pq.filter(models.Partido.fecha <= req.fecha_hasta)
        ids = [pid for (pid,) in pq.all()]
        q = q.filter(models.Asignacion.partido_id.in_(ids))
    else:
        ids = [pid for (pid,) in db.query(models.Partido.id).all()]

    afectados = {a.partido_id for a in q.all()}
    n = q.delete(synchronize_session=False)
    db.flush()
    for partido in db.query(models.Partido).filter(models.Partido.id.in_(afectados)).all():
        _recalcular_estado(db, partido)
    db.commit()
    return {"eliminadas": n}
