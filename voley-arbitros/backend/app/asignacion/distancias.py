"""Distancias geográficas para la optimización de desplazamientos (RF2.3).

- `haversine`: distancia en km entre dos coordenadas (sin dependencias).
- `resolver_sedes`: casa el campo de cada partido (`Partido.campo`, texto libre)
  con un `Polideportivo` geolocalizado, por nombre normalizado (igual criterio
  que `geo._normalizar`). 38/39 sedes de los datos resuelven así.
"""
import math
import re
import unicodedata


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Distancia en kilómetros entre dos puntos (lat/lon en grados)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalizar(texto):
    if not texto:
        return ""
    texto = str(texto).replace("\xa0", " ").strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^A-Z0-9]+", " ", texto.upper()).strip()


def resolver_sedes(campos, polideportivos):
    """Devuelve {campo_original: (lat, lon)} para los campos reconocidos.

    `polideportivos` es la lista de modelos Polideportivo (nombre, lat, lon).
    Coincidencia exacta primero y, si no, por inclusión de subcadena.
    """
    indice = {}
    for p in polideportivos:
        indice[_normalizar(p.nombre)] = (p.latitud, p.longitud)

    salida = {}
    for campo in campos:
        if not campo:
            continue
        nc = _normalizar(campo)
        if not nc or nc == "POR DETERMINAR":
            continue
        if nc in indice:
            salida[campo] = indice[nc]
            continue
        # Coincidencia parcial (la más larga gana, para evitar falsos positivos).
        mejor = None
        for nombre, coord in indice.items():
            if nc in nombre or nombre in nc:
                if mejor is None or len(nombre) > mejor[0]:
                    mejor = (len(nombre), coord)
        if mejor:
            salida[campo] = mejor[1]
    return salida
