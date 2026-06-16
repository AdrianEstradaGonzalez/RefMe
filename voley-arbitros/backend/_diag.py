"""Diagnóstico: agenda del 2025-02-08 en Llanes y designaciones de id=31."""
import datetime as dt
from app.database import SessionLocal
from app import models

db = SessionLocal()
AID = 31
F = dt.date(2025, 2, 8)

# Todos los partidos de Llanes ese dia, con sus designaciones publicadas
parts = (db.query(models.Partido)
         .filter(models.Partido.fecha == F)
         .filter(models.Partido.campo.like("%LLANES%"))
         .order_by(models.Partido.hora).all())
print(f"== Partidos en Llanes el {F}: {len(parts)} ==")
for p in parts:
    asigs = db.query(models.Asignacion).filter(models.Asignacion.partido_id == p.id).all()
    nombres = []
    for a in asigs:
        ar = db.query(models.Arbitro).get(a.arbitro_id)
        marca = " <==id31" if a.arbitro_id == AID else ""
        nombres.append(f"{a.rol}:{ar.nombre if ar else '?'}{marca}")
    print(f"  p={p.id} {p.hora} {p.local} vs {p.visitante} | {p.categoria.nombre if p.categoria else '?'}")
    print(f"        designados: {nombres}")

# Todas las designaciones publicadas de id=31 en TODO el rango, ordenadas
print(f"\n== TODAS las publicadas de id=31 ==")
rows = db.query(models.Asignacion).filter(models.Asignacion.arbitro_id == AID).all()
items = []
for r in rows:
    p = db.query(models.Partido).get(r.partido_id)
    if p:
        items.append((p.fecha, p.hora, p.id, p.campo))
for f, h, pid, campo in sorted(items):
    print(f"  {f} {h} p={pid} @ {campo}")
db.close()
