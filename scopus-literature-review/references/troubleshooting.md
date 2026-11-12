# Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Falta la variable de entorno SCOPUS_API_KEY` | No se exportó la clave | Pedírsela al usuario y `export SCOPUS_API_KEY=...` |
| `HTTP 401` | Clave mal copiada, revocada o vencida | Revisar en https://dev.elsevier.com → *My API Key* |
| `HTTP 403` en búsqueda | La clave no tiene derecho a Scopus (la institución no está suscrita, o se llama desde fuera de su red) | Probar desde la red de la universidad o VPN; pedir un token institucional a la biblioteca |
| `HTTP 403` en Serial Title | La clave no tiene permiso para métricas de revistas | Seguir sin cuartil y avisar; consultar SCImago a mano |
| `HTTP 400 … Error translating query` | Paréntesis o comillas sin cerrar, campo mal escrito, `AND NOT` en medio | Revisar la consulta; probarla en la búsqueda avanzada de scopus.com |
| `HTTP 429` | Demasiadas llamadas por segundo o cuota semanal agotada | El script reintenta. Si persiste, `check` muestra la cuota y cuándo se renueva |
| `No se pudo conectar…` / `connect_rejected` / error de proxy | El entorno no permite ese dominio | Habilitar `api.elsevier.com` (y `api.crossref.org`, `api.semanticscholar.org`, `api.unpaywall.org`) o ejecutar el script en la computadora del usuario |
| 0 resultados | Filtros demasiado estrictos o error de sintaxis silencioso | Quitar filtros uno por uno; revisar `PUBYEAR >` (es estricto) |
| Total enorme | Consulta demasiado amplia | Pasar de `ALL()` a `TITLE-ABS-KEY()`, agregar un concepto, limitar años o área |
| Muchos «no aparece» en resumen | Elsevier, Springer y otras editoriales no permiten compartir los resúmenes en fuentes abiertas (Semantic Scholar lo indica como *elided by the publisher*); `abstract_note` lo explica | Con token institucional o desde la red de la institución, Scopus sí los entrega. Si no, el agente puede leer el resumen en la página del DOI |
| `unrecognized arguments` al buscar en PowerShell | PowerShell quita las comillas dobles de dentro de la consulta y la parte en varios argumentos | Guardar la consulta en un `.txt` y usar `--query-file consulta.txt`, o escapar: `'TITLE-ABS-KEY(\"frase\")'` |
| Resultados con fecha del año siguiente | Artículos «en prensa» ya asignados a un número futuro | Es normal. Para citar, el script usa el año del número (artículos) o la fecha de publicación (capítulos) |
| Trabajos ajenos al tema entre los resultados | Scopus también busca en palabras clave indexadas | Ajustar la consulta (`TITLE()`, otro concepto, `AND NOT`) |
| Semantic Scholar muy lento | Límite estricto sin clave | Pedir una clave gratuita en semanticscholar.org/product/api y exportarla como `S2_API_KEY` |
| Cuartil vacío para una revista conocida | ISSN distinto en el registro, revista nueva o descontinuada | Probar `journal` con el otro ISSN; buscarla en scopus.com/sources |
| `journal_check: source-id distinto` | El ISSN apunta a otra revista (pasa con revistas que cambiaron de nombre) | Verificar a mano antes de reportar el cuartil |
| Caracteres raros en CSV abierto en Excel | Codificación | El CSV se guarda en UTF-8 con BOM; si aún falla, importar como UTF-8 |

## Sobre la clave de Elsevier

- Se crea en https://dev.elsevier.com con una cuenta de Elsevier, idealmente con correo institucional.
- La clave gratuita da acceso a Scopus Search y a las métricas solo si la institución está suscrita a Scopus; la API verifica la IP o el token institucional.
- Cuotas habituales de la clave estándar: unas 20 000 búsquedas por semana y ~9 llamadas por segundo; cada página de búsqueda trae hasta 25 registros y una consulta hasta 5000. Pueden variar: `check` muestra la cuota real.
- Si una clave quedó visible en un chat, repositorio o captura de pantalla, regenérala en el portal.
- Respeta las condiciones de uso de Elsevier: los datos son para uso de investigación de la persona; no publiques volcados masivos de registros de Scopus.

## Borrar la caché

```bash
rm -rf ~/.cache/scopus-literature-review     # o la carpeta de SCOPUS_CACHE_DIR
python3 scripts/scopus.py journal <ISSN> --refresh   # solo una revista
```
