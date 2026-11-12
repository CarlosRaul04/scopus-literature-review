# APIs usadas

Encabezados de Elsevier: `X-ELS-APIKey: <clave>`, `Accept: application/json` y, si existe, `X-ELS-Insttoken: <token>`.

## Scopus Search
`GET https://api.elsevier.com/content/search/scopus?query=...&start=0&count=25&sort=-coverDate&view=STANDARD`

- `count` máximo 25; paginar con `start`. Máximo 5000 resultados por consulta.
- `sort`: `-coverDate`, `+coverDate`, `-citedby-count`, `relevancy`, `-pubyear`.
- `view=COMPLETE` (requiere derecho institucional): agrega todos los autores (`author`), resumen (`dc:description`) y palabras clave (`authkeywords`).
- Campos que usa el script: `dc:title`, `dc:creator`, `prism:publicationName`, `prism:issn`, `prism:eIssn`, `source-id`, `prism:volume`, `prism:issueIdentifier`, `prism:pageRange`, `article-number`, `prism:coverDate`, `prism:doi`, `eid`, `dc:identifier`, `citedby-count`, `subtypeDescription`, `prism:aggregationType`, `openaccessFlag`, `affiliation[]`.
- Resultado vacío: `entry: [{"error": "Result set was empty"}]`.
- Cuota en los encabezados: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (epoch).

## Serial Title (métricas de revistas)
`GET https://api.elsevier.com/content/serial/title/issn/{ISSN}?view=CITESCORE`

- `subject-area[]`: `@code` (ASJC de 4 dígitos), `@abbrev`, `$` (nombre).
- `citeScoreYearInfoList`: `citeScoreCurrentMetric`, `citeScoreCurrentMetricYear`, `citeScoreTracker`, `citeScoreTrackerYear`, `citeScoreYearInfo[]` (`@year`, `@status` = `Complete` o `In-Progress`, `citeScoreInformationList[].citeScoreInfo[].citeScoreSubjectRank[]` con `subjectCode`, `rank`, `percentile`).
- `SJRList.SJR[]` y `SNIPList.SNIP[]`: `@year`, `$`. A veces vienen como objeto en vez de lista; el script lo normaliza.
- Consultar por **ISSN**; el endpoint por `source_id` dio resultados equivocados en pruebas.

## Abstract Retrieval
`GET https://api.elsevier.com/content/abstract/eid/{EID}?view=META_ABS` (o `/doi/{DOI}`).

- Resumen en `abstracts-retrieval-response.coredata.dc:description`. El script quita la línea de copyright final.
- Requiere derecho (red de la institución o token). Ante el primer 401/403 el script deja de intentarlo en esa ejecución y sigue con fuentes abiertas.

## Crossref
`GET https://api.crossref.org/works/{DOI}?mailto={correo}`

- Sin clave. Con `mailto` se entra al *polite pool* (más estable).
- `message`: `title[]`, `author[]` (`given`, `family`, `name` para autores institucionales, `ORCID`), `container-title[]`, `published-print` / `published-online` / `issued` (`date-parts`), `volume`, `issue`, `page`, `article-number`, `publisher`, `type`, `abstract` (JATS XML, opcional).

## OpenAlex
`GET https://api.openalex.org/works/doi:{DOI}?mailto={correo}`

- Sin clave. Resumen como índice invertido (`abstract_inverted_index`), que el script reconstruye.
- `open_access.oa_url` / `best_oa_location.pdf_url`: enlace de acceso abierto (lo usa `enrich` para `oa_pdf`).

## Semantic Scholar
`GET https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}?fields=title,abstract,year,authors,openAccessPdf,tldr`

- Sin clave: límite compartido y estricto (esperar 3–5 s entre llamadas; responde 429). Con `x-api-key` es más holgado.
- Si la editorial no permite compartir el resumen, `abstract` viene vacío y `openAccessPdf.disclaimer` dice *elided by the publisher*; el script lo registra en `abstract_note`.

## Unpaywall (opcional)
`GET https://api.unpaywall.org/v2/{DOI}?email={correo}`

- `best_oa_location.url_for_pdf` o `.url`: copia legal de acceso abierto.
