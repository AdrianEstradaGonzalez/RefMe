"""Clubs de la federación y sus equipos asociados."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/clubs", tags=["clubs"])


@router.get("", response_model=list[schemas.ClubOut])
def listar_clubs(db: Session = Depends(get_db)):
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.equipos))
        .order_by(models.Club.nombre)
        .all()
    )


@router.get("/equipos", response_model=list[schemas.EquipoClubOut])
def listar_equipos(
    sin_club: bool = False, db: Session = Depends(get_db)
):
    """Lista de equipos; con `sin_club=true` solo los externos (sin club)."""
    q = db.query(models.EquipoClub)
    if sin_club:
        q = q.filter(models.EquipoClub.club_id.is_(None))
    return q.order_by(models.EquipoClub.nombre).all()
