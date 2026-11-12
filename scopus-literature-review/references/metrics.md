# Métricas de revistas y cuartiles

## Las métricas que entrega la API

| Métrica | Quién la calcula | Qué mide | Ventana |
|---|---|---|---|
| **CiteScore** | Elsevier (Scopus) | Citas promedio por documento | 4 años: citas recibidas en los años Y-3…Y por documentos publicados en esos mismos años |
| **CiteScore Tracker** | Elsevier | El CiteScore del año en curso, provisional | Se actualiza cada mes; no es oficial hasta que se publica el CiteScore anual (a mediados de año) |
| **Percentil de CiteScore** | Elsevier | Posición de la revista dentro de **cada** área temática (ASJC) | Mismo año que el CiteScore |
| **SJR** | SCImago (con datos de Scopus) | Prestigio: pondera las citas según la revista que cita | 3 años |
| **SNIP** | CWTS Leiden (con datos de Scopus) | Impacto normalizado según cuánto se cita en el campo | 3 años |

El **Factor de Impacto (JIF)** y los cuartiles **JCR** son de Clarivate (Web of Science). No salen de la API de Scopus y no se deben deducir de CiteScore.

## Cuartil por CiteScore (lo que calcula el script)

| Percentil | Cuartil |
|---|---|
| 75–99 | Q1 |
| 50–74 | Q2 |
| 25–49 | Q3 |
| 0–24 | Q4 |

- Se calcula **por área**. Una revista multidisciplinaria puede ser Q1 en un área y Q3 en otra.
- `quartile_best` es el mejor de sus áreas; muchas universidades aceptan el mejor, pero algunas exigen el del área del trabajo. Pregunta si importa.
- El script toma el año de `citeScoreCurrentMetricYear` con estado *Complete*. El *Tracker* puede subir o bajar y no debe usarse para afirmar el cuartil.

## Cuartil SCImago (SJR) y JCR

- SCImago publica cuartiles propios por categoría, basados en SJR. Suelen parecerse a los de CiteScore pero **no siempre coinciden** (otra fórmula, otra ventana y otras categorías).
- Muchas universidades y convocatorias latinoamericanas piden «cuartil SCImago». Si es el caso, el cuartil de esta skill sirve para preseleccionar, y el usuario debe confirmarlo en https://www.scimagojr.com buscando la revista por ISSN.
- La API entrega el **valor** de SJR, no el cuartil SCImago. No lo conviertas.

## Advertencias

- **Revistas nuevas** no tienen CiteScore hasta completar los años necesarios: el script devuelve cuartil vacío («no aparece»), no Q4.
- **Revistas descontinuadas** en Scopus pueden seguir apareciendo con métricas antiguas. Si el usuario quiere publicar ahí, sugiere revisar la lista de títulos descontinuados de Scopus.
- **ISSN impreso y electrónico**: el script prueba los dos. Si la revista no aparece con ninguno, puede que el ISSN del registro esté mal.
- **`source-id` distinto**: si el `source-id` del artículo no coincide con el de la revista consultada por ISSN, el campo `journal_check` lo avisa; revisa a mano antes de reportar el cuartil.
- **Series de libros y actas de conferencias** (LNCS, CCIS, Lecture Notes in…) sí tienen CiteScore y cuartil en Scopus, pero es el de la **serie**, que reúne volúmenes de muchas conferencias distintas. El script lo marca en `quartile_note`. Muchas universidades y convocatorias no lo cuentan como «cuartil de revista»: dilo siempre y usa `filter --journals-only` si el usuario pidió revistas.
- **Libros o actas sin serie indexada** no tienen cuartil. Repórtalo así, no como Q4.
- Los cuartiles cambian cada año: di siempre de qué año es el dato.

## Cómo reportarlo

> *Computers in Human Behavior* — CiteScore 2024: X; Q1 en Human-Computer Interaction (percentil 9X) según Scopus. SJR 2024: X.

Nunca: «es Q1» sin decir la fuente, el área y el año.
