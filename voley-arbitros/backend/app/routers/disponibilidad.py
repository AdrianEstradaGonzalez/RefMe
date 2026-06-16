"""Endpoints de disponibilidad horaria de los árbitros (RF1.2).

La disponibilidad se modela por árbitro, fecha y franja horaria, con tres
estados posibles: disponible con transporte, disponible sin transporte o no
disponible.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..parsing import FRANJAS

router = APIRouter(prefix="/api/disponibilidad", tags=["disponibilidad"])

ESTADOS_VALIDOS = {"con_transporte", "sin_transporte", "no_disponible"}


@router.get("/franjas", response_model=list[str])
def listar_franjas():
    return FRANJAS


@router.get("", response_model=list[schemas.DisponibilidadOut])
def listar_disponibilidad(
    arbitro_id: int | None = None,
    fecha: date | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Disponibilidad)
    if arbitro_id is not None:
        q = q.filter_by(arbitro_id=arbitro_id)
    if fecha is not None:
        q = q.filter_by(fecha=fecha)
    return q.all()


@router.put("", response_model=schemas.DisponibilidadOut)
def establecer_disponibilidad(
    datos: schemas.DisponibilidadCreate, db: Session = Depends(get_db)
):
    """Crea o actualiza la disponibilidad de un árbitro en una franja concreta."""
    if datos.franja not in FRANJAS:
        raise HTTPException(422, f"Franja no válida. Use una de: {FRANJAS}")
    if datos.estado not in ESTADOS_VALIDOS:
        raise HTTPException(422, f"Estado no válido. Use uno de: {sorted(ESTADOS_VALIDOS)}")
    if not db.get(models.Arbitro, datos.arbitro_id):
        raise HTTPException(404, "Árbitro no encontrado")

    disp = (
        db.query(models.Disponibilidad)
        .filter_by(arbitro_id=datos.arbitro_id, fecha=datos.fecha, franja=datos.franja)
        .first()
    )
    if disp:
        disp.estado = datos.estado
    else:
        disp = models.Disponibilidad(**datos.model_dump())
        db.add(disp)
    db.commit()
    db.refresh(disp)
    return disp


@router.delete("/{disponibilidad_id}", status_code=204)
def eliminar_disponibilidad(disponibilidad_id: int, db: Session = Depends(get_db)):
    disp = db.get(models.Disponibilidad, disponibilidad_id)
    if not disp:
        raise HTTPException(404, "Registro no encontrado")
    db.delete(disp)
    db.commit()
