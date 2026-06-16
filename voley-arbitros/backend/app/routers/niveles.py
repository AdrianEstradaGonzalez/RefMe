"""Endpoints de niveles arbitrales (sólo lectura)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/niveles", tags=["niveles"])


@router.get("", response_model=list[schemas.NivelOut])
def listar_niveles(db: Session = Depends(get_db)):
    return db.query(models.Nivel).order_by(models.Nivel.orden).all()
