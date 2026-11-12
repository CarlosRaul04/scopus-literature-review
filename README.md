<div align="center">

# 📚 Scopus Literature Review

**Skill para Claude que hace revisiones de literatura con Scopus: busca artículos, saca el cuartil de cada revista, completa resúmenes y cita en APA 7 o BibTeX, sin inventar datos.**

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Dependencias](https://img.shields.io/badge/dependencias-ninguna-brightgreen)
![Licencia](https://img.shields.io/badge/licencia-MIT-green)
![Idioma](https://img.shields.io/badge/idioma-espa%C3%B1ol-orange)

[Instalación](#-instalación) · [Uso](#-uso) · [Comandos](#-comandos) · [Preguntas frecuentes](#-preguntas-frecuentes) · [English](#-english)

</div>

---

## ¿Qué es?

Una **skill** es un paquete de instrucciones y herramientas que Claude carga cuando la necesita. Con esta, le puedes pedir en lenguaje normal algo como:

> Búscame artículos de 2020 en adelante sobre accesibilidad web para personas con dislexia, solo en revistas Q1 o Q2. Dame una tabla con título, autores, año, revista, cuartil, DOI y un resumen de dos líneas, y las referencias en APA 7.

Y Claude:

1. Arma la consulta en la sintaxis avanzada de Scopus.
2. Busca en Scopus y guarda los resultados.
3. Saca el cuartil de cada revista en cada una de sus áreas.
4. Completa autores, páginas y resúmenes desde fuentes abiertas.
5. Filtra por cuartil, año o tipo de documento.
6. Te entrega la tabla, las referencias y un registro de la búsqueda.

## ¿Por qué esta skill?

Ya existen otras skills y servidores MCP para Scopus. Esta está pensada para quien escribe un artículo, una tesis o una revisión sistemática:

| | |
|---|---|
| 🎯 **Cuartil por área** | Calcula Q1–Q4 con el percentil de CiteScore **en cada área temática**, usando el año oficial (no el provisional). |
| 📘 **Distingue revistas de series** | Las series de libros y actas (como *Lecture Notes in Computer Science*) también tienen cuartil en Scopus, pero no son revistas. La skill lo marca y permite filtrarlas. |
| 📝 **Resúmenes de varias fuentes** | Prueba Scopus, Crossref, OpenAlex y Semantic Scholar, y dice de dónde salió cada resumen. |
| 🚫 **No inventa datos** | Si algo no aparece en las fuentes, escribe «no aparece» y explica por qué. Las citas salen de Crossref, no de la memoria del modelo. |
| 🔁 **Búsquedas reproducibles** | Cada búsqueda queda registrada con la consulta exacta, la fecha y el total encontrado. Sirve para el diagrama PRISMA. |
| 📦 **Sin instalar nada** | Un solo script de Python con la librería estándar. Funciona en Windows, macOS, Linux y en entornos en la nube. |

## 📋 Requisitos

- **Python 3.10 o superior.**
- **Una clave de API de Elsevier.** Se crea gratis en [dev.elsevier.com](https://dev.elsevier.com) (botón *I want an API key*). Normalmente solo funciona si tu universidad o institución está suscrita a Scopus.
- **Acceso a internet** a `api.elsevier.com`, `api.crossref.org`, `api.openalex.org` y `api.semanticscholar.org`.

## 🚀 Instalación

### Claude (web o escritorio)

1. Descarga `scopus-literature-review.zip` desde la sección [**Releases**](../../releases).
2. En Claude, entra a la sección **Skills** de la configuración y sube el archivo `.zip`.
3. Si usas Claude en la web, agrega los dominios de la sección [Requisitos](#-requisitos) en **Configuración → Capacidades**.

### Claude Code

```bash
git clone https://github.com/CarlosRaul04/scopus-literature-review.git
cp -r scopus-literature-review/scopus-literature-review ~/.claude/skills/
```

En Windows, copia la carpeta `scopus-literature-review\scopus-literature-review` a `%USERPROFILE%\.claude\skills\`.

### Otros agentes

Cualquier agente compatible con el formato `SKILL.md` puede usarla: copia la carpeta interna `scopus-literature-review/` donde tu agente busque sus skills.

## 💬 Uso

Después de instalarla, pídele a Claude lo que necesites. La primera vez te pedirá tu clave de API.

**Ejemplos de pedidos:**

- *«Busca en Scopus estudios sobre telemedicina en atención primaria desde 2021 y dame los 20 más citados.»*
- *«¿En qué revistas Q3 o Q4 se publica sobre accesibilidad cognitiva? Quiero elegir dónde enviar mi artículo.»*
- *«Hazme la búsqueda para una revisión sistemática sobre IA generativa en evaluación universitaria, con los números para el diagrama PRISMA.»*
- *«Dame el cuartil de Computers in Human Behavior.»*

**Ejemplo de lo que entrega** (métricas de una revista):

```
Computers in Human Behavior — Elsevier Ltd
  ISSN 0747-5632 · source-id 19419
  CiteScore 22.6 (2025) · SJR 3.072 (2025) · SNIP 3.286
  Q1  Arts and Humanities (miscellaneous)  (percentil 99)
  Q1  Psychology (all)                     (percentil 97)
  Q1  Human-Computer Interaction           (percentil 96)
```

> 🔐 **Tu clave es privada.** La skill le indica al agente que la use solo durante la sesión y que nunca la escriba en archivos. No la subas a GitHub ni la compartas.

## 🛠 Comandos

Claude usa estos comandos por ti, pero también puedes correrlos tú mismo desde la carpeta de la skill:

```bash
export SCOPUS_API_KEY="tu_clave"          # En PowerShell: $env:SCOPUS_API_KEY = "tu_clave"
```

| Comando | Qué hace | Ejemplo |
|---|---|---|
| `check` | Verifica la clave y muestra la cuota semanal | `python scripts/scopus.py check` |
| `search` | Busca en Scopus y guarda los resultados | `python scripts/scopus.py search 'TITLE-ABS-KEY(...)' --max 100 --out r.json` |
| `enrich` | Agrega cuartil, autores completos, páginas, resumen y enlace abierto | `python scripts/scopus.py enrich r.json` |
| `filter` | Filtra por cuartil, año, tipo, citas o resumen | `python scripts/scopus.py filter r_enriched.json --quartiles Q1,Q2 --journals-only` |
| `export` | Exporta a CSV (Excel) o Markdown | `python scripts/scopus.py export r_enriched.json --format csv` |
| `cite` | Referencias en APA 7 o BibTeX | `python scripts/scopus.py cite --file r_enriched.json --style bibtex` |
| `journal` | Métricas y cuartil de una revista | `python scripts/scopus.py journal 0747-5632` |
| `merge` | Une varias búsquedas y quita duplicados | `python scripts/scopus.py merge a.json b.json --out todos.json` |
| `summary` | Agrupa por revista, año o cuartil | `python scripts/scopus.py summary todos.json --by journal` |
| `abstract` | Resumen de un artículo | `python scripts/scopus.py abstract 10.1016/j.chb.2020.106000` |

Usa `python scripts/scopus.py <comando> -h` para ver todas las opciones.

**En Windows (PowerShell):** las comillas dobles dentro de la consulta se pierden. Guarda la consulta en un archivo y usa `--query-file`:

```powershell
'TITLE-ABS-KEY("digital literacy") AND PUBYEAR > 2020' | Out-File -Encoding utf8 consulta.txt
python scripts\scopus.py search --query-file consulta.txt --max 50 --out r.json
```

**Variables opcionales:**

| Variable | Para qué sirve |
|---|---|
| `SCOPUS_INSTTOKEN` | Token institucional: trae todos los autores y el resumen desde Scopus |
| `CONTACT_EMAIL` | Tu correo, para el acceso preferente de Crossref y OpenAlex y para usar Unpaywall (`--oa`) |
| `S2_API_KEY` | Clave de Semantic Scholar, para que las consultas no esperen tanto |
| `SCOPUS_CACHE_DIR` | Carpeta donde se guardan las respuestas para no repetir consultas |

## 🔍 Cómo funciona

```
Scopus Search ──► resultados ──► Serial Title (CiteScore, SJR, SNIP) ──► cuartil por área
                       │
                       ├──► Crossref ──► autores, páginas, datos para la cita
                       └──► resumen: Scopus → Crossref → OpenAlex → Semantic Scholar
```

| Fuente | Qué aporta | ¿Necesita clave? |
|---|---|---|
| **Scopus** (Elsevier) | Búsqueda, citas recibidas, métricas de revistas | Sí |
| **Crossref** | Autores completos, volumen, páginas, datos para APA y BibTeX | No |
| **OpenAlex** | Resúmenes y enlaces de acceso abierto | No |
| **Semantic Scholar** | Resúmenes | No (opcional) |
| **Unpaywall** | PDF de acceso abierto (`--oa`) | No (pide un correo) |

Más detalle en la carpeta [`references/`](scopus-literature-review/references): sintaxis de búsqueda, métricas, flujos de trabajo y errores comunes.

## ⚠️ Limitaciones

- **Algunos resúmenes no se pueden obtener.** Elsevier, Springer y otras editoriales no permiten compartirlos en fuentes abiertas. La skill lo indica, y el agente puede leer el resumen en la página del DOI.
- **El cuartil es el de CiteScore (Scopus).** Puede no coincidir con el de SCImago (SJR) o el de JCR (Clarivate). Si tu institución exige uno de esos, confírmalo en su sitio.
- **Solo cubre Scopus.** Una revisión sistemática suele necesitar también otras bases (Web of Science, PubMed, etc.).
- **Títulos en APA.** Las citas dejan el título como lo registró la editorial. APA 7 lo pide en minúscula de oración: revísalo antes de entregar.
- **Límites de la clave estándar:** 25 resultados por página, hasta 5000 por consulta y unas 20 000 consultas por semana.

## ❓ Preguntas frecuentes

<details>
<summary><b>Me sale «HTTP 401» o «HTTP 403»</b></summary>

401 significa que la clave está mal copiada. 403 suele significar que tu institución no está suscrita a Scopus o que estás fuera de su red: prueba conectado a la red de la universidad o con su VPN. Más casos en [`troubleshooting.md`](scopus-literature-review/references/troubleshooting.md).
</details>

<details>
<summary><b>Me sale «No se pudo conectar»</b></summary>

El entorno donde corre el agente no tiene permiso para salir a esos sitios. En Claude web, agrega los dominios en **Configuración → Capacidades**. También puedes correr el script en tu computadora.
</details>

<details>
<summary><b>¿Por qué una conferencia sale con cuartil?</b></summary>

Porque Scopus le da cuartil a la serie donde se publican las actas (por ejemplo, *Lecture Notes in Computer Science*). La skill lo marca en `quartile_note`. Si solo quieres revistas, usa `filter --journals-only`.
</details>

<details>
<summary><b>¿Puedo usarla sin Claude?</b></summary>

Sí. El script `scripts/scopus.py` funciona solo desde la terminal.
</details>

## 🧪 Pruebas

```bash
python -m unittest discover -s tests -v
```

Las pruebas no necesitan internet ni clave: simulan las respuestas de las APIs. La skill también se probó con la API real de Scopus (clave estándar, sin token institucional) en noviembre de 2026.

## 📁 Estructura

```
scopus-literature-review/          ← la skill (lo que se instala)
├── SKILL.md                       instrucciones para el agente
├── scripts/scopus.py              la herramienta
└── references/                    guías de apoyo
    ├── query-syntax.md            cómo escribir búsquedas
    ├── metrics.md                 CiteScore, SJR, cuartiles
    ├── workflow.md                antecedentes, elegir revista, PRISMA
    ├── troubleshooting.md         errores comunes
    └── apis.md                    detalles técnicos de cada API
tests/                             pruebas automáticas
```

## 🤝 Contribuir

Los reportes de errores y las mejoras son bienvenidos. Abre un *issue* o un *pull request*, y si cambias el script, agrega una prueba en `tests/`.

## 📄 Licencia y aviso

[MIT](LICENSE). Proyecto independiente, sin relación con Elsevier, Scopus, Crossref, OpenAlex, Semantic Scholar ni SCImago. Usa los datos según los términos de uso de las APIs de Elsevier ([dev.elsevier.com](https://dev.elsevier.com)): son para tu investigación, no para redistribuir volcados de registros de Scopus.

---

## 🌎 English

**A Claude skill for Scopus-based literature reviews: search papers, get each journal's quartile per subject area, fill in abstracts and authors, and cite in APA 7 or BibTeX, without making up data.**

### What it does

Ask Claude in plain language, for example *"Find papers since 2020 on web accessibility for people with dyslexia, only in Q1–Q2 journals, with a two-line summary and APA references"*. Claude builds the Scopus query, runs the search, computes quartiles, fills in metadata and abstracts, filters, and returns a table, a reference list and a search log.

### Why this one

- **Quartile per subject area** from the CiteScore percentile, using the official year (not the provisional Tracker).
- **Journals vs. book series:** series such as *Lecture Notes in Computer Science* have a Scopus quartile too; the skill flags them and can filter them out.
- **Abstracts from several sources** (Scopus, Crossref, OpenAlex, Semantic Scholar), with the source recorded and a clear note when the publisher withholds it.
- **No made-up data:** missing fields say "not found" and why; citations come from Crossref metadata.
- **Reproducible:** every query is logged with date and hit count (PRISMA-friendly); `merge` removes duplicates across searches.
- **Zero dependencies:** one standard-library Python script; works on Windows, macOS, Linux and sandboxed cloud environments.

### Install

- **Claude apps:** download `scopus-literature-review.zip` from [Releases](../../releases) and upload it in the **Skills** section of Claude's settings.
- **Claude Code:** copy the inner `scopus-literature-review/` folder to `~/.claude/skills/`.
- **Other `SKILL.md`-compatible agents:** copy the same folder to your agent's skills directory.

You need Python 3.10+ and an Elsevier API key from [dev.elsevier.com](https://dev.elsevier.com), which usually requires an institutional Scopus subscription.

### Language

Instructions and messages are in Spanish; the agent replies in the user's language, so it works in English too.

### Limitations

Some publishers (e.g. Elsevier, Springer) don't allow their abstracts to be shared through open sources. Quartiles are CiteScore-based and may differ from SCImago (SJR) or JCR quartiles. Only Scopus is covered. APA titles keep the publisher's capitalization and should be converted to sentence case.

MIT licensed. Not affiliated with Elsevier.
