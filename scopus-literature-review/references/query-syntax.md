# Sintaxis de búsqueda avanzada de Scopus

La API usa la misma sintaxis que la búsqueda avanzada de scopus.com. Si una consulta funciona en la web, funciona en la API.

## Campos más útiles

| Campo | Busca en | Ejemplo |
|---|---|---|
| `TITLE-ABS-KEY()` | Título, resumen y palabras clave (el más usado) | `TITLE-ABS-KEY("digital literacy")` |
| `TITLE()` | Solo título (más preciso, menos resultados) | `TITLE(dyslexia)` |
| `ABS()` | Solo resumen | `ABS("randomized controlled trial")` |
| `KEY()` | Todas las palabras clave | `KEY(telemedicine)` |
| `AUTHKEY()` | Palabras clave del autor | `AUTHKEY(usability)` |
| `INDEXTERMS()` | Términos controlados (MeSH, EMTREE, etc.) | `INDEXTERMS("Attention Deficit Disorder with Hyperactivity")` |
| `ALL()` | Todo el registro, incluso referencias (genera ruido) | `ALL(blockchain)` |
| `AUTH()` | Autor | `AUTH("garcia m")` |
| `AUTHLASTNAME()` · `AUTHFIRST()` | Apellido / inicial | `AUTHLASTNAME(nielsen)` |
| `AU-ID()` | Identificador de autor de Scopus (el más fiable) | `AU-ID(<identificador>)` |
| `AFFIL()` · `AFFILORG()` | Afiliación | `AFFIL("Universidad de Chile")` |
| `AF-ID()` | Identificador de institución | `AF-ID(<identificador>)` |
| `AFFILCOUNTRY()` · `AFFILCITY()` | País / ciudad | `AFFILCOUNTRY(peru)` |
| `SRCTITLE()` | Nombre de la revista (contiene) | `SRCTITLE("human-computer")` |
| `EXACTSRCTITLE()` | Nombre exacto de la revista | `EXACTSRCTITLE("Computers in Human Behavior")` |
| `ISSN()` · `ISBN()` | Revista o libro | `ISSN(0747-5632)` |
| `DOI()` | Un artículo | `DOI(10.1016/j.chb.2020.106000)` |
| `PUBYEAR` | Año | `PUBYEAR > 2019` · `PUBYEAR < 2026` · `PUBYEAR = 2024` |
| `LANGUAGE()` | Idioma del documento | `LANGUAGE(spanish)` |
| `DOCTYPE()` | Tipo de documento | `DOCTYPE(ar)` |
| `SRCTYPE()` | Tipo de fuente | `SRCTYPE(j)` |
| `SUBJAREA()` | Área temática | `SUBJAREA(PSYC)` |
| `OPENACCESS()` | Acceso abierto | `OPENACCESS(1)` |
| `FUND-SPONSOR()` | Financiador | `FUND-SPONSOR("National Science Foundation")` |
| `REF()` | Referencias citadas | `REF("Braun and Clarke")` |

`PUBYEAR > 2019` incluye 2020 en adelante (no incluye 2019). Para un rango: `PUBYEAR > 2019 AND PUBYEAR < 2026` (2020–2025).

## Operadores

| Operador | Uso |
|---|---|
| `AND`, `OR`, `AND NOT` | Lógicos. `AND NOT` va al final de la consulta |
| `"frase exacta"` | Frase con variantes de plural y ortografía aproximada |
| `{frase literal}` | Frase exacta carácter por carácter (incluye signos) |
| `*` | Cero o más caracteres: `educat*` → education, educational, educator |
| `?` | Un carácter: `wom?n` |
| `W/n` | Ambos términos a ≤ n palabras, en cualquier orden: `reading W/3 difficult*` |
| `PRE/n` | El primero precede al segundo a ≤ n palabras |

**Precedencia (trampa frecuente):** Scopus evalúa `OR` antes que `AND`, y `AND NOT` al final. Usa **siempre paréntesis** para que la consulta diga lo que quieres.

## Tipos de documento (`DOCTYPE`)

| Código | Tipo | Código | Tipo |
|---|---|---|---|
| `ar` | Artículo | `re` | Revisión |
| `cp` | Artículo de conferencia | `cr` | Revisión de conferencia |
| `ch` | Capítulo de libro | `bk` | Libro |
| `ed` | Editorial | `le` | Carta |
| `no` | Nota | `sh` | Short survey |
| `dp` | Data paper | `er` | Fe de erratas |
| `tb` | Retractado | | |

En los resultados aparecen como texto (`Article`, `Review`, `Conference Paper`…); usa ese texto con `filter --doctype`.

## Tipos de fuente (`SRCTYPE`)

`j` revista · `p` actas de conferencia · `b` libro · `k` serie de libros · `d` publicación comercial.

## Áreas temáticas (`SUBJAREA`)

| Código | Área | Código | Área |
|---|---|---|---|
| `AGRI` | Ciencias agrícolas y biológicas | `IMMU` | Inmunología y microbiología |
| `ARTS` | Artes y humanidades | `MATE` | Ciencia de materiales |
| `BIOC` | Bioquímica, genética y biología molecular | `MATH` | Matemáticas |
| `BUSI` | Negocios, gestión y contabilidad | `MEDI` | Medicina |
| `CENG` | Ingeniería química | `NEUR` | Neurociencia |
| `CHEM` | Química | `NURS` | Enfermería |
| `COMP` | Ciencias de la computación | `PHAR` | Farmacología, toxicología y farmacia |
| `DECI` | Ciencias de la decisión | `PHYS` | Física y astronomía |
| `DENT` | Odontología | `PSYC` | Psicología |
| `EART` | Ciencias de la Tierra y planetarias | `SOCI` | Ciencias sociales |
| `ECON` | Economía, econometría y finanzas | `VETE` | Veterinaria |
| `ENER` | Energía | `HEAL` | Profesiones de la salud |
| `ENGI` | Ingeniería | `MULT` | Multidisciplinaria |
| `ENVI` | Ciencias ambientales | | |

## Cómo construir una buena consulta

1. Escribe la pregunta en una frase: «¿Qué efecto tiene X en Y en la población Z?»
2. Saca 2–3 conceptos (X, Y, Z). No metas todos los detalles: cada `AND` reduce mucho los resultados.
3. Para cada concepto, junta sinónimos, siglas, variantes británicas/estadounidenses y términos en otros idiomas si buscas literatura regional:
   `(ADHD OR "attention deficit" OR TDAH)`
4. Une conceptos con `AND`, agrega filtros (años, tipo, idioma) al final.
5. Prueba y ajusta mirando los primeros 25 resultados: ¿son pertinentes? Si aparecen temas ajenos, agrega `AND NOT (...)` con cuidado.
6. Guarda cada versión de la consulta (el script lo hace en `search_log.csv`).

## Ejemplos por disciplina

```
# Salud: intervención en población
TITLE-ABS-KEY((telemedicine OR telehealth OR "remote consultation") AND (diabetes) AND ("primary care")) AND PUBYEAR > 2019 AND DOCTYPE(ar)

# Educación: revisión de revisiones
TITLE-ABS-KEY(("generative AI" OR ChatGPT OR "large language model*") AND (assessment OR grading) AND (university OR "higher education")) AND DOCTYPE(re)

# Interacción humano-computador y accesibilidad
TITLE-ABS-KEY((accessib* OR usability) AND (neurodiver* OR ADHD OR dyslexi* OR autis*) AND (web OR app OR interface)) AND SUBJAREA(COMP)

# Ingeniería: proximidad
TITLE-ABS-KEY((concrete W/3 (recycled OR waste)) AND (compressive W/2 strength)) AND SRCTYPE(j)

# Negocios en América Latina, en español
TITLE-ABS-KEY((emprendimiento OR entrepreneurship) AND (mujer* OR women OR female)) AND AFFILCOUNTRY(peru OR colombia OR chile OR mexico)

# Producción de una revista concreta
ISSN(0747-5632) AND TITLE-ABS-KEY(misinformation) AND PUBYEAR > 2021

# Autor por identificador
AU-ID(<identificador>) AND PUBYEAR > 2020
```
