---
name: scopus-literature-review
description: Busca artículos en Scopus con la API de Elsevier, saca el cuartil de cada revista por área (CiteScore), completa resúmenes y autores con Crossref, OpenAlex y Semantic Scholar y cita en APA 7 o BibTeX sin inventar datos. Úsala para revisiones de literatura, estado del arte, antecedentes, elegir revista por cuartil (Q1–Q4) o cuando el usuario mencione Scopus, Elsevier, CiteScore, SJR o cuartiles. Also for Scopus literature search, journal quartiles and citations in any language.
---

# Revisión de literatura con Scopus

Esta skill convierte un pedido como «búscame artículos sobre X en revistas Q3 o Q4 desde 2020, con resumen y cita APA» en una tabla verificable. Todo se hace con `scripts/scopus.py`, que solo usa la librería estándar de Python 3.10+.

## Reglas que no se rompen

1. **Nunca inventes datos.** Si un resumen, cuartil, autor, página o DOI no aparece en las APIs, escribe «no aparece» (o «not found» si el usuario escribe en inglés). No completes desde la memoria.
2. **La clave de API es del usuario.** Pídesela si no está en `SCOPUS_API_KEY`, expórtala solo para la sesión y nunca la escribas en archivos, artifacts, repositorios, páginas publicadas ni en la respuesta.
3. **Los resultados van a archivos, no al chat.** Guarda JSON y CSV; en el chat muestra solo la tabla final o un resumen.
4. **Cita con los datos de Crossref**, no con los de Scopus Search (que solo trae el primer autor) ni de memoria.
5. **Di de dónde sale cada cuartil**: «cuartil por CiteScore (Scopus), año X». No lo presentes como cuartil SJR/SCImago ni JCR: pueden no coincidir.
6. **Registra cada búsqueda** (el script lo hace en `search_log.csv`): la consulta exacta, la fecha y el total. Así la revisión es reproducible.

## 1. Preparación (una vez por sesión)

```bash
export SCOPUS_API_KEY="<clave que dé el usuario>"
export CONTACT_EMAIL="<correo del usuario, opcional>"   # Crossref polite pool y Unpaywall
python3 scripts/scopus.py check
```

`check` confirma que la clave funciona, muestra la cuota semanal restante y si hay acceso a métricas de revistas.

Variables opcionales: `SCOPUS_INSTTOKEN` (token institucional: trae todos los autores y el resumen desde Scopus), `S2_API_KEY` (Semantic Scholar sin pausas largas), `SCOPUS_CACHE_DIR`.

**Si la conexión falla** (`No se pudo conectar…`, proxy, `connect_rejected`): el entorno no permite `api.elsevier.com`. Díselo al usuario en una línea y ofrece dos salidas: habilitar el dominio en la configuración de su entorno o ejecutar el script en su computadora. No intentes rodear el bloqueo con otros comandos.

Si el usuario no tiene clave: se crea gratis en https://dev.elsevier.com («I want an API key»), pero normalmente solo funciona si su institución está suscrita a Scopus. Ver `references/troubleshooting.md`.

## 2. Aclarar el pedido

Antes de buscar, asegúrate de tener (pregunta solo lo que falte y cambie el resultado):

- **Tema** y, si los hay, conceptos que deben aparecer juntos.
- **Años**, **idioma** y **tipo de documento** (artículo, revisión, conferencia).
- **Cuartil objetivo** (p. ej. Q1–Q2, o Q3–Q4 para publicar en revistas más accesibles).
- **Cuántos resultados** quiere y **para qué**: antecedentes (pocos y relevantes), revisión sistemática (todos, con registro PRISMA) o elegir revista.

## 3. Construir la consulta

Divide el tema en 2–3 conceptos; para cada uno junta sinónimos con `OR` y une los conceptos con `AND`:

```
TITLE-ABS-KEY(("cognitive accessibility" OR "easy read*") AND (news OR journalism)) AND PUBYEAR > 2019 AND DOCTYPE(ar)
```

- Usa `*` para variantes (`neurodiver*`), comillas para frases exactas y `W/n` para proximidad.
- `PUBYEAR > 2019` significa desde 2020.
- Prueba primero con `--max 25`: si el total es enorme (> 1000), acota; si es casi cero, amplía sinónimos o quita un concepto.
- Mira los primeros resultados: si aparecen trabajos ajenos al tema (Scopus también busca en las palabras clave indexadas), ajusta la consulta, por ejemplo pasando a `TITLE()` o agregando un concepto.
- Por defecto se ordena por relevancia. Usa `--sort -coverDate` para lo más reciente (incluye artículos «en prensa» con fecha del año siguiente) o `--sort -citedby-count` para lo más citado.
- **Windows / PowerShell:** PowerShell quita las comillas dobles internas al pasarlas a Python. Escribe la consulta en un archivo de texto y usa `--query-file consulta.txt`, o escapa las comillas: `'TITLE-ABS-KEY(\"frase exacta\")'`.
- Sintaxis completa, códigos de área y ejemplos: `references/query-syntax.md`.

## 4. Flujo de trabajo

```bash
# 1) Buscar (guarda JSON y anota la búsqueda en search_log.csv)
python3 scripts/scopus.py search 'TITLE-ABS-KEY(...) AND PUBYEAR > 2019' --max 100 --out resultados.json

# 2) Enriquecer: cuartil por área, CiteScore, SJR, autores completos, páginas, resumen
python3 scripts/scopus.py enrich resultados.json            # → resultados_enriched.json
#    el enlace a PDF abierto (oa_pdf) sale de OpenAlex; --oa busca además en Unpaywall (requiere CONTACT_EMAIL)
#    --no-abstracts si solo se necesitan métricas

# 3) Filtrar
python3 scripts/scopus.py filter resultados_enriched.json --quartiles Q3,Q4 --since 2020 --doctype Article
#    --any-area acepta la revista si tiene ese cuartil en cualquiera de sus áreas
#    --journals-only deja solo revistas (excluye series de libros y actas, como LNCS)
#    --with-abstract, --min-citations N, --open-access

# 4) Exportar y citar
python3 scripts/scopus.py export resultados_enriched_filtered.json --format csv
python3 scripts/scopus.py export resultados_enriched_filtered.json --format md
python3 scripts/scopus.py cite --file resultados_enriched_filtered.json --style apa --out referencias.md
python3 scripts/scopus.py cite --file resultados_enriched_filtered.json --style bibtex --out refs.bib
```

Consultas sueltas:

```bash
python3 scripts/scopus.py journal 0747-5632 1071-5819     # métricas y cuartil por área de revistas
python3 scripts/scopus.py abstract 10.xxxx/yyyy           # resumen de un artículo
python3 scripts/scopus.py cite 10.xxxx/yyyy --style bibtex
python3 scripts/scopus.py merge a.json b.json --out todos.json   # unir búsquedas sin duplicados
python3 scripts/scopus.py summary todos_enriched.json --by journal   # revistas, años o cuartiles
```

Para revisiones con muchos registros, el enriquecimiento tarda (Semantic Scholar sin clave permite ~1 llamada cada 3–4 s). Avísale al usuario y trabaja en segundo plano si el entorno lo permite. La caché evita repetir llamadas.

## 5. Cómo se calcula el cuartil

- Scopus da, para cada revista y **cada área temática**, un percentil de CiteScore. Cuartil: ≥ 75 → Q1 · 50–74 → Q2 · 25–49 → Q3 · < 25 → Q4.
- El script usa el **año oficial de CiteScore** (`citeScoreCurrentMetricYear`), no el *CiteScore Tracker* del año en curso, que cambia cada mes.
- **Series de libros y actas** (Lecture Notes in Computer Science, CCIS, etc.) también tienen CiteScore y cuartil en Scopus, pero es el cuartil de la **serie**, no de una revista. El script lo marca en `quartile_note`. Si el usuario pide «revistas Q1–Q2», usa `--journals-only` o avísale.
- Una revista puede ser Q2 en un área y Q4 en otra. `quartile_best` es el mejor; `quartiles_by_area` los muestra todos. Si el usuario necesita el cuartil en un área concreta, usa esa.
- SJR (SCImago) y JCR (Clarivate) tienen sus propios cuartiles. Si el usuario o su institución exige uno de ellos, dilo y sugiere confirmarlo en https://www.scimagojr.com o en JCR.
- Detalle y advertencias: `references/metrics.md`.

## 6. Qué entregar

Por defecto, una tabla con: **título, autores, año, revista, cuartil (con área), citas, DOI y un resumen de 1–2 líneas en el idioma del usuario**, más:

- los archivos (`.csv`, `.md`, `referencias.md` o `refs.bib`) y `search_log.csv`;
- una línea con la consulta usada, la fecha y cuántos resultados hubo en cada paso (encontrados → con cuartil → tras filtros);
- los huecos: cuántos registros quedaron con «no aparece» y en qué campo (`missing`).

El resumen de 1–2 líneas lo escribes tú **a partir del resumen recuperado**; si no hay resumen, pon «no aparece» y no lo deduzcas del título.

**De dónde salen los resúmenes:** Scopus (si la clave tiene derecho a Abstract Retrieval o hay token institucional) → Crossref → OpenAlex → Semantic Scholar. Varias editoriales grandes (Elsevier, Springer y otras) **no permiten** compartir sus resúmenes en fuentes abiertas; en ese caso `abstract_note` lo dice. Si tienes una herramienta para leer páginas web, puedes abrir `https://doi.org/<DOI>` y tomar el resumen de la página de la editorial; anota la fuente como «página de la editorial». Si tampoco aparece ahí, queda «no aparece».

## 7. Revisión sistemática (PRISMA)

Si el usuario hace una revisión sistemática: guarda cada consulta (el script ya lo hace), no borres los archivos intermedios y reporta los números de cada etapa. La guía de cribado, duplicados y diagrama PRISMA está en `references/workflow.md`.

## 8. Antes de entregar, verifica

- [ ] Cada fila tiene DOI o dice «no aparece».
- [ ] Ningún resumen ni autor salió de tu memoria.
- [ ] El cuartil dice de qué área y año es; si `journal_check` avisa de un `source-id` distinto, revísalo.
- [ ] Las citas APA tienen el título en minúsculas de oración (APA 7): Crossref lo entrega como lo depositó la editorial; corrígelo respetando nombres propios y siglas.
- [ ] La clave no aparece en ningún archivo entregado.

## Referencias

- `references/query-syntax.md` — campos, operadores, códigos de área y tipos de documento, ejemplos por disciplina.
- `references/metrics.md` — CiteScore, SJR, SNIP, cuartiles y sus diferencias.
- `references/workflow.md` — revisión sistemática, PRISMA, duplicados, cribado.
- `references/troubleshooting.md` — errores HTTP, cuotas, clave sin permisos, red bloqueada.
- `references/apis.md` — endpoints, límites y campos de cada API.
