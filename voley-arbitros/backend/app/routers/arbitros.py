"""CRUD de árbitros (RF1.1)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/arbitros", tags=["arbitros"])


@router.get("", response_model=list[schemas.ArbitroOut])
def listar_arbitros(db: Session = Depends(get_db)):
    return (
        db.query(models.Arbitro)
        .options(joinedload(models.Arbitro.nivel))
        .order_by(models.Arbitro.nombre)
        .all()
    )


@router.get("/{arbitro_id}", response_model=schemas.ArbitroOut)
def obtener_arbitro(arbitro_id: int, db: Session = Depends(get_db)):
    arb = db.get(models.Arbitro, arbitro_id)
    if not arb:
        raise HTTPException(404, "Árbitro no encontrado")
    return arb


@router.post("", response_model=schemas.ArbitroOut, status_code=201)
def crear_arbitro(datos: schemas.ArbitroCreate, db: Session = Depends(get_db)):
    if db.query(models.Arbitro).filter_by(codigo=datos.codigo).first():
        raise HTTPException(409, "Ya existe un árbitro con ese código")
    arb = models.Arbitro(**datos.model_dump())
    db.add(arb)
    db.commit()
    db.refresh(arb)
    return arb


@router.put("/{arbitro_id}", response_model=schemas.ArbitroOut)
def actualizar_arbitro(
    arbitro_id: int, datos: schemas.ArbitroUpdate, db: Session = Depends(get_db)
):
    arb = db.get(models.Arbitro, arbitro_id)
    if not arb:
        raise HTTPException(404, "Árbitro no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(arb, campo, valor)
    db.commit()
    db.refresh(arb)
    return arb


@router.delete("/{arbitro_id}", status_code=204)
def eliminar_arbitro(arbitro_id: int, db: Session = Depends(get_db)):
    arb = db.get(models.Arbitro, arbitro_id)
    if not arb:
        raise HTTPException(404, "Árbitro no encontrado")
    db.delete(arb)
    db.commit()
