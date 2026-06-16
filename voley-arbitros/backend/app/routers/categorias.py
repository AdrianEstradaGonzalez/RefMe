"""Endpoints de categorías y equipos (RF1.3)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api", tags=["categorias"])


@router.get("/categorias", response_model=list[schemas.CategoriaOut])
def listar_categorias(db: Session = Depends(get_db)):
    return (
        db.query(models.Categoria)
        .order_by(models.Categoria.prioridad, models.Categoria.nombre)
        .all()
    )


@router.get("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def obtener_categoria(categoria_id: int, db: Session = Depends(get_db)):
    cat = db.get(models.Categoria, categoria_id)
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    return cat


@router.get("/equipos", response_model=list[schemas.EquipoOut])
def listar_equipos(categoria_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Equipo)
    if categoria_id is not None:
        q = q.filter_by(categoria_id=categoria_id)
    return q.order_by(models.Equipo.nombre).all()
