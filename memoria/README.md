# Memoria del TFM

Memoria del Trabajo de Fin de Máster *"Sistema inteligente para la optimización
de designaciones arbitrales en el voleibol"*.

## Ficheros

- `memoria.tex` — documento principal.
- `bibliografia.bib` — referencias (formato `apacite`).
- `capts/` — capturas de la aplicación usadas en el capítulo de desarrollo.

## Compilación

El documento usa el estilo `estilo_unir-1.sty` (plantilla de la UNIR) y el paquete
`apacite`, que **no** se incluyen en este repositorio. Para compilarlo necesitas
añadir `estilo_unir-1.sty` junto a `memoria.tex`.

La forma más cómoda es subir esta carpeta a [Overleaf](https://www.overleaf.com)
(que ya trae `apacite`), añadir el `estilo_unir-1.sty` y compilar con la secuencia
habitual:

```
pdflatex memoria
bibtex   memoria
pdflatex memoria
pdflatex memoria
```
