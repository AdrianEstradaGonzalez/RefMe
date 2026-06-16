"""Configuración de la base de datos (SQLAlchemy + SQLite).

Se usa SQLite por simplicidad: un único fichero `voley.db` sin servidor
externo. La capa ORM permite cambiar a PostgreSQL/MySQL en el futuro
modificando únicamente `DATABASE_URL`.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# El fichero de base de datos se guarda junto al backend.
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'voley.db'}"

# check_same_thread=False es necesario para SQLite con FastAPI (varios hilos).
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: abre una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
