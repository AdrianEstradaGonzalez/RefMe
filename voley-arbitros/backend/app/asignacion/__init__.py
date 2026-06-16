"""Algoritmo de asignación automática de árbitros a partidos (RF2).

Pipeline híbrido en tres fases:
  1. Greedy constructivo  (greedy.py)
  2. Solver CP-SAT         (cpsat.py)
  3. Búsqueda local / ILS  (local.py)

Punto de entrada: `pipeline.generar(db, opciones)`.
"""
from .pipeline import generar, OpcionesAsignacion

__all__ = ["generar", "OpcionesAsignacion"]
