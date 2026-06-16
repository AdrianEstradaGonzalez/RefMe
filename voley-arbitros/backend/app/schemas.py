"""Esquemas Pydantic (v2) para validar entradas y serializar respuestas."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- Niveles
class NivelOut(_Base):
    id: int
    nombre: str
    orden: int


# ---------------------------------------------------------------- Árbitros
class ArbitroBase(BaseModel):
    nombre: str
    codigo: int
    nivel_id: Optional[int] = None
    nivel_arbitral: Optional[str] = None
    direccion: Optional[str] = None
    codigo_postal: Optional[str] = None
    localidad: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    activo: bool = True


class ArbitroCreate(ArbitroBase):
    pass


class ArbitroUpdate(BaseModel):
    nombre: Optional[str] = None
    codigo: Optional[int] = None
    nivel_id: Optional[int] = None
    nivel_arbitral: Optional[str] = None
    direccion: Optional[str] = None
    codigo_postal: Optional[str] = None
    localidad: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    activo: Optional[bool] = None


class ArbitroOut(ArbitroBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    geocodificado: bool = False
    nivel: Optional[NivelOut] = None


# ---------------------------------------------------------------- Polideportivos
class PolideportivoOut(_Base):
    id: str
    nombre: str
    latitud: float
    longitud: float


# ---------------------------------------------------------------- Clubs / equipos
class CategoriaFedMini(_Base):
    id: str
    nombre: str
    prioridad: Optional[int] = None
    min_arbitros: int = 1
    primer_arbitro: Optional[str] = None
    segundo_arbitro: Optional[str] = None
    anotador: Optional[str] = None


class EquipoClubOut(_Base):
    id: str
    nombre: str
    club_id: Optional[str] = None
    categoria_uuid: Optional[str] = None
    categoria: Optional[CategoriaFedMini] = None


class ClubOut(_Base):
    id: str
    nombre: str
    equipos: list[EquipoClubOut] = []


# ---------------------------------------------------------------- Categorías
class CategoriaOut(_Base):
    id: int
    nombre: str
    requiere_primero: bool
    requiere_segundo: bool
    requiere_anotador: bool
    min_arbitros: int
    prioridad: Optional[int] = None
    nivel_primero: Optional[NivelOut] = None
    nivel_segundo: Optional[NivelOut] = None
    nivel_anotador: Optional[NivelOut] = None
    nivel_general: Optional[NivelOut] = None


# ---------------------------------------------------------------- Equipos
class EquipoOut(_Base):
    id: int
    nombre: str
    club: Optional[str] = None
    categoria_id: int


# ---------------------------------------------------------------- Asignaciones
class AsignacionBase(BaseModel):
    partido_id: int
    arbitro_id: int
    rol: str  # primero | segundo | anotador


class AsignacionCreate(AsignacionBase):
    origen: str = "manual"


class ArbitroMini(_Base):
    id: int
    nombre: str
    codigo: int


class AsignacionOut(_Base):
    id: int
    partido_id: int
    rol: str
    origen: str
    arbitro: ArbitroMini


# ---------------------------------------------------------------- Partidos
class PartidoOut(_Base):
    id: int
    codigo_partido: Optional[int] = None
    fecha: date
    hora: Optional[str] = None
    categoria_id: int
    jornada: Optional[int] = None
    numero_partido: Optional[int] = None
    local: str
    visitante: str
    campo: Optional[str] = None
    provincia: Optional[str] = None
    estado: str
    categoria: Optional[CategoriaOut] = None
    asignaciones: list[AsignacionOut] = []


class PartidoUpdate(BaseModel):
    fecha: Optional[date] = None
    hora: Optional[str] = None
    local: Optional[str] = None
    visitante: Optional[str] = None
    campo: Optional[str] = None
    provincia: Optional[str] = None
    estado: Optional[str] = None


# ---------------------------------------------------------------- Disponibilidad
class DisponibilidadBase(BaseModel):
    arbitro_id: int
    fecha: date
    franja: str
    estado: str  # con_transporte | sin_transporte | no_disponible


class DisponibilidadCreate(DisponibilidadBase):
    pass


class DisponibilidadOut(_Base):
    id: int
    arbitro_id: int
    fecha: date
    franja: str
    estado: str


# ---------------------------------------------------- Asignación automática (RF2)
class GenerarRequest(BaseModel):
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    segundos_max: float = 20.0
    usar_cpsat: bool = True
    partido_ids: Optional[list[int]] = None  # selección manual; None = todos los completos


class GenerarResponse(BaseModel):
    fecha_desde: date
    fecha_hasta: date
    metricas: dict
    asignaciones: list[dict]


class AsignacionGenerada(BaseModel):
    partido_id: int
    arbitro_id: int
    rol: str


class PublicarRequest(BaseModel):
    asignaciones: list[AsignacionGenerada]


class LimpiarRequest(BaseModel):
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    partido_ids: Optional[list[int]] = None


class DesignacionMini(_Base):
    rol: str
    origen: str
    arbitro_id: int
    arbitro_nombre: str
    # Cómo se desplaza: 'con' (vehículo propio) | 'llevan' (le recogen) | 'andando'.
    transporte: Optional[str] = None
    conductor: Optional[str] = None  # quién le lleva (si transporte == 'llevan')
    recoge: list[str] = []           # a quién recoge (si conduce a otros)
    km: Optional[float] = None       # km que recorre hasta la sede
    desde: Optional[str] = None      # de dónde sale (domicilio / nombre de sede)
    # domicilio | sede_anterior | mismo_poli (ya estaba en el polideportivo)
    desde_tipo: Optional[str] = None


class PartidoDesignableOut(BaseModel):
    id: int
    fecha: date
    hora: Optional[str] = None
    franja: Optional[str] = None
    categoria: Optional[str] = None
    min_arbitros: int = 1
    local: str
    visitante: str
    sede: Optional[str] = None
    estado: str
    designaciones: list[DesignacionMini] = []
