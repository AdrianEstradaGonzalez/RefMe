"""Equivalencia de niveles entre el árbitro y el nivel exigido por la categoría.

El cuerpo arbitral usa un vocabulario propio (`Arbitro.nivel_arbitral`:
"NIVEL I", "NIVEL II - HABILITADO NIVEL III", "UNIFORME NACIONAL"…) distinto del
que exigen las categorías (`Nivel.orden`, jerarquía "Candidato Territorial I
Pista" → "Internacional Pista"). Ambos se proyectan sobre una escala ordinal
común 0–8 para poder comprobar si un árbitro alcanza el nivel mínimo del rol
(RF2.2).

La correspondencia es monótona y está confirmada por las categorías de los
datos (p. ej. "Nivel II + Hab. Nacional C" ⇔ que el árbitro tenga "NIVEL II -
HABILITADO NIVEL III"). Es una tabla CONFIGURABLE: ante un cambio normativo de
la federación basta editar `RANGO_ARBITRO`.
"""

# nivel_arbitral (normalizado a mayúsculas) -> rango 0..8
RANGO_ARBITRO = {
    "NIVEL I": 1,
    "NIVEL I - HABILITADO NIVEL II": 2,
    "NIVEL II": 3,
    "NIVEL II - HABILITADO NIVEL III": 4,
    "NIVEL III - C": 5,
    "NIVEL III - B": 6,
    "NIVEL III - A": 7,
    "UNIFORME NACIONAL": 8,
    # Anotadores: capacitados para el rol de anotador en su rango equivalente.
    "ANOTADOR TERRITORIAL": 1,
    "ANOTADOR NACIONAL B": 5,
}

ROLES = ("primero", "segundo", "anotador")


def rango_arbitro(nivel_arbitral) -> int:
    """Rango 0..8 del árbitro (0 si no consta o está en formación)."""
    if not nivel_arbitral:
        return 0
    return RANGO_ARBITRO.get(nivel_arbitral.strip().upper(), 0)


def rango_exigido(categoria, rol) -> int | None:
    """Rango mínimo exigido por la categoría para un rol, o None si no se exige.

    Se deriva de `Nivel.orden` (1..9) del nivel asociado al rol → rango 0..8.
    """
    if categoria is None:
        return None
    nivel = {
        "primero": categoria.nivel_primero,
        "segundo": categoria.nivel_segundo,
        "anotador": categoria.nivel_anotador,
    }.get(rol)
    if nivel is None:
        return None
    return max(0, nivel.orden - 1)


def roles_requeridos(categoria):
    """Lista [(rol, rango_exigido)] de los roles que la categoría exige cubrir.

    Si el nº de roles marcados es menor que `min_arbitros`, se completa con los
    roles restantes (rango exigido 0) para alcanzar el mínimo de árbitros.
    """
    requeridos = []
    for rol in ROLES:
        requiere = getattr(categoria, f"requiere_{rol}", False) if categoria else False
        if requiere:
            requeridos.append((rol, rango_exigido(categoria, rol) or 0))

    minimo = categoria.min_arbitros if categoria else 1
    if len(requeridos) < minimo:
        ya = {r for r, _ in requeridos}
        for rol in ROLES:
            if rol not in ya:
                requeridos.append((rol, rango_exigido(categoria, rol) or 0))
            if len(requeridos) >= minimo:
                break
    return requeridos


def cumple_nivel(rango_arb: int, rango_min) -> bool:
    """True si el árbitro alcanza el nivel mínimo del rol."""
    if rango_min is None:
        return True
    return rango_arb >= rango_min
