"""Conflictos de interés (RF2.4).

Un árbitro no debe arbitrar partidos en los que él mismo o un familiar participe.
Los datos disponibles no incluyen el vínculo árbitro→club/jugador, por lo que esta
comprobación queda como un gancho extensible: cuando se disponga de esa relación,
basta rellenar `EXCLUSIONES` o sustituir `hay_conflicto`.
"""

# {arbitro_id: {nombre_equipo_normalizado, ...}} con los que tiene conflicto.
EXCLUSIONES: dict[int, set[str]] = {}


def hay_conflicto(arbitro_id: int, local: str, visitante: str) -> bool:
    equipos = EXCLUSIONES.get(arbitro_id)
    if not equipos:
        return False
    cand = {(local or "").strip().upper(), (visitante or "").strip().upper()}
    return bool(equipos & cand)
