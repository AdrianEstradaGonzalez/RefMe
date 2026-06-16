"""Endpoints del calendario de partidos (RF1.3, RF3.1)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/partidos", tags=["partidos"])


@router.get("", response_model=list[schemas.PartidoOut])
def listar_partidos(
    desde: date | None = None,
    hasta: date | None = None,
    categoria_id: int | None = None,
    estado: str | None = None,
    provincia: str | None = None,
    limite: int = 500,
    db: Session = Depends(get_db),
):
    """Lista partidos con filtros opcionales. Por defecto limita a 500 filas."""
    q = db.query(models.Partido).options(
        joinedload(models.Partido.categoria),
        joinedload(models.Partido.asignaciones).joinedload(models.Asignacion.arbitro),
    )
    if desde:
        q = q.filter(models.Partido.fecha >= desde)
    if hasta:
        q = q.filter(models.Partido.fecha <= hasta)
    if categoria_id is not None:
        q = q.filter(models.Partido.categoria_id == categoria_id)
    if estado:
        q = q.filter(models.Partido.estado == estado)
    if provincia:
        q = q.filter(models.Partido.provincia == provincia)
    return q.order_by(models.Partido.fecha, models.Partido.hora).limit(limite).all()


@router.get("/fechas", response_model=list[date])
def fechas_disponibles(db: Session = Depends(get_db)):
    """Devuelve las fechas que tienen al menos un partido (para filtros)."""
    filas = db.query(models.Partido.fecha).distinct().order_by(models.Partido.fecha).all()
    return [f[0] for f in filas]


@router.get("/{partido_id}", response_model=schemas.PartidoOut)
def obtener_partido(partido_id: int, db: Session = Depends(get_db)):
    partido = db.get(models.Partido, partido_id)
    if not partido:
        raise HTTPException(404, "Partido no encontrado")
    return partido


@router.put("/{partido_id}", response_model=schemas.PartidoOut)
def actualizar_partido(
    partido_id: int, datos: schemas.PartidoUpdate, db: Session = Depends(get_db)
):
    partido = db.get(models.Partido, partido_id)
    if not partido:
        raise HTTPException(404, "Partido no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(partido, campo, valor)
    db.commit()
    db.refresh(partido)
    return partido
