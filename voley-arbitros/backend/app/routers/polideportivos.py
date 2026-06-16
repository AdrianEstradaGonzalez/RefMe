"""Catálogo de polideportivos (sedes de competición)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/polideportivos", tags=["polideportivos"])


@router.get("", response_model=list[schemas.PolideportivoOut])
def listar_polideportivos(db: Session = Depends(get_db)):
    return db.query(models.Polideportivo).order_by(models.Polideportivo.nombre).all()
