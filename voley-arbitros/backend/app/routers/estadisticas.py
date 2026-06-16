"""Estadísticas agregadas para el panel principal."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/estadisticas", tags=["estadisticas"])


@router.get("")
def estadisticas(db: Session = Depends(get_db)):
    total_partidos = db.query(models.Partido).count()
    por_estado = {
        estado: db.query(models.Partido).filter_by(estado=estado).count()
        for estado in ("asignado", "pendiente", "por_determinar")
    }
    return {
        "arbitros": db.query(models.Arbitro).count(),
        "categorias": db.query(models.Categoria).count(),
        "equipos": db.query(models.Equipo).count(),
        "partidos": total_partidos,
        "asignaciones": db.query(models.Asignacion).count(),
        "partidos_por_estado": por_estado,
    }
