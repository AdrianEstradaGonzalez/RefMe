"""Geolocalización aproximada de árbitros por concejo (RF2.3 / mapa).

No dependemos de ningún servicio externo: se usa una tabla de coordenadas
(centroides de la capital de cada concejo asturiano) indexada por el nombre del
municipio normalizado. Es suficiente para situar a cada árbitro en su zona del
Principado en el mapa interactivo. La dispersión de árbitros que comparten
municipio se resuelve en el cliente con un pequeño desplazamiento determinista.
"""
import re
import unicodedata

# Centroides (lat, lon) de la capital de cada concejo. Cubre los municipios
# presentes en los datos y un conjunto amplio del Principado para robustez.
CONCEJOS = {
    "GIJON": (43.5357, -5.6615),
    "OVIEDO": (43.3603, -5.8448),
    "AVILES": (43.5560, -5.9222),
    "SIERO": (43.3922, -5.6628),          # Pola de Siero
    "NORENA": (43.3886, -5.6889),
    "LLANES": (43.4199, -4.7556),
    "INFIESTO": (43.3506, -5.3761),       # Piloña
    "PILONA": (43.3506, -5.3761),
    "MIERES": (43.2503, -5.7765),
    "CASTRILLON": (43.5556, -5.9972),     # Piedras Blancas
    "CARRENO": (43.5872, -5.7575),        # Candás
    "LANGREO": (43.3000, -5.6886),        # Sama
    "SAN MARTIN DEL REY AURELIO": (43.2790, -5.6510),
    "LAVIANA": (43.2430, -5.5520),
    "VILLAVICIOSA": (43.4830, -5.4350),
    "CORVERA": (43.4720, -5.9170),
    "CORVERA DE ASTURIAS": (43.4720, -5.9170),
    "GOZON": (43.6170, -5.8330),          # Luanco
    "GRADO": (43.3900, -6.0670),
    "PRAVIA": (43.4900, -6.1120),
    "NAVIA": (43.5390, -6.7220),
    "VALDES": (43.5440, -6.5370),         # Luarca
    "LUARCA": (43.5440, -6.5370),
    "CANGAS DE ONIS": (43.3510, -5.1300),
    "RIBADESELLA": (43.4620, -5.0580),
    "CANGAS DEL NARCEA": (43.1780, -6.5470),
    "TINEO": (43.3340, -6.4150),
    "LENA": (43.1560, -5.8290),           # Pola de Lena
    "ALLER": (43.1230, -5.6720),          # Cabañaquinta
    "SALAS": (43.4090, -6.2630),
    "LLANERA": (43.4560, -5.8730),        # Posada
    "NAVA": (43.3540, -5.5070),
    "COLUNGA": (43.4800, -5.2680),
    "PARRES": (43.3060, -5.0930),         # Arriondas
    "RIBERA DE ARRIBA": (43.2900, -5.8400),
    "MORCIN": (43.3060, -5.8550),
    "RIOSA": (43.2300, -5.8270),
    "BIMENES": (43.3290, -5.5760),
    "SARIEGO": (43.4070, -5.5390),
    "CABRANES": (43.3760, -5.4290),
    "PROAZA": (43.2520, -6.0220),
    "CANDAMO": (43.4500, -6.0830),
    "LAS REGUERAS": (43.4090, -5.9460),
    "SOTO DEL BARCO": (43.5400, -6.0570),
    "MUROS DE NALON": (43.5430, -6.1080),
    "CUDILLERO": (43.5630, -6.1460),
    "RIBADEDEVA": (43.3870, -4.5170),     # Colombres
    "PEÑAMELLERA BAJA": (43.3450, -4.6010),
    "PENAMELLERA BAJA": (43.3450, -4.6010),
    "ONIS": (43.3030, -4.9840),
    "CABRALES": (43.3050, -4.8290),
    "AMIEVA": (43.2840, -5.1010),
    "PONGA": (43.2200, -5.1700),
    "CASO": (43.2160, -5.3760),
    "SOBRESCOBIO": (43.2510, -5.4690),
    "TEVERGA": (43.1610, -6.0960),
    "QUIROS": (43.1700, -5.9920),
    "SOMIEDO": (43.0950, -6.2540),
    "BELMONTE DE MIRANDA": (43.2870, -6.2230),
    "YERNES Y TAMEZA": (43.2920, -6.1320),
    "ILLAS": (43.4990, -5.9580),
    "CARAVIA": (43.4670, -5.1860),
    "CARAVIA ALTA": (43.4670, -5.1860),
    "PESOZ": (43.2480, -6.8770),
    "ALLANDE": (43.2680, -6.6240),        # Pola de Allande
    "ILLANO": (43.3290, -6.8350),
    "BOAL": (43.4350, -6.8170),
    "VILLAYON": (43.3690, -6.6620),
    "COANA": (43.4830, -6.7470),
    "EL FRANCO": (43.5500, -6.8000),      # La Caridad
    "TAPIA DE CASARIEGO": (43.5700, -6.9430),
    "CASTROPOL": (43.5380, -7.0290),
    "VEGADEO": (43.4750, -7.0480),
    "SAN TIRSO DE ABRES": (43.4100, -7.1280),
    "TARAMUNDI": (43.3590, -7.1110),
    "VILLANUEVA DE OSCOS": (43.3500, -6.9700),
    "SANTA EULALIA DE OSCOS": (43.3050, -6.9920),
    "GRANDAS DE SALIME": (43.2210, -6.8770),
    "DEGANA": (42.9460, -6.6210),
    "IBIAS": (43.0190, -6.7700),
    "BELMONTE": (43.2870, -6.2230),
    "PONTES": (43.2200, -5.1700),
    "NUEVO": (43.3540, -5.5070),
}

# Centro del Principado (fallback cuando no se reconoce el municipio).
ASTURIAS_CENTRO = (43.3614, -5.8593)


def _normalizar(texto):
    if not texto:
        return ""
    texto = str(texto).replace("\xa0", " ").strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", texto).upper()


def coords_concejo(localidad):
    """Devuelve (lat, lon) del concejo, o None si no se reconoce."""
    clave = _normalizar(localidad)
    if not clave:
        return None
    if clave in CONCEJOS:
        return CONCEJOS[clave]
    # Coincidencia parcial: "GIJON (ASTURIAS)", "POLA DE SIERO", etc.
    for nombre, coord in CONCEJOS.items():
        if nombre in clave or clave in nombre:
            return coord
    return None
