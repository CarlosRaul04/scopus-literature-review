#!/usr/bin/env python3
"""
scopus.py — Búsqueda en Scopus, métricas de revistas (CiteScore, cuartil, SJR, SNIP),
resúmenes de respaldo (Crossref / Semantic Scholar) y citas APA 7 / BibTeX.

Solo usa la librería estándar de Python 3.8+.

Variables de entorno:
  SCOPUS_API_KEY      (obligatoria) clave de https://dev.elsevier.com
  SCOPUS_INSTTOKEN    (opcional) token institucional: habilita view=COMPLETE (todos los autores y resumen)
  CONTACT_EMAIL       (opcional) correo para el "polite pool" de Crossref y para Unpaywall
  S2_API_KEY          (opcional) clave de Semantic Scholar (sube el límite de llamadas)
  SCOPUS_CACHE_DIR    (opcional) carpeta de caché; por defecto ~/.cache/scopus-literature-review

Comandos (python3 scopus.py <comando> -h para ver opciones):
  check                      Verifica la clave y muestra la cuota restante
  search  QUERY              Busca en Scopus y guarda los resultados (JSON)
  journal ISSN [ISSN ...]    Métricas de revista: CiteScore, percentil y cuartil por área, SJR, SNIP
  enrich  ARCHIVO.json       Agrega cuartiles, autores completos, resumen, páginas y PDF abierto
  filter  ARCHIVO.json       Filtra por cuartil, año, tipo, citas o resumen disponible
  export  ARCHIVO.json       Exporta a CSV o Markdown
  merge   A.json B.json …    Une búsquedas y elimina duplicados (DOI → EID → título)
  summary ARCHIVO.json       Agrupa por revista, año, cuartil o tipo de documento
  cite    DOI [DOI ...]      Cita en APA 7 o BibTeX desde Crossref
  abstract DOI               Resumen de un artículo (Crossref → Semantic Scholar)
"""
import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ELSEVIER = "https://api.elsevier.com/content"
CROSSREF = "https://api.crossref.org/works/"
S2 = "https://api.semanticscholar.org/graph/v1/paper/DOI:"
UNPAYWALL = "https://api.unpaywall.org/v2/"
OPENALEX = "https://api.openalex.org/works/doi:"
UA = "scopus-literature-review/1.0"
NOT_FOUND = "no aparece"

LAST_RATE = {}  # últimos encabezados de cuota de Elsevier
SCOPUS_ABSTRACT_OK = [True]  # se apaga tras el primer 401/403 de Abstract Retrieval


# ───────────────────────────── utilidades ─────────────────────────────

def eprint(*a):
    print(*a, file=sys.stderr)


def as_list(x):
    """Elsevier devuelve a veces un objeto y a veces una lista: normalizar."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def norm_issn(s):
    """'27637719' o '2763-7719' → '2763-7719'. Devuelve None si no es un ISSN."""
    if not s:
        return None
    d = re.sub(r"[^0-9Xx]", "", str(s)).upper()
    return f"{d[:4]}-{d[4:]}" if len(d) == 8 else None


def norm_doi(s):
    if not s:
        return None
    s = s.strip()
    s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", s, flags=re.I)
    return s or None


def strip_tags(t):
    if not t:
        return None
    t = re.sub(r"<(jats:)?title>.*?</(jats:)?title>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[\u00ad\u200b\u200c\u200d\ufeff]", "", html.unescape(t))
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(Abstract|Resumen|Summary)\s*[:.]\s*", "", t, flags=re.I)
    t = re.sub(r"^(Abstract|ABSTRACT)\s+(?=[A-Z])", "", t)
    return t or None


def quartile(percentile):
    p = float(percentile)
    return "Q1" if p >= 75 else "Q2" if p >= 50 else "Q3" if p >= 25 else "Q4"


def cache_dir():
    d = os.environ.get("SCOPUS_CACHE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "scopus-literature-review")
    os.makedirs(d, exist_ok=True)
    return d


def cache_get(kind, key, max_age_days=None):
    path = os.path.join(cache_dir(), kind + "_" + hashlib.sha1(key.encode()).hexdigest() + ".json")
    if not os.path.exists(path):
        return None
    if max_age_days is not None and time.time() - os.path.getmtime(path) > max_age_days * 86400:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def cache_put(kind, key, value):
    path = os.path.join(cache_dir(), kind + "_" + hashlib.sha1(key.encode()).hexdigest() + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)


class ApiError(Exception):
    pass


def http_get(url, headers=None, tries=4, base_wait=2.0):
    """GET con reintentos ante 429/5xx. Devuelve el JSON o None si 404."""
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=40) as r:
                if "elsevier.com" in url:
                    for k in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
                        if r.headers.get(k):
                            LAST_RATE[k] = r.headers.get(k)
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                wait = base_wait * (2 ** i)
                ra = e.headers.get("Retry-After") if e.headers else None
                if ra and ra.isdigit():
                    wait = max(wait, int(ra))
                eprint(f"  HTTP {e.code}; reintentando en {wait:.0f} s…")
                time.sleep(wait)
                continue
            raise ApiError(explain_http(e.code, body, url))
        except urllib.error.URLError as e:
            if i < tries - 1:
                time.sleep(base_wait * (2 ** i))
                continue
            raise ApiError(f"No se pudo conectar con {urllib.parse.urlparse(url).netloc}: {e.reason}. "
                           "Si es un entorno con lista de dominios permitidos, hay que habilitar el dominio "
                           "o ejecutar el script en la computadora del usuario.")
    return None


def explain_http(code, body, url):
    msg = ""
    try:
        j = json.loads(body)
        st = (j.get("service-error") or {}).get("status") or {}
        msg = st.get("statusText") or j.get("error-response", {}).get("error-message") or j.get("message") or ""
    except ValueError:
        msg = body[:300]
    host = urllib.parse.urlparse(url).netloc
    hints = {
        400: "consulta mal formada (revisar paréntesis, comillas y nombres de campo)",
        401: "clave inválida o no enviada (revisar SCOPUS_API_KEY)",
        403: "la clave no tiene permiso para este recurso (puede requerir token institucional o red de la institución)",
        429: "cuota o límite de velocidad excedido",
    }
    return f"HTTP {code} en {host}: {hints.get(code, 'error del servicio')}. {msg}".strip()


def els_headers():
    key = os.environ.get("SCOPUS_API_KEY")
    if not key:
        raise ApiError("Falta la variable de entorno SCOPUS_API_KEY. "
                       "Pídele la clave al usuario y expórtala solo para esta sesión.")
    h = {"X-ELS-APIKey": key}
    tok = os.environ.get("SCOPUS_INSTTOKEN")
    if tok:
        h["X-ELS-Insttoken"] = tok
    return h


def load_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["records"] if isinstance(data, dict) and "records" in data else data


def save_json(path, records, meta=None):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta or {}, "records": records}, f, ensure_ascii=False, indent=1)


# ───────────────────────────── check ─────────────────────────────

def cmd_check(args):
    h = els_headers()
    url = f"{ELSEVIER}/search/scopus?" + urllib.parse.urlencode({"query": "TITLE(test)", "count": 1})
    d = http_get(url, h)
    total = (d or {}).get("search-results", {}).get("opensearch:totalResults")
    print("Scopus Search: OK (resultados de prueba:", total, ")")
    rem = LAST_RATE.get("X-RateLimit-Remaining")
    if rem:
        reset = LAST_RATE.get("X-RateLimit-Reset")
        when = dt.datetime.fromtimestamp(int(reset)).strftime("%Y-%m-%d %H:%M") if reset and reset.isdigit() else "?"
        print(f"Cuota semanal restante: {rem} de {LAST_RATE.get('X-RateLimit-Limit', '?')} (se renueva: {when})")
    try:
        j = http_get(f"{ELSEVIER}/serial/title/issn/0028-0836?view=CITESCORE", h)
        print("Serial Title (métricas de revistas): OK" if j else "Serial Title: sin respuesta")
    except ApiError as e:
        print("Serial Title: NO disponible →", e)
    print("Token institucional:", "sí" if os.environ.get("SCOPUS_INSTTOKEN") else
          "no (resúmenes y lista completa de autores se completan con Crossref)")


# ───────────────────────────── search ─────────────────────────────

def parse_entry(e):
    affs = as_list(e.get("affiliation"))
    authors = []
    for a in as_list(e.get("author")):  # solo en view=COMPLETE
        n = a.get("authname") or " ".join(x for x in (a.get("surname"), a.get("given-name")) if x)
        if n:
            authors.append(n)
    sid = e.get("dc:identifier") or ""
    return {
        "title": e.get("dc:title"),
        "first_author": e.get("dc:creator"),
        "authors_scopus": authors or None,
        "journal": e.get("prism:publicationName"),
        "issn": norm_issn(e.get("prism:issn")),
        "eissn": norm_issn(e.get("prism:eIssn")),
        "source_id": e.get("source-id"),
        "volume": e.get("prism:volume"),
        "issue": e.get("prism:issueIdentifier"),
        "pages": e.get("prism:pageRange"),
        "article_number": e.get("article-number"),
        "date": e.get("prism:coverDate"),
        "year": int(e["prism:coverDate"][:4]) if (e.get("prism:coverDate") or "")[:4].isdigit() else None,
        "doi": norm_doi(e.get("prism:doi")),
        "eid": e.get("eid"),
        "scopus_id": sid.replace("SCOPUS_ID:", "") or None,
        "cited_by": int(e["citedby-count"]) if str(e.get("citedby-count", "")).isdigit() else None,
        "doctype": e.get("subtypeDescription"),
        "source_type": e.get("prism:aggregationType"),
        "open_access": str(e.get("openaccessFlag")).lower() == "true" or str(e.get("openaccess")) == "1",
        "affiliations": sorted({a.get("affilname") for a in affs if a.get("affilname")}) or None,
        "countries": sorted({a.get("affiliation-country") for a in affs if a.get("affiliation-country")}) or None,
        "keywords": e.get("authkeywords"),
        "abstract": strip_tags(e.get("dc:description")),
        "abstract_source": "Scopus" if e.get("dc:description") else None,
        "scopus_url": next((l.get("@href") for l in as_list(e.get("link")) if l.get("@ref") == "scopus"), None),
    }


def cmd_search(args):
    if args.query_file:
        with open(args.query_file, encoding="utf-8-sig") as f:
            args.query = " ".join(f.read().split())
    if not args.query:
        raise ApiError("Falta la consulta: pásala entre comillas o con --query-file archivo.txt")
    h = els_headers()
    view = "COMPLETE" if os.environ.get("SCOPUS_INSTTOKEN") and not args.standard else "STANDARD"
    limit = min(args.max, 5000)
    if args.max > 5000:
        eprint("Aviso: Scopus Search entrega como máximo 5000 resultados por consulta; acota la búsqueda.")
    out, total, start = [], None, 0
    while start < limit:
        params = {"query": args.query, "count": min(25, limit - start), "start": start,
                  "sort": args.sort, "view": view}
        d = http_get(f"{ELSEVIER}/search/scopus?" + urllib.parse.urlencode(params), h)
        sr = (d or {}).get("search-results", {})
        if total is None:
            total = int(sr.get("opensearch:totalResults") or 0)
            eprint(f"Resultados totales en Scopus: {total}")
            limit = min(limit, total)
        entries = [e for e in as_list(sr.get("entry")) if "error" not in e]
        if not entries:
            break
        out.extend(parse_entry(e) for e in entries)
        start += len(entries)
        time.sleep(0.15)
    meta = {"query": args.query, "sort": args.sort, "view": view, "total_in_scopus": total,
            "retrieved": len(out), "date": dt.datetime.now().isoformat(timespec="seconds")}
    save_json(args.out, out, meta)
    log_search(args.out, meta)
    eprint(f"Guardados {len(out)} registros en {args.out}")
    if args.show:
        for r in out[: args.show]:
            print(f"- {r['year']} | {r['title']} | {r['journal']} | citas: {r['cited_by']} | doi: {r['doi']}")


def log_search(out_path, meta):
    """Registro reproducible de búsquedas (útil para PRISMA)."""
    log = os.path.join(os.path.dirname(os.path.abspath(out_path)), "search_log.csv")
    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "database", "query", "sort", "total_in_scopus", "retrieved", "file"])
        w.writerow([meta["date"], "Scopus", meta["query"], meta["sort"], meta["total_in_scopus"],
                    meta["retrieved"], os.path.basename(out_path)])


# ───────────────────────────── journal ─────────────────────────────

def journal_metrics(issn, refresh=False):
    """Métricas de una revista por ISSN. Usa caché de 30 días."""
    issn = norm_issn(issn)
    if not issn:
        return None
    if not refresh:
        c = cache_get("journal", issn, max_age_days=30)
        if c is not None:
            return c or None
    d = http_get(f"{ELSEVIER}/serial/title/issn/{issn}?view=CITESCORE", els_headers())
    entries = as_list((d or {}).get("serial-metadata-response", {}).get("entry"))
    if not entries or "error" in entries[0]:
        cache_put("journal", issn, {})
        return None
    e = entries[0]
    areas = {str(a.get("@code")): a.get("$") for a in as_list(e.get("subject-area"))}
    info = e.get("citeScoreYearInfoList") or {}
    cur_year = str(info.get("citeScoreCurrentMetricYear") or "")
    years = as_list(info.get("citeScoreYearInfo"))
    # Año oficial: el que coincide con citeScoreCurrentMetricYear y está "Complete" (no el tracker en curso)
    chosen = next((y for y in years if str(y.get("@year")) == cur_year), None) or \
        next((y for y in years if str(y.get("@status", "")).lower() == "complete"), None)
    ranks = []
    if chosen:
        for il in as_list(chosen.get("citeScoreInformationList")):
            for ci in as_list(il.get("citeScoreInfo")):
                if ci.get("docType") not in (None, "all"):
                    continue
                for r in as_list(ci.get("citeScoreSubjectRank")):
                    try:
                        p = float(r.get("percentile"))
                    except (TypeError, ValueError):
                        continue
                    code = str(r.get("subjectCode"))
                    ranks.append({"area_code": code, "area": areas.get(code, code), "percentile": p,
                                  "rank": r.get("rank"), "quartile": quartile(p)})
    sjr = as_list((e.get("SJRList") or {}).get("SJR"))
    snip = as_list((e.get("SNIPList") or {}).get("SNIP"))
    res = {
        "issn_query": issn,
        "title": e.get("dc:title"),
        "publisher": e.get("dc:publisher"),
        "source_id": e.get("source-id"),
        "issn": norm_issn(e.get("prism:issn")),
        "eissn": norm_issn(e.get("prism:eIssn")),
        "open_access_journal": str(e.get("openaccess")) == "1" if e.get("openaccess") is not None else None,
        "citescore": float(info["citeScoreCurrentMetric"]) if info.get("citeScoreCurrentMetric") else None,
        "citescore_year": int(cur_year) if cur_year.isdigit() else None,
        "citescore_tracker": float(info["citeScoreTracker"]) if info.get("citeScoreTracker") else None,
        "sjr": float(sjr[0]["$"]) if sjr and sjr[0].get("$") else None,
        "sjr_year": int(sjr[0]["@year"]) if sjr and str(sjr[0].get("@year", "")).isdigit() else None,
        "snip": float(snip[0]["$"]) if snip and snip[0].get("$") else None,
        "ranks": sorted(ranks, key=lambda r: -r["percentile"]),
        "best_quartile": min((r["quartile"] for r in ranks), default=None),
        "scopus_url": next((l.get("@href") for l in as_list(e.get("link")) if l.get("@ref") == "scopus-source"), None),
    }
    cache_put("journal", issn, res)
    return res


def cmd_journal(args):
    rows = []
    for i in args.issn:
        try:
            m = journal_metrics(i, refresh=args.refresh)
        except ApiError as e:
            eprint(f"{i}: {e}")
            continue
        if not m:
            print(f"{i}: {NOT_FOUND} en Scopus (ISSN incorrecto, revista no indexada o descontinuada)")
            continue
        rows.append(m)
        if args.json:
            continue
        print(f"\n{m['title']} — {m['publisher'] or ''}")
        print(f"  ISSN {m['issn'] or '-'} · eISSN {m['eissn'] or '-'} · source-id {m['source_id']}")
        print(f"  CiteScore {m['citescore']} ({m['citescore_year']}) · tracker {m['citescore_tracker']} · "
              f"SJR {m['sjr']} ({m['sjr_year']}) · SNIP {m['snip']}")
        if not m["ranks"]:
            print("  Sin percentiles de CiteScore (revista sin CiteScore aún o sin datos)")
        for r in m["ranks"]:
            print(f"  {r['quartile']}  {r['area']}  (percentil {r['percentile']:.0f}, puesto {r['rank']})")
        print(f"  Mejor cuartil (CiteScore): {m['best_quartile'] or NOT_FOUND}")
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))


# ───────────────────────────── Crossref / S2 / Unpaywall ─────────────────────────────

def crossref(doi):
    doi = norm_doi(doi)
    if not doi:
        return None
    c = cache_get("crossref", doi.lower())
    if c is not None:
        return c or None
    q = ""
    if os.environ.get("CONTACT_EMAIL"):
        q = "?" + urllib.parse.urlencode({"mailto": os.environ["CONTACT_EMAIL"]})
    d = http_get(CROSSREF + urllib.parse.quote(doi) + q)
    msg = (d or {}).get("message") or {}
    cache_put("crossref", doi.lower(), msg)
    time.sleep(0.1)
    return msg or None


def semantic_scholar(doi):
    doi = norm_doi(doi)
    c = cache_get("s2", doi.lower())
    if c is not None:
        return c or None
    h = {}
    if os.environ.get("S2_API_KEY"):
        h["x-api-key"] = os.environ["S2_API_KEY"]
    else:
        time.sleep(3.5)  # sin clave el límite es estricto
    try:
        d = http_get(S2 + urllib.parse.quote(doi) +
                     "?fields=title,abstract,year,authors,openAccessPdf,tldr", h, base_wait=5)
    except ApiError as e:
        eprint(f"  Semantic Scholar: {e}")
        return None
    cache_put("s2", doi.lower(), d or {})
    return d


def unpaywall(doi):
    email = os.environ.get("CONTACT_EMAIL")
    if not email:
        return None
    doi = norm_doi(doi)
    c = cache_get("unpaywall", doi.lower(), max_age_days=60)
    if c is not None:
        return c or None
    try:
        d = http_get(UNPAYWALL + urllib.parse.quote(doi) + "?" + urllib.parse.urlencode({"email": email}))
    except ApiError:
        d = None
    cache_put("unpaywall", doi.lower(), d or {})
    return d


def cr_authors(msg):
    out = []
    for a in msg.get("author", []) or []:
        if a.get("family"):
            out.append({"family": a["family"], "given": a.get("given", ""), "orcid": a.get("ORCID")})
        elif a.get("name"):
            out.append({"family": a["name"], "given": "", "orcid": None, "corporate": True})
    return out


def cr_year(msg):
    # Artículos: año del número impreso (APA 7 usa la versión final). Capítulos y otros: fecha de publicación (issued).
    order = ("published-print", "issued", "published-online", "published") if msg.get("type") == "journal-article" \
        else ("issued", "published-online", "published-print", "published")
    for k in order:
        parts = ((msg.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            return int(parts[0])
    return None


def scopus_abstract(eid=None, doi=None):
    """Resumen desde Scopus Abstract Retrieval. Requiere derecho (red institucional o token);
    si la clave no lo tiene, se desactiva para el resto de la ejecución."""
    if not SCOPUS_ABSTRACT_OK[0] or not (eid or doi):
        return None
    key = eid or doi.lower()
    c = cache_get("scopus_abs", key)
    if c is not None:
        return c.get("abstract")
    url = f"{ELSEVIER}/abstract/eid/{eid}" if eid else f"{ELSEVIER}/abstract/doi/{urllib.parse.quote(doi)}"
    try:
        d = http_get(url + "?view=META_ABS", els_headers(), tries=2)
    except ApiError as e:
        if "HTTP 401" in str(e) or "HTTP 403" in str(e):
            SCOPUS_ABSTRACT_OK[0] = False
            eprint("  Scopus Abstract Retrieval no disponible con esta clave (se usan fuentes abiertas).")
        return None
    desc = (((d or {}).get("abstracts-retrieval-response") or {}).get("coredata") or {}).get("dc:description")
    if isinstance(desc, dict):
        desc = desc.get("$") or desc.get("abstract")
    ab = strip_tags(desc) if isinstance(desc, str) else None
    if ab:
        ab = re.sub(r"\s*©.*$", "", ab).strip() or None  # quitar la línea de copyright final
    cache_put("scopus_abs", key, {"abstract": ab})
    return ab


def openalex(doi):
    doi = norm_doi(doi)
    c = cache_get("openalex", doi.lower())
    if c is not None:
        return c or None
    q = "?" + urllib.parse.urlencode({"mailto": os.environ["CONTACT_EMAIL"]}) if os.environ.get("CONTACT_EMAIL") else ""
    try:
        d = http_get(OPENALEX + urllib.parse.quote(doi) + q)
    except ApiError as e:
        eprint(f"  OpenAlex: {e}")
        return None
    cache_put("openalex", doi.lower(), d or {})
    return d


def openalex_abstract(w):
    inv = (w or {}).get("abstract_inverted_index")
    if not inv:
        return None
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return strip_tags(" ".join(pos[i] for i in sorted(pos)))


def get_abstract(doi, record=None):
    """Devuelve (resumen, fuente, nota). Nunca inventa: si no hay, (None, None, motivo)."""
    if record and record.get("abstract") and record.get("abstract_source"):
        return record["abstract"], record["abstract_source"], None
    ab = scopus_abstract((record or {}).get("eid"), doi)
    if ab:
        return ab, "Scopus", None
    if not doi:
        return None, None, "sin DOI"
    ab = strip_tags((crossref(doi) or {}).get("abstract"))
    if ab:
        return ab, "Crossref", None
    ab = openalex_abstract(openalex(doi))
    if ab:
        return ab, "OpenAlex", None
    s = semantic_scholar(doi) or {}
    if s.get("abstract"):
        return s["abstract"].strip(), "Semantic Scholar", None
    disclaimer = str((s.get("openAccessPdf") or {}).get("disclaimer") or "")
    if "elided by the publisher" in disclaimer:
        return None, None, "la editorial no permite compartir el resumen en fuentes abiertas; verlo en la página del DOI"
    return None, None, "no está en Scopus, Crossref, OpenAlex ni Semantic Scholar"


def cmd_abstract(args):
    ab, src, note = get_abstract(args.doi)
    print(f"[{src}] {ab}" if ab else f"{NOT_FOUND} ({note})")


# ───────────────────────────── enrich / filter / export ─────────────────────────────

def cmd_enrich(args):
    recs = load_json(args.file)
    jcache = {}
    n = len(recs)
    for i, r in enumerate(recs, 1):
        eprint(f"[{i}/{n}] {(r.get('title') or '')[:70]}")
        # 1) métricas de la revista (por ISSN impreso o electrónico)
        m = None
        for issn in (r.get("issn"), r.get("eissn")):
            if not issn:
                continue
            if issn not in jcache:
                try:
                    jcache[issn] = journal_metrics(issn)
                except ApiError as e:
                    eprint("  ", e)
                    jcache[issn] = None
            m = jcache[issn]
            if m:
                break
        if m:
            if r.get("source_id") and m.get("source_id") and str(r["source_id"]) != str(m["source_id"]):
                r["journal_check"] = f"source-id distinto: artículo {r['source_id']} vs revista {m['source_id']}"
            r["citescore"] = m["citescore"]
            r["citescore_year"] = m["citescore_year"]
            r["sjr"] = m["sjr"]
            r["quartile_best"] = m["best_quartile"]
            r["quartiles_by_area"] = "; ".join(f"{x['area']}: {x['quartile']}" for x in m["ranks"]) or None
            st = (r.get("source_type") or "").lower()
            if st and st != "journal" and m["best_quartile"]:
                r["quartile_note"] = (f"cuartil de la serie ({r.get('source_type')}), no de una revista: "
                                      "muchas instituciones no lo cuentan como cuartil de revista")
        else:
            r.setdefault("quartile_best", None)
        # 2) Crossref: autores completos, volumen, páginas, resumen
        doi = r.get("doi")
        if doi:
            msg = crossref(doi) or {}
            if msg:
                r["authors"] = cr_authors(msg) or None
                r["volume"] = r.get("volume") or msg.get("volume")
                r["issue"] = r.get("issue") or msg.get("issue")
                r["pages"] = r.get("pages") or msg.get("page")
                r["article_number"] = r.get("article_number") or msg.get("article-number")
                r["publisher"] = msg.get("publisher")
            if not args.no_abstracts:
                ab, src, note = get_abstract(doi, r)
                r["abstract"], r["abstract_source"] = ab, src
                r["abstract_note"] = note
            w = openalex(doi) or {}
            oa = (w.get("open_access") or {}).get("oa_url") or ((w.get("best_oa_location") or {}).get("pdf_url"))
            if args.oa and not oa:
                u = unpaywall(doi) or {}
                loc = u.get("best_oa_location") or {}
                oa = loc.get("url_for_pdf") or loc.get("url")
            r["oa_pdf"] = oa
        r["missing"] = [k for k in ("doi", "abstract", "quartile_best", "authors") if not r.get(k)] or None
    out = args.out or args.file.replace(".json", "_enriched.json")
    save_json(out, recs, {"enriched_from": os.path.basename(args.file),
                          "date": dt.datetime.now().isoformat(timespec="seconds")})
    with_ab = sum(1 for r in recs if r.get("abstract"))
    with_q = sum(1 for r in recs if r.get("quartile_best"))
    series = sum(1 for r in recs if r.get("quartile_note"))
    eprint(f"Listo: {out} · con cuartil {with_q}/{n}" + (f" ({series} de series de libros/actas)" if series else "") +
           f" · con resumen {with_ab}/{n}")
    blocked = sum(1 for r in recs if "editorial" in (r.get("abstract_note") or ""))
    if blocked:
        eprint(f"  {blocked} sin resumen porque la editorial no lo comparte en fuentes abiertas "
               "(se puede leer en la página del DOI).")


def cmd_filter(args):
    recs = load_json(args.file)
    qs = {q.strip().upper() for q in args.quartiles.split(",")} if args.quartiles else None
    out = []
    for r in recs:
        if qs is not None:
            q = r.get("quartile_best")
            if args.any_area and r.get("quartiles_by_area"):
                found = set(re.findall(r"Q[1-4]", r["quartiles_by_area"]))
                if not found & qs:
                    continue
            elif q not in qs:
                continue
        if args.journals_only and (r.get("source_type") or "").lower() != "journal":
            continue
        if args.since and (r.get("year") or 0) < args.since:
            continue
        if args.until and (r.get("year") or 9999) > args.until:
            continue
        if args.doctype and (r.get("doctype") or "").lower() not in [d.lower() for d in args.doctype]:
            continue
        if args.min_citations and (r.get("cited_by") or 0) < args.min_citations:
            continue
        if args.with_abstract and not r.get("abstract"):
            continue
        if args.open_access and not (r.get("open_access") or r.get("oa_pdf")):
            continue
        out.append(r)
    dst = args.out or args.file.replace(".json", "_filtered.json")
    crit = {k: v for k, v in vars(args).items() if k not in ("fn", "cmd", "file", "out") and v}
    save_json(dst, out, {"filtered_from": os.path.basename(args.file), "criteria": crit})
    eprint(f"{len(out)} de {len(recs)} registros cumplen los filtros → {dst}")


def fmt_authors_short(r):
    if r.get("authors"):
        names = [a["family"] + (", " + initials(a["given"]) if a.get("given") else "") for a in r["authors"]]
        return "; ".join(names)
    if r.get("authors_scopus"):
        return "; ".join(r["authors_scopus"])
    return (r.get("first_author") or "") + " et al." if r.get("first_author") else NOT_FOUND


def cmd_export(args):
    recs = load_json(args.file)
    cols = ["year", "title", "authors", "journal", "quartile_best", "citescore", "sjr", "cited_by",
            "doctype", "source_type", "doi", "abstract", "abstract_source", "abstract_note",
            "quartiles_by_area", "quartile_note", "oa_pdf"]
    def val(r, c):
        if c == "authors":
            return fmt_authors_short(r)
        v = r.get(c)
        return NOT_FOUND if v in (None, "", []) else v
    if args.format == "csv":
        dst = args.out or args.file.replace(".json", ".csv")
        with open(dst, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in recs:
                w.writerow([val(r, c) for c in cols])
    else:
        dst = args.out or args.file.replace(".json", ".md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write("| Año | Título | Autores | Revista | Cuartil | Citas | DOI |\n|---|---|---|---|---|---|---|\n")
            for r in recs:
                cells = [val(r, "year"), val(r, "title"), val(r, "authors"), val(r, "journal"),
                         val(r, "quartile_best"), val(r, "cited_by"),
                         f"https://doi.org/{r['doi']}" if r.get("doi") else NOT_FOUND]
                f.write("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |\n")
    eprint(f"Exportado: {dst}")


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def cmd_merge(args):
    """Une varios archivos y elimina duplicados por DOI → EID → título normalizado."""
    seen, out, dups, total = set(), [], 0, 0
    for path in args.files:
        for r in load_json(path):
            total += 1
            keys = [k for k in (("doi:" + r["doi"].lower()) if r.get("doi") else None,
                                ("eid:" + r["eid"]) if r.get("eid") else None,
                                ("t:" + norm_title(r.get("title")) + f":{r.get('year')}") if r.get("title") else None) if k]
            if any(k in seen for k in keys):
                dups += 1
                continue
            seen.update(keys)
            r.setdefault("from_file", os.path.basename(path))
            out.append(r)
    save_json(args.out, out, {"merged_from": [os.path.basename(p) for p in args.files],
                              "total_in": total, "duplicates_removed": dups, "total_out": len(out),
                              "date": dt.datetime.now().isoformat(timespec="seconds")})
    eprint(f"{total} registros leídos · {dups} duplicados eliminados · {len(out)} únicos → {args.out}")


def cmd_summary(args):
    recs = load_json(args.file)
    groups = {}
    for r in recs:
        k = r.get(args.by)
        k = NOT_FOUND if k in (None, "") else k
        g = groups.setdefault(k, {"n": 0, "cites": 0, "quartile": r.get("quartile_best"),
                                  "citescore": r.get("citescore"), "sjr": r.get("sjr")})
        g["n"] += 1
        g["cites"] += r.get("cited_by") or 0
    order = sorted(groups.items(), key=(lambda kv: str(kv[0])) if args.by == "year" else (lambda kv: -kv[1]["n"]))
    if args.by == "journal":
        print("| Revista | Trabajos | Citas | Mejor cuartil | CiteScore | SJR |\n|---|---|---|---|---|---|")
        for k, g in order[: args.top]:
            print(f"| {k} | {g['n']} | {g['cites']} | {g['quartile'] or NOT_FOUND} | "
                  f"{g['citescore'] if g['citescore'] is not None else NOT_FOUND} | "
                  f"{g['sjr'] if g['sjr'] is not None else NOT_FOUND} |")
    else:
        print(f"| {args.by} | Trabajos | Citas |\n|---|---|---|")
        for k, g in order[: args.top]:
            print(f"| {k} | {g['n']} | {g['cites']} |")
    eprint(f"{len(recs)} registros · {len(groups)} grupos")


# ───────────────────────────── citas ─────────────────────────────

def initials(given):
    parts = re.split(r"[\s]+", given.strip())
    out = []
    for p in parts:
        if not p:
            continue
        if "-" in p:
            out.append("-".join(s[0].upper() + "." for s in p.split("-") if s))
        elif p.endswith(".") and len(p) <= 3:
            out.append(p)
        else:
            out.append(p[0].upper() + ".")
    return " ".join(out)


def apa_author(a):
    if a.get("corporate"):
        return a["family"]
    return a["family"] + (", " + initials(a["given"]) if a.get("given") else "")


def apa(msg, italics=True):
    it = (lambda s: f"*{s}*") if italics else (lambda s: s)
    au = [apa_author(a) for a in cr_authors(msg)]
    if not au:
        authors = ""
    elif len(au) == 1:
        authors = au[0]
    elif len(au) <= 20:
        authors = ", ".join(au[:-1]) + ", & " + au[-1]
    else:
        authors = ", ".join(au[:19]) + ", . . . " + au[-1]
    year = cr_year(msg) or "s.f."
    title = strip_tags((msg.get("title") or [""])[0]) or ""
    cts = [strip_tags(c) for c in (msg.get("container-title") or []) if c]
    # Crossref pone en capítulos [serie, libro]; para APA se usa el título del libro (el último)
    cont = (cts[-1] if msg.get("type") in ("book-chapter", "proceedings-article") else cts[0]) if cts else ""
    vol, iss = msg.get("volume"), msg.get("issue")
    pages = (msg.get("page") or "").replace("-", "–")
    artno = msg.get("article-number")
    doi = msg.get("DOI")
    typ = msg.get("type", "")
    head = f"{authors} ({year}). " if authors else ""
    end = lambda s: s if s.rstrip().endswith((".", "?", "!")) else s + "."  # no duplicar puntuación
    title = title.strip()
    if typ == "journal-article" or (cont and vol):
        src = it(cont)
        if vol:
            src += ", " + it(vol)
        if iss:
            src += f"({iss})"
        if pages:
            src += f", {pages}"
        elif artno:
            src += f", Artículo {artno}"
        body = f"{head}{end(title)} {src}."
    elif typ in ("proceedings-article", "book-chapter"):
        body = f"{head}{end(title)} En {it(cont)}" + (f" (pp. {pages})" if pages else "") + \
               (f". {msg.get('publisher')}." if msg.get("publisher") else ".")
    else:
        body = f"{head}{it(end(title))}" + (f" {msg.get('publisher')}." if msg.get("publisher") else "")
    return body + (f" https://doi.org/{doi}" if doi else "")


def bibtex(msg):
    au = cr_authors(msg)
    year = cr_year(msg) or ""
    first = re.sub(r"[^A-Za-z]", "", (au[0]["family"] if au else "anon")).lower() or "anon"
    word = next((w for w in re.findall(r"[A-Za-z]+", (msg.get("title") or [""])[0]) if len(w) > 3), "x").lower()
    key = f"{first}{year}{word}"
    typ = {"journal-article": "article", "proceedings-article": "inproceedings",
           "book-chapter": "incollection", "book": "book"}.get(msg.get("type"), "misc")
    esc = lambda s: re.sub(r"([&%$#_])", r"\\\1", strip_tags(s) or "")
    fields = [("title", "{" + esc((msg.get("title") or [""])[0]) + "}"),
              ("author", " and ".join(
                  "{" + a["family"] + "}" if a.get("corporate") else f"{a['family']}, {a['given']}".strip(", ")
                  for a in au)),
              ("journal" if typ == "article" else "booktitle",
               esc((msg.get("container-title") or [""])[0 if typ == "article" else -1])),
              ("series", esc(msg["container-title"][0]) if typ != "article" and len(msg.get("container-title") or []) > 1 else None),
              ("year", str(year)), ("volume", msg.get("volume")), ("number", msg.get("issue")),
              ("pages", (msg.get("page") or "").replace("-", "--")), ("publisher", esc(msg.get("publisher"))),
              ("doi", msg.get("DOI"))]
    body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v)
    return f"@{typ}{{{key},\n{body}\n}}"


def cmd_cite(args):
    dois = list(args.doi)
    if args.file:
        dois += [r["doi"] for r in load_json(args.file) if r.get("doi")]
    out = []
    for d in dois:
        try:
            msg = crossref(d)
        except ApiError as e:
            eprint(f"{d}: {e}")
            continue
        if not msg:
            out.append(f"% {d}: {NOT_FOUND} en Crossref" if args.style == "bibtex" else f"{d}: {NOT_FOUND} en Crossref")
            continue
        out.append(bibtex(msg) if args.style == "bibtex" else apa(msg, italics=not args.plain))
    if args.style == "apa":
        out.sort(key=lambda s: s.lower())
    text = ("\n\n" if args.style == "bibtex" else "\n\n").join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        eprint(f"Guardado: {args.out}")
    else:
        print(text)


# ───────────────────────────── CLI ─────────────────────────────

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("check", help="verificar clave y cuota").set_defaults(fn=cmd_check)

    s = sp.add_parser("search", help="buscar en Scopus")
    s.add_argument("query", nargs="?", help="consulta (o usar --query-file)")
    s.add_argument("--query-file", help="archivo de texto con la consulta (evita problemas de comillas en Windows)")
    s.add_argument("--max", type=int, default=25, help="máximo de registros (≤ 5000)")
    s.add_argument("--sort", default="relevancy",
                   help="relevancy (por defecto), -coverDate (recientes), -citedby-count (más citados)")
    s.add_argument("--out", default="scopus_results.json")
    s.add_argument("--show", type=int, default=10, help="cuántos mostrar en pantalla (0 = ninguno)")
    s.add_argument("--standard", action="store_true", help="forzar view=STANDARD aunque haya token")
    s.set_defaults(fn=cmd_search)

    j = sp.add_parser("journal", help="métricas y cuartil de revistas por ISSN")
    j.add_argument("issn", nargs="+")
    j.add_argument("--json", action="store_true")
    j.add_argument("--refresh", action="store_true", help="ignorar la caché")
    j.set_defaults(fn=cmd_journal)

    e = sp.add_parser("enrich", help="agregar cuartiles, autores, resúmenes")
    e.add_argument("file")
    e.add_argument("--out")
    e.add_argument("--no-abstracts", action="store_true")
    e.add_argument("--oa", action="store_true", help="buscar PDF abierto en Unpaywall (requiere CONTACT_EMAIL)")
    e.set_defaults(fn=cmd_enrich)

    f = sp.add_parser("filter", help="filtrar registros")
    f.add_argument("file")
    f.add_argument("--quartiles", help="p. ej. Q1,Q2 o Q3,Q4 (usa el mejor cuartil)")
    f.add_argument("--any-area", action="store_true", help="aceptar si el cuartil aparece en cualquier área")
    f.add_argument("--journals-only", action="store_true", help="solo revistas (excluye series de libros y actas)")
    f.add_argument("--since", type=int)
    f.add_argument("--until", type=int)
    f.add_argument("--doctype", nargs="+", help='p. ej. Article Review "Conference Paper"')
    f.add_argument("--min-citations", type=int)
    f.add_argument("--with-abstract", action="store_true")
    f.add_argument("--open-access", action="store_true")
    f.add_argument("--out")
    f.set_defaults(fn=cmd_filter)

    x = sp.add_parser("export", help="exportar a CSV o Markdown")
    x.add_argument("file")
    x.add_argument("--format", choices=["csv", "md"], default="csv")
    x.add_argument("--out")
    x.set_defaults(fn=cmd_export)

    mg = sp.add_parser("merge", help="unir archivos y quitar duplicados")
    mg.add_argument("files", nargs="+")
    mg.add_argument("--out", default="merged.json")
    mg.set_defaults(fn=cmd_merge)

    sm = sp.add_parser("summary", help="agrupar por revista, año, cuartil o tipo")
    sm.add_argument("file")
    sm.add_argument("--by", choices=["journal", "year", "quartile_best", "doctype", "source_type"],
                    default="journal")
    sm.add_argument("--top", type=int, default=30)
    sm.set_defaults(fn=cmd_summary)

    c = sp.add_parser("cite", help="citar en APA 7 o BibTeX")
    c.add_argument("doi", nargs="*")
    c.add_argument("--file", help="citar todos los DOI de un archivo de resultados")
    c.add_argument("--style", choices=["apa", "bibtex"], default="apa")
    c.add_argument("--plain", action="store_true", help="APA sin marcas de cursiva")
    c.add_argument("--out")
    c.set_defaults(fn=cmd_cite)

    a = sp.add_parser("abstract", help="resumen de un DOI")
    a.add_argument("doi")
    a.set_defaults(fn=cmd_abstract)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except ApiError as e:
        eprint("ERROR:", e)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
