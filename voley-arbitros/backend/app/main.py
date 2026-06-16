"""Aplicación FastAPI: punto de entrada del backend.

Al arrancar crea las tablas (si no existen) y realiza la carga inicial de
datos desde los Excel de `data/`. Expone la API REST bajo `/api/...` y sirve
la interfaz web estática (carpeta `frontend/`).
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models, seed
from .database import Base, SessionLocal, engine
from .routers import (
    arbitros,
    asignaciones,
    categorias,
    clubs,
    disponibilidad,
    estadisticas,
    niveles,
    partidos,
    polideportivos,
)

app = FastAPI(
    title="Designación Arbitral - Voleibol Asturias",
    description="Backend de gestión y designación de árbitros de voleibol.",
    version="0.1.0",
)

# CORS abierto para facilitar el desarrollo (frontend separado si se desea).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def inicializar():
    """Crea las tablas y carga los datos iniciales la primera vez."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not seed.hay_datos(db):
            seed.cargar_datos_iniciales(db)
        else:
            # BD con datos base pero sin la disponibilidad/domicilios reales.
            if db.query(models.Disponibilidad).count() == 0:
                seed.cargar_domicilios_y_disponibilidad(db)
                seed.geocodificar_arbitros(db, permitir_red=False)
            if db.query(models.Polideportivo).count() == 0:
                seed.cargar_polideportivos(db)
            if db.query(models.Club).count() == 0:
                seed.cargar_clubs_y_equipos(db)
    finally:
        db.close()


# Routers de la API
app.include_router(estadisticas.router)
app.include_router(niveles.router)
app.include_router(arbitros.router)
app.include_router(categorias.router)
app.include_router(partidos.router)
app.include_router(disponibilidad.router)
app.include_router(asignaciones.router)
app.include_router(polideportivos.router)
app.include_router(clubs.router)


@app.get("/api/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}


# ------------------------------------------------------------------ Frontend
# Sirve la interfaz web estática. Debe ir DESPUÉS de registrar la API.
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
