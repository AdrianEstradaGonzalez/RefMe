"""Modelos ORM del dominio de designación arbitral.

Entidades principales:
  - Nivel          : jerarquía de niveles arbitrales (con un orden numérico).
  - Arbitro        : datos del árbitro (nombre, código, nivel, ubicación).
  - Categoria      : competición y sus requisitos (niveles por rol, mínimos).
  - Equipo         : equipos por categoría.
  - Partido        : encuentros del calendario.
  - Disponibilidad : disponibilidad de cada árbitro por fecha y franja horaria.
  - Asignacion     : árbitro asignado a un partido en un rol concreto.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Nivel(Base):
    __tablename__ = "niveles"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)
    # Orden ascendente de competencia (mayor = más alto). Permite comprobar
    # de forma sencilla si un árbitro alcanza el nivel mínimo requerido.
    orden = Column(Integer, nullable=False)


class Arbitro(Base):
    __tablename__ = "arbitros"

    id = Column(Integer, primary_key=True)
    codigo = Column(Integer, unique=True, nullable=False)
    nombre = Column(String, nullable=False)
    nivel_id = Column(Integer, ForeignKey("niveles.id"), nullable=True)
    # Clasificación arbitral propia del árbitro (NIVEL I/II/III, Nacional, etc.),
    # tomada del fichero de disponibilidad. Distinta del nivel exigido por categoría.
    nivel_arbitral = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    codigo_postal = Column(String, nullable=True)
    localidad = Column(String, nullable=True)
    # Coordenadas para la futura optimización geográfica (RF2.3).
    latitud = Column(Float, nullable=True)
    longitud = Column(Float, nullable=True)
    # True si las coordenadas provienen de geocodificar la dirección exacta;
    # False si son una aproximación al centro del concejo.
    geocodificado = Column(Boolean, default=False, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    nivel = relationship("Nivel")
    disponibilidades = relationship(
        "Disponibilidad", back_populates="arbitro", cascade="all, delete-orphan"
    )
    asignaciones = relationship(
        "Asignacion", back_populates="arbitro", cascade="all, delete-orphan"
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True)
    nombre = Column(String, unique=True, nullable=False)

    # Requisitos por rol. requiere_* indica si el rol es necesario; nivel_*_id
    # el nivel mínimo exigido para ese rol (puede ser nulo si no se especifica).
    requiere_primero = Column(Boolean, default=False, nullable=False)
    nivel_primero_id = Column(Integer, ForeignKey("niveles.id"), nullable=True)
    requiere_segundo = Column(Boolean, default=False, nullable=False)
    nivel_segundo_id = Column(Integer, ForeignKey("niveles.id"), nullable=True)
    requiere_anotador = Column(Boolean, default=False, nullable=False)
    nivel_anotador_id = Column(Integer, ForeignKey("niveles.id"), nullable=True)

    min_arbitros = Column(Integer, default=1, nullable=False)
    # Nivel general orientativo de la categoría (columna "Nivel árbitro").
    nivel_general_id = Column(Integer, ForeignKey("niveles.id"), nullable=True)
    prioridad = Column(Integer, nullable=True)

    nivel_primero = relationship("Nivel", foreign_keys=[nivel_primero_id])
    nivel_segundo = relationship("Nivel", foreign_keys=[nivel_segundo_id])
    nivel_anotador = relationship("Nivel", foreign_keys=[nivel_anotador_id])
    nivel_general = relationship("Nivel", foreign_keys=[nivel_general_id])

    equipos = relationship(
        "Equipo", back_populates="categoria", cascade="all, delete-orphan"
    )
    partidos = relationship("Partido", back_populates="categoria")


class Equipo(Base):
    __tablename__ = "equipos"
    __table_args__ = (UniqueConstraint("nombre", "categoria_id", name="uq_equipo_cat"),)

    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    club = Column(String, nullable=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)

    categoria = relationship("Categoria", back_populates="equipos")


class Partido(Base):
    __tablename__ = "partidos"

    id = Column(Integer, primary_key=True)
    codigo_partido = Column(Integer, unique=True, nullable=True)
    fecha = Column(Date, nullable=False)
    hora = Column(String, nullable=True)  # "HH:MM"
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    jornada = Column(Integer, nullable=True)
    numero_partido = Column(Integer, nullable=True)
    local = Column(String, nullable=False)
    visitante = Column(String, nullable=False)
    campo = Column(String, nullable=True)
    provincia = Column(String, nullable=True)
    # pendiente | asignado | por_determinar
    estado = Column(String, default="pendiente", nullable=False)

    categoria = relationship("Categoria", back_populates="partidos")
    asignaciones = relationship(
        "Asignacion", back_populates="partido", cascade="all, delete-orphan"
    )


class Disponibilidad(Base):
    __tablename__ = "disponibilidades"
    __table_args__ = (
        UniqueConstraint("arbitro_id", "fecha", "franja", name="uq_disp"),
    )

    id = Column(Integer, primary_key=True)
    arbitro_id = Column(Integer, ForeignKey("arbitros.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    # 09:00-12:00 | 12:00-15:00 | 15:00-18:00 | 18:00-22:00
    franja = Column(String, nullable=False)
    # con_transporte | sin_transporte | no_disponible
    estado = Column(String, nullable=False)

    arbitro = relationship("Arbitro", back_populates="disponibilidades")


class Polideportivo(Base):
    """Sede de competición con su ubicación geográfica."""

    __tablename__ = "polideportivos"

    id = Column(String, primary_key=True)  # UUID facilitado por la federación
    nombre = Column(String, nullable=False)
    latitud = Column(Float, nullable=False)
    longitud = Column(Float, nullable=False)


class Club(Base):
    """Club de la federación."""

    __tablename__ = "clubs"

    id = Column(String, primary_key=True)  # UUID facilitado por la federación
    nombre = Column(String, nullable=False)

    equipos = relationship(
        "EquipoClub", back_populates="club", order_by="EquipoClub.nombre"
    )


class CategoriaFed(Base):
    """Categoría de competición (identificada por UUID) y sus requisitos."""

    __tablename__ = "categorias_fed"

    id = Column(String, primary_key=True)  # UUID facilitado por la federación
    nombre = Column(String, nullable=False)
    anotador = Column(String, nullable=True)        # nivel exigido al anotador
    min_arbitros = Column(Integer, default=1, nullable=False)
    primer_arbitro = Column(String, nullable=True)  # nivel exigido al 1º árbitro
    segundo_arbitro = Column(String, nullable=True)  # nivel exigido al 2º árbitro
    prioridad = Column(Integer, nullable=True)


class EquipoClub(Base):
    """Equipo federado, asociado a un club (o externo, sin club)."""

    __tablename__ = "equipos_club"

    id = Column(String, primary_key=True)  # UUID facilitado por la federación
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)
    nombre = Column(String, nullable=False)
    categoria_uuid = Column(String, nullable=True)

    club = relationship("Club", back_populates="equipos")
    # Relación sin FK a nivel de BD (algún UUID podría no estar en el catálogo).
    categoria = relationship(
        "CategoriaFed",
        primaryjoin="foreign(EquipoClub.categoria_uuid) == CategoriaFed.id",
        viewonly=True,
    )


class Asignacion(Base):
    __tablename__ = "asignaciones"
    __table_args__ = (
        UniqueConstraint("partido_id", "rol", name="uq_asig_rol"),
        UniqueConstraint("partido_id", "arbitro_id", name="uq_asig_arb"),
    )

    id = Column(Integer, primary_key=True)
    partido_id = Column(Integer, ForeignKey("partidos.id"), nullable=False)
    arbitro_id = Column(Integer, ForeignKey("arbitros.id"), nullable=False)
    rol = Column(String, nullable=False)  # primero | segundo | anotador
    origen = Column(String, default="manual", nullable=False)  # manual | automatico
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)

    partido = relationship("Partido", back_populates="asignaciones")
    arbitro = relationship("Arbitro", back_populates="asignaciones")
