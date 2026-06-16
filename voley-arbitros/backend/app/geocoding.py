"""Geocodificación de direcciones mediante Nominatim (OpenStreetMap).

No requiere clave de API. Para cumplir la política de uso de Nominatim se
limita a 1 petición por segundo y se identifica con un User-Agent propio.
Los resultados se cachean en disco (`data/geocache.json`) para que las
sucesivas ejecuciones sean instantáneas y no repitan llamadas a la red.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "geocache.json"
_BASE = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "RefMe-TFM-Voleibol-Asturias/1.0 (designacion arbitral)"
_INTERVALO = 1.1  # segundos entre peticiones (política de Nominatim)

_cache = None
_ultimo_request = 0.0


def _cargar_cache():
    global _cache
    if _cache is None:
        if _CACHE_PATH.exists():
            try:
                _cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                _cache = {}
        else:
            _cache = {}
    return _cache


def _guardar_cache():
    if _cache is not None:
        _CACHE_PATH.write_text(
            json.dumps(_cache, ensure_ascii=False, indent=0), encoding="utf-8"
        )


def _limpiar_direccion(direccion: str) -> str:
    """Quita saltos de línea y detalles de piso/puerta que confunden al geocoder."""
    texto = direccion.replace("\n", ", ")
    # Eliminar indicaciones de planta/puerta tipo "9ºC", "1ºE", "5ºB", "3 dcha".
    texto = re.sub(r"\b\d+\s*[ºª°]\s*[A-Za-z]?\b", " ", texto)
    texto = re.sub(r"\b(\d+\s*)?(dcha|izda|izq|bajo|esc|escalera|portal)\.?\b",
                   " ", texto, flags=re.IGNORECASE)
    texto = re.sub(r"[;,]\s*[;,]+", ", ", texto)
    return re.sub(r"\s+", " ", texto).strip(" ,;")


def _consultar(query: str):
    """Llama a Nominatim respetando el límite de frecuencia. Devuelve (lat, lon) o None."""
    global _ultimo_request
    espera = _INTERVALO - (time.monotonic() - _ultimo_request)
    if espera > 0:
        time.sleep(espera)
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "es"}
    )
    req = urllib.request.Request(
        f"{_BASE}?{params}", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            datos = json.load(r)
    except Exception:
        return None
    finally:
        _ultimo_request = time.monotonic()
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def geocodificar(direccion, codigo_postal, localidad, permitir_red=True):
    """Devuelve (lat, lon, preciso) para una dirección.

    Estrategia en cascada (con caché por cada consulta):
      1. Dirección completa + CP + localidad  → resultado preciso.
      2. Localidad + CP                        → aproximado (centro de zona).
    Con `permitir_red=False` solo se usan resultados ya cacheados (no llama a la
    red), lo que permite arranques offline instantáneos. Devuelve None si no hay
    nada disponible.
    """
    cache = _cargar_cache()

    intentos = []
    if direccion:
        partes = [_limpiar_direccion(direccion)]
        if codigo_postal:
            partes.append(str(codigo_postal))
        if localidad:
            partes.append(localidad)
        intentos.append(("preciso", ", ".join(partes) + ", Asturias, España"))
    if localidad:
        cp = f"{codigo_postal} " if codigo_postal else ""
        intentos.append(("aprox", f"{cp}{localidad}, Asturias, España"))

    for nivel, query in intentos:
        if query in cache:
            res = cache[query]
        elif permitir_red:
            res = _consultar(query)
            cache[query] = res  # se cachea también el None (sin resultado)
            _guardar_cache()
        else:
            continue
        if res:
            return res[0], res[1], nivel == "preciso"

    return None
