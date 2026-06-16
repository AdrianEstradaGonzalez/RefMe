"""Carga inicial de datos en la base de datos.

Lee los Excel de la carpeta `data/` mediante `parsing.py` e inserta niveles,
árbitros, categorías, equipos, partidos y las asignaciones de ejemplo que ya
venían rellenas en el calendario original.

Se puede ejecutar de forma independiente:  python -m app.seed
"""
import re
import unicodedata
from pathlib import Path

from sqlalchemy.orm import Session

from . import categorias_fed, clubs_equipos, geo, geocoding, models, parsing
from . import polideportivos as polideportivos_data
from .database import Base, SessionLocal, engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FICHERO_PRINCIPAL = DATA_DIR / "datos_iniciales.xlsx"
FICHERO_CATEGORIAS = DATA_DIR / "categorias_niveles.xlsx"
FICHERO_LICENCIAS = DATA_DIR / "Relacion_licencias.xlsx"
FICHERO_DISPONIBILIDAD = DATA_DIR / "Disponibilidad arbitros.xlsx"


def _clave_nombre(nombre: str) -> str:
    """Normaliza un nombre para cruzar ficheros: sin acentos, mayúsculas."""
    if not nombre:
        return ""
    texto = str(nombre).replace("\xa0", " ").strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", texto).upper()


def _crear_niveles(db: Session) -> dict:
    """Inserta la jerarquía de niveles y devuelve {nombre: Nivel}."""
    mapa = {}
    for i, nombre in enumerate(parsing.NIVELES_ORDENADOS, start=1):
        nivel = models.Nivel(nombre=nombre, orden=i)
        db.add(nivel)
        mapa[nombre] = nivel
    db.flush()
    return mapa


def _crear_categorias(db: Session, niveles: dict) -> dict:
    mapa = {}
    for fila in parsing.leer_categorias(FICHERO_CATEGORIAS):
        cat = models.Categoria(
            nombre=fila["nombre"],
            requiere_primero=fila["nivel_primero"] is not None,
            nivel_primero_id=_id(niveles, fila["nivel_primero"]),
            requiere_segundo=fila["nivel_segundo"] is not None,
            nivel_segundo_id=_id(niveles, fila["nivel_segundo"]),
            requiere_anotador=fila["nivel_anotador"] is not None,
            nivel_anotador_id=_id(niveles, fila["nivel_anotador"]),
            min_arbitros=fila["min_arbitros"],
            nivel_general_id=_id(niveles, fila["nivel_general"]),
            prioridad=fila["prioridad"],
        )
        db.add(cat)
        mapa[fila["nombre"]] = cat
    db.flush()
    return mapa


def _id(niveles: dict, nombre):
    nivel = niveles.get(nombre) if nombre else None
    return nivel.id if nivel else None


def _crear_equipos(db: Session, categorias: dict) -> None:
    vistos = set()
    for fila in parsing.leer_equipos(FICHERO_PRINCIPAL):
        cat = categorias.get(fila["categoria"])
        if cat is None:
            continue
        clave = (fila["equipo"], cat.id)
        if clave in vistos:
            continue
        vistos.add(clave)
        db.add(
            models.Equipo(
                nombre=fila["equipo"], club=fila["club"], categoria_id=cat.id
            )
        )
    db.flush()


def _crear_arbitros(db: Session) -> dict:
    """Inserta árbitros y devuelve {nombre: Arbitro} para enlazar asignaciones."""
    mapa = {}
    for fila in parsing.leer_arbitros(FICHERO_PRINCIPAL):
        if fila["codigo"] is None:
            continue
        arb = models.Arbitro(nombre=fila["nombre"], codigo=fila["codigo"])
        db.add(arb)
        mapa[fila["nombre"]] = arb
    db.flush()
    return mapa


def _crear_partidos(db: Session, categorias: dict, arbitros: dict) -> None:
    roles = [("arbitro1", "primero"), ("arbitro2", "segundo"), ("anotador", "anotador")]
    for fila in parsing.leer_calendario(FICHERO_PRINCIPAL):
        cat = categorias.get(fila["categoria"])
        if cat is None or fila["fecha"] is None:
            continue
        partido = models.Partido(
            codigo_partido=fila["codigo_partido"],
            fecha=fila["fecha"],
            hora=fila["hora"],
            categoria_id=cat.id,
            jornada=fila["jornada"],
            numero_partido=fila["numero_partido"],
            local=fila["local"] or "(sin definir)",
            visitante=fila["visitante"] or "(sin definir)",
            campo=fila["campo"],
            provincia=fila["provincia"],
            estado="por_determinar" if not fila["campo"] else "pendiente",
        )
        db.add(partido)
        db.flush()

        # Reconstruir asignaciones de ejemplo a partir de los nombres del Excel.
        asignados = 0
        usados = set()
        for columna, rol in roles:
            nombre = fila[columna]
            if not nombre:
                continue
            arb = arbitros.get(nombre)
            if arb is None or arb.id in usados:
                continue
            usados.add(arb.id)
            db.add(
                models.Asignacion(
                    partido_id=partido.id,
                    arbitro_id=arb.id,
                    rol=rol,
                    origen="manual",
                )
            )
            asignados += 1

        if asignados >= cat.min_arbitros:
            partido.estado = "asignado"
    db.flush()


def cargar_domicilios_y_disponibilidad(db: Session) -> dict:
    """Completa domicilios/coordenadas y carga la disponibilidad real.

    - Domicilios desde `Relacion_licencias` (dirección, CP, municipio), cruzando
      por nombre con el cuerpo arbitral ya existente.
    - Coordenadas del concejo a partir del municipio (tabla `geo`).
    - Disponibilidad desde `Disponibilidad arbitros`: 'SI' → con/sin transporte
      según tenga coche; 'NO' → no disponible.
    """
    por_nombre = {
        _clave_nombre(a.nombre): a for a in db.query(models.Arbitro).all()
    }

    # 1) Domicilios desde el fichero de licencias.
    if FICHERO_LICENCIAS.exists():
        for lic in parsing.leer_licencias(FICHERO_LICENCIAS):
            arb = por_nombre.get(_clave_nombre(lic["nombre"]))
            if arb is None:
                continue
            if lic["direccion"]:
                arb.direccion = lic["direccion"]
            if lic["codigo_postal"]:
                arb.codigo_postal = lic["codigo_postal"]
            if lic["localidad"]:
                arb.localidad = lic["localidad"]

    # 2) Disponibilidad + ciudad/coche desde el fichero de disponibilidad.
    n_disp = 0
    if FICHERO_DISPONIBILIDAD.exists():
        for fila in parsing.leer_disponibilidad(FICHERO_DISPONIBILIDAD):
            arb = por_nombre.get(_clave_nombre(fila["nombre"]))
            if arb is None:
                continue
            if fila["nivel"]:
                arb.nivel_arbitral = fila["nivel"]
            if not arb.localidad and fila["ciudad"]:
                arb.localidad = fila["ciudad"]

            estado_disp = "con_transporte" if fila["coche"] else "sin_transporte"
            for fecha, franja, valor in fila["celdas"]:
                estado = estado_disp if valor == "SI" else "no_disponible"
                db.add(
                    models.Disponibilidad(
                        arbitro_id=arb.id, fecha=fecha, franja=franja, estado=estado
                    )
                )
                n_disp += 1

    # 3) Coordenadas aproximadas del concejo (respaldo offline para el mapa).
    #    La geocodificación exacta de la dirección se hace en otro paso.
    n_geo = 0
    for arb in por_nombre.values():
        coord = geo.coords_concejo(arb.localidad)
        if coord:
            arb.latitud, arb.longitud = coord
            arb.geocodificado = False
            n_geo += 1

    db.commit()
    return {"disponibilidades": n_disp, "geolocalizados": n_geo}


def cargar_polideportivos(db: Session) -> int:
    """Inserta el catálogo de polideportivos (sedes) con sus coordenadas."""
    existentes = {p.id for p in db.query(models.Polideportivo.id).all()}
    nuevos = 0
    for p in polideportivos_data.cargar():
        if p["id"] in existentes:
            continue
        db.add(models.Polideportivo(**p))
        nuevos += 1
    db.commit()
    return nuevos


def cargar_categorias_fed(db: Session) -> int:
    """Inserta el catálogo de categorías de competición (UUID + requisitos)."""
    existentes = {c.id for c in db.query(models.CategoriaFed.id).all()}
    nuevas = 0
    for c in categorias_fed.cargar():
        if c["id"] in existentes:
            continue
        db.add(models.CategoriaFed(**c))
        existentes.add(c["id"])
        nuevas += 1
    db.commit()
    return nuevas


def cargar_clubs_y_equipos(db: Session) -> dict:
    """Inserta clubs y sus equipos asociados (equipos externos sin club)."""
    cargar_categorias_fed(db)
    clubs_existentes = {c.id for c in db.query(models.Club.id).all()}
    n_clubs = 0
    for c in clubs_equipos.cargar_clubs():
        if c["id"] in clubs_existentes:
            continue
        db.add(models.Club(**c))
        clubs_existentes.add(c["id"])
        n_clubs += 1
    db.flush()

    equipos_existentes = {e.id for e in db.query(models.EquipoClub.id).all()}
    n_eq = 0
    for e in clubs_equipos.cargar_equipos():
        if e["id"] in equipos_existentes:
            continue
        # Seguridad: solo enlazar a un club que exista de verdad.
        club_id = e["club_id"] if e["club_id"] in clubs_existentes else None
        db.add(
            models.EquipoClub(
                id=e["id"],
                club_id=club_id,
                nombre=e["nombre"],
                categoria_uuid=e["categoria_uuid"],
            )
        )
        n_eq += 1
    db.commit()
    return {"clubs": n_clubs, "equipos": n_eq}


def geocodificar_arbitros(db: Session, permitir_red: bool = True) -> dict:
    """Geocodifica las direcciones reales a coordenadas exactas (Nominatim).

    Sustituye el centroide del concejo por la posición exacta de la dirección
    cuando se obtiene. Con `permitir_red=False` solo aplica resultados ya
    cacheados (arranque offline). Mantiene el centroide como respaldo.
    """
    n_preciso = n_aprox = 0
    for arb in db.query(models.Arbitro).all():
        if not (arb.direccion or arb.localidad):
            continue
        res = geocoding.geocodificar(
            arb.direccion, arb.codigo_postal, arb.localidad, permitir_red=permitir_red
        )
        if res:
            arb.latitud, arb.longitud, preciso = res
            arb.geocodificado = preciso
            n_preciso += int(preciso)
            n_aprox += int(not preciso)
        elif arb.latitud is None:
            coord = geo.coords_concejo(arb.localidad)
            if coord:
                arb.latitud, arb.longitud = coord
    db.commit()
    return {"precisos": n_preciso, "aproximados": n_aprox}


def cargar_datos_iniciales(db: Session) -> dict:
    """Ejecuta toda la carga. Devuelve un resumen con los conteos."""
    niveles = _crear_niveles(db)
    categorias = _crear_categorias(db, niveles)
    _crear_equipos(db, categorias)
    arbitros = _crear_arbitros(db)
    _crear_partidos(db, categorias, arbitros)
    db.commit()
    cargar_domicilios_y_disponibilidad(db)
    cargar_polideportivos(db)
    cargar_clubs_y_equipos(db)
    # Geocodificación exacta solo desde caché (no bloquea el arranque ni la red);
    # la geocodificación con red se lanza como paso explícito.
    geocodificar_arbitros(db, permitir_red=False)
    return {
        "niveles": db.query(models.Nivel).count(),
        "categorias": db.query(models.Categoria).count(),
        "equipos": db.query(models.Equipo).count(),
        "arbitros": db.query(models.Arbitro).count(),
        "partidos": db.query(models.Partido).count(),
        "asignaciones": db.query(models.Asignacion).count(),
        "disponibilidades": db.query(models.Disponibilidad).count(),
        "polideportivos": db.query(models.Polideportivo).count(),
        "clubs": db.query(models.Club).count(),
        "equipos_club": db.query(models.EquipoClub).count(),
        "categorias_fed": db.query(models.CategoriaFed).count(),
    }


def hay_datos(db: Session) -> bool:
    return db.query(models.Nivel).count() > 0


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if hay_datos(db):
            print("La base de datos ya contiene datos. No se hace nada.")
            return
        resumen = cargar_datos_iniciales(db)
        print("Carga inicial completada:")
        for clave, valor in resumen.items():
            print(f"  - {clave}: {valor}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
