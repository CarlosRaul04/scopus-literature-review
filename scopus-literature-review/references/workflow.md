# Flujos de trabajo

## A. Antecedentes o estado del arte (lo más común)

Objetivo: 10–40 trabajos relevantes y recientes, bien citados.

1. 1–3 consultas con sinónimos; por defecto se ordena por relevancia; `--sort -citedby-count` para los más influyentes y `-coverDate` para lo reciente.
2. `enrich` → `filter` (años, tipo, cuartil si se pide, `--with-abstract`).
3. Lee los resúmenes recuperados y descarta los que no responden a la pregunta. Explica en una línea por qué quedó cada uno, si el usuario lo pide.
4. Entrega tabla + referencias APA/BibTeX.

Combina los dos órdenes: los más citados dan el marco clásico; los recientes, el estado actual.

## B. Elegir revista para publicar

1. Busca trabajos cercanos al del usuario y mira en qué revistas salieron:
   ```bash
   python3 scripts/scopus.py search 'TITLE-ABS-KEY(...)' --max 200 --out cercanos.json
   python3 scripts/scopus.py enrich cercanos.json --no-abstracts
   ```
2. Agrupa por revista: cuántos trabajos cercanos publicó cada una, mejor cuartil, CiteScore y SJR:
   ```bash
   python3 scripts/scopus.py summary cercanos_enriched.json --by journal --top 20
   ```
   Para las 3–5 más prometedoras, muestra el cuartil por área con `journal <ISSN>`.
3. Advierte que hay que revisar en la web de cada revista: alcance, idioma, costos (APC), tiempos de revisión y si sigue indexada.

## C. Revisión sistemática (PRISMA 2020)

La skill no reemplaza el protocolo, pero deja el rastro que PRISMA pide.

1. **Registrar**: cada consulta queda en `search_log.csv` (fecha, consulta exacta, total). No cambies consultas sin registrar la nueva versión.
2. **Recuperar todo**: `--max` igual al total (hasta 5000). Si el total pasa de 5000, divide por años (`PUBYEAR = 2021`, `PUBYEAR = 2022`…) y une los archivos.
3. **Duplicados**: si combinas varias consultas, únelas con
   ```bash
   python3 scripts/scopus.py merge consulta1.json consulta2.json --out todos.json
   ```
   Elimina duplicados por DOI, luego por EID de Scopus y luego por título + año. El conteo de eliminados queda en `meta.duplicates_removed`.
4. **Cribado por título y resumen**: aplica los criterios de inclusión/exclusión del usuario. Si los aplicas tú, marca cada decisión con el motivo en una columna, para que el usuario la revise. No excluyas en silencio.
5. **Elegibilidad a texto completo**: la decide el usuario (o tú, si te da los PDF). `--oa` ayuda a encontrar los de acceso abierto.
6. **Números para el diagrama**: identificados en Scopus → duplicados eliminados → cribados → excluidos (con motivos) → evaluados a texto completo → incluidos.
7. Recuerda al usuario que una revisión sistemática suele exigir más de una base de datos (Web of Science, PubMed, etc.); esta skill solo cubre Scopus.

## D. Producción de un autor, institución o país

```bash
python3 scripts/scopus.py search 'AF-ID(<id>) AND PUBYEAR > 2019' --max 500 --out inst.json --show 0
python3 scripts/scopus.py enrich inst.json --no-abstracts
```

Luego agrupa con `summary inst_enriched.json --by year` (o `journal`, `quartile_best`, `doctype`) y muestra el resultado como tabla o gráfico. Para autores usa `AU-ID()`: los nombres son ambiguos.

## Resumen de 1–2 líneas

- Hazlo **solo** a partir del resumen recuperado (`abstract`), en el idioma del usuario.
- Incluye: qué se hizo, con quién o con qué, y el hallazgo principal si está.
- Si `abstract` es «no aparece», el resumen también es «no aparece».

## Archivos que deben quedar al final

| Archivo | Contenido |
|---|---|
| `search_log.csv` | Todas las búsquedas con fecha y total |
| `*_enriched.json` | Datos completos (para volver a filtrar sin repetir llamadas) |
| `*.csv` / `*.md` | Tabla final |
| `referencias.md` / `refs.bib` | Citas APA 7 / BibTeX |
