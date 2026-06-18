# RefMe — Designación arbitral de voleibol (Asturias)

Sistema inteligente para asignar árbitros a partidos de voleibol de la Federación
de Voleibol del Principado de Asturias (FVBPA). El objetivo es automatizar un
proceso que hoy se hace a mano: repartir los árbitros entre los partidos de cada
jornada respetando disponibilidad, nivel, horarios y conflictos de interés, y a la
vez reduciendo los desplazamientos y repartiendo la carga de forma equitativa.

Este repositorio es el código del Trabajo de Fin de Máster *"Sistema inteligente
para la optimización de designaciones arbitrales en el voleibol"*.

## Arquitectura

- **Backend** (`voley-arbitros/backend`): API REST con [FastAPI](https://fastapi.tiangolo.com/),
  base de datos SQLite vía SQLAlchemy y el motor de asignación.
- **Frontend** (`voley-arbitros/frontend`): interfaz web estática (HTML + CSS +
  JavaScript) servida por el propio backend.

### El motor de asignación

El núcleo está en `voley-arbitros/backend/app/asignacion/` y combina tres fases
(enfoque híbrido):

1. **`greedy.py`** — construcción inicial golosa que respeta disponibilidad, nivel
   y horarios sin solape.
2. **`cpsat.py`** — optimización con el solver [CP-SAT](https://developers.google.com/optimization/cp/cp_solver/)
   de OR-Tools, sembrado con la solución golosa.
3. **`local.py`** — búsqueda local (relleno, *move* y *swap*) que pule el resultado.

Las restricciones (disponibilidad, niveles, conflictos, coche compartido,
distancias) se modelan en `datos.py`, `niveles.py`, `conflictos.py` y
`distancias.py`. El pipeline completo y las métricas están en `pipeline.py`.

## Requisitos

- Python 3.10 o superior.
- Las dependencias de `voley-arbitros/backend/requirements.txt` (FastAPI, Uvicorn,
  SQLAlchemy, Pydantic, openpyxl, OR-Tools).

## Puesta en marcha

```bash
cd voley-arbitros
./run.sh
```

El script crea un entorno virtual, instala las dependencias y arranca el servidor
de desarrollo. La primera vez se cargan los datos iniciales desde los Excel de
`backend/data/`.

Después, abre <http://127.0.0.1:8000> en el navegador.

> En Windows, si no puedes ejecutar `run.sh`, puedes arrancarlo a mano:
> ```bash
> cd voley-arbitros/backend
> python -m venv .venv && .venv\Scripts\activate
> pip install -r requirements.txt
> uvicorn app.main:app --reload
> ```

## Funcionalidades

- Gestión de árbitros (con mapa del cuerpo arbitral) y su disponibilidad por
  franjas horarias y transporte.
- Calendario de partidos y catálogo de categorías, clubs y equipos.
- Designación automática de un rango de fechas, con métricas de cobertura,
  kilometraje y equidad, previsualización y publicación al calendario.

## Estructura del repositorio

```
voley-arbitros/
├── backend/
│   ├── app/
│   │   ├── asignacion/   # motor de asignación (las 3 fases + restricciones)
│   │   ├── routers/      # endpoints de la API REST
│   │   ├── main.py       # punto de entrada FastAPI
│   │   └── models.py     # modelos ORM del dominio
│   └── data/             # datos iniciales (Excel) y caché de geocodificación
├── frontend/             # interfaz web estática
└── run.sh                # arranque del servidor de desarrollo
```
