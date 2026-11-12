"""
Pruebas sin red: se reemplaza http_get por respuestas simuladas con la misma
estructura que devuelven Scopus, Crossref y Semantic Scholar.

    python3 -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scopus-literature-review", "scripts"))
import scopus  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def rj(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def rt(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def fake_http_get(url, headers=None, tries=4, base_wait=2.0):
    if "search/scopus" in url:
        if "start=0" in url:
            return fixture("search_page1.json")
        return fixture("search_empty.json")
    if "serial/title/issn/1234-5679" in url:
        return fixture("serial_title.json")
    if "serial/title/issn/" in url:
        return None
    if "api.crossref.org" in url:
        if "10.5555%2Fdemo.001" in url or "10.5555/demo.001" in url:
            return fixture("crossref_with_abstract.json")
        if "10.1000%2Fno-abstract" in url or "10.1000/no-abstract" in url:
            return fixture("crossref_no_abstract.json")
        if "chapter.001" in url:
            return fixture("crossref_chapter.json")
        return None
    if "/content/abstract/" in url:
        return None
    if "api.openalex.org" in url:
        return None
    if "semanticscholar" in url:
        if "chapter.001" in url:
            return {"title": "x", "abstract": None, "openAccessPdf": {
                "disclaimer": "Notice: The following paper fields have been elided by the publisher: {'abstract'}."}}
        return {"title": "x", "abstract": "Resumen desde Semantic Scholar.", "year": 2024}
    return None


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SCOPUS_CACHE_DIR"] = os.path.join(self.tmp, "cache")
        os.environ["SCOPUS_API_KEY"] = "TEST"
        os.environ.pop("SCOPUS_INSTTOKEN", None)
        os.environ["S2_API_KEY"] = "x"  # evita la pausa de 3.5 s en las pruebas
        self._orig = scopus.http_get
        scopus.http_get = fake_http_get

    def tearDown(self):
        scopus.http_get = self._orig

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = scopus.main(list(argv))
        return code, out.getvalue(), err.getvalue()


class TestHelpers(unittest.TestCase):
    def test_quartile_limits(self):
        self.assertEqual(scopus.quartile(99), "Q1")
        self.assertEqual(scopus.quartile(75), "Q1")
        self.assertEqual(scopus.quartile(74.9), "Q2")
        self.assertEqual(scopus.quartile(50), "Q2")
        self.assertEqual(scopus.quartile(25), "Q3")
        self.assertEqual(scopus.quartile(24), "Q4")

    def test_norm_issn_and_doi(self):
        self.assertEqual(scopus.norm_issn("12345679"), "1234-5679")
        self.assertEqual(scopus.norm_issn("0000-000x"), "0000-000X")
        self.assertIsNone(scopus.norm_issn("123"))
        self.assertEqual(scopus.norm_doi("https://doi.org/10.1/ABC"), "10.1/ABC")

    def test_strip_jats(self):
        t = "<jats:title>Abstract</jats:title><jats:p>Texto &amp; más.</jats:p>"
        self.assertEqual(scopus.strip_tags(t), "Texto & más.")

    def test_initials(self):
        self.assertEqual(scopus.initials("Jean-Paul"), "J.-P.")
        self.assertEqual(scopus.initials("María José"), "M. J.")


class TestSearch(Base):
    def test_search_saves_records_and_log(self):
        out = os.path.join(self.tmp, "r.json")
        code, _, err = self.run_cli("search", "TITLE(x)", "--max", "50", "--out", out, "--show", "0")
        self.assertEqual(code, 0, err)
        data = rj(out)
        self.assertEqual(data["meta"]["total_in_scopus"], 2)
        recs = data["records"]
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["issn"], "1234-5679")
        self.assertEqual(recs[0]["year"], 2021)
        self.assertEqual(recs[0]["cited_by"], 7)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "search_log.csv")))

    def test_missing_key(self):
        os.environ.pop("SCOPUS_API_KEY")
        code, _, err = self.run_cli("search", "TITLE(x)", "--out", os.path.join(self.tmp, "r.json"))
        self.assertEqual(code, 1)
        self.assertIn("SCOPUS_API_KEY", err)


class TestJournal(Base):
    def test_uses_official_year_not_tracker(self):
        m = scopus.journal_metrics("12345679")
        self.assertEqual(m["citescore_year"], 2024)
        self.assertEqual(m["citescore"], 1.6)
        # 2025 (tracker en curso) tiene percentil 90; no debe usarse
        self.assertEqual(m["best_quartile"], "Q3")
        areas = {r["area"]: r["quartile"] for r in m["ranks"]}
        self.assertEqual(areas["Human-Computer Interaction"], "Q3")
        self.assertEqual(areas["Computer Science Applications"], "Q4")
        self.assertEqual(m["sjr"], 0.25)

    def test_unknown_issn(self):
        code, out, _ = self.run_cli("journal", "1111-1111")
        self.assertIn("no aparece", out)


class TestEnrichFilterExportCite(Base):
    def _search(self):
        out = os.path.join(self.tmp, "r.json")
        self.run_cli("search", "TITLE(x)", "--max", "25", "--out", out, "--show", "0")
        return out

    def test_pipeline(self):
        f = self._search()
        code, _, err = self.run_cli("enrich", f)
        self.assertEqual(code, 0, err)
        enr = f.replace(".json", "_enriched.json")
        recs = rj(enr)["records"]
        a, b = recs
        self.assertEqual(a["quartile_best"], "Q3")
        self.assertEqual(a["abstract_source"], "Crossref")
        self.assertTrue(a["abstract"].startswith("This paper"))
        self.assertEqual(a["authors"][0]["family"], "Silva")
        # el segundo no tiene resumen en Crossref → Semantic Scholar
        self.assertEqual(b["abstract_source"], "Semantic Scholar")
        self.assertIsNone(b["quartile_best"])
        self.assertIn("quartile_best", b["missing"])

        code, _, err = self.run_cli("filter", enr, "--quartiles", "Q3,Q4")
        self.assertEqual(code, 0, err)
        flt = rj(enr.replace(".json", "_filtered.json"))["records"]
        self.assertEqual(len(flt), 1)

        code, _, err = self.run_cli("filter", enr, "--quartiles", "Q4", "--any-area",
                                    "--out", os.path.join(self.tmp, "q4.json"))
        self.assertEqual(len(rj(os.path.join(self.tmp, "q4.json"))["records"]), 1)

        code, _, _ = self.run_cli("export", enr, "--format", "md")
        md = rt(enr.replace(".json", ".md"))
        self.assertIn("| 2021 |", md)
        self.assertIn("no aparece", md)
        code, _, _ = self.run_cli("export", enr)
        self.assertTrue(os.path.exists(enr.replace(".json", ".csv")))

    def test_cite_apa_and_bibtex(self):
        code, out, _ = self.run_cli("cite", "10.5555/demo.001", "--plain")
        self.assertEqual(code, 0)
        self.assertIn("Silva, A. B., Souza, C., & Pereira, D.-E. (2021).", out)
        self.assertIn("Example Journal of Interactive Systems, 12(1), 45–60. https://doi.org/10.5555/demo.001", out)
        code, out, _ = self.run_cli("cite", "10.5555/demo.001", "--style", "bibtex")
        self.assertIn("@article{silva2021accessibility,", out)
        self.assertIn("pages = {45--60}", out)

    def test_abstract_not_found_never_invented(self):
        scopus.http_get = lambda *a, **k: None
        code, out, _ = self.run_cli("abstract", "10.9999/none")
        self.assertTrue(out.startswith("no aparece ("))
        self.assertNotIn("[", out)


class TestMergeSummary(Base):
    def test_merge_and_summary(self):
        a = os.path.join(self.tmp, "a.json")
        b = os.path.join(self.tmp, "b.json")
        self.run_cli("search", "TITLE(x)", "--out", a, "--show", "0")
        self.run_cli("search", "TITLE(y)", "--out", b, "--show", "0")
        m = os.path.join(self.tmp, "m.json")
        code, _, err = self.run_cli("merge", a, b, "--out", m)
        self.assertEqual(code, 0, err)
        d = rj(m)
        self.assertEqual(d["meta"]["duplicates_removed"], 2)
        self.assertEqual(len(d["records"]), 2)
        self.run_cli("enrich", m)
        code, out, _ = self.run_cli("summary", m.replace(".json", "_enriched.json"), "--by", "journal")
        self.assertIn("| Example Journal of Interactive Systems | 1 | 7 | Q3 | 1.6 | 0.25 |", out)
        code, out, _ = self.run_cli("summary", m.replace(".json", "_enriched.json"), "--by", "year")
        self.assertLess(out.index("| 2021 |"), out.index("| 2024 |"))


class TestFromRealRun(Base):
    """Casos detectados en la primera prueba con la API real."""

    def test_chapter_uses_book_title_and_issued_year(self):
        code, out, _ = self.run_cli("cite", "10.5555/chapter.001", "--plain")
        self.assertIn("Pérez, L., & Gil, T. (2026).", out)
        self.assertIn("En Proceedings of the Example Conference on Accessibility (pp. 377–384).", out)
        code, out, _ = self.run_cli("cite", "10.5555/chapter.001", "--style", "bibtex")
        self.assertIn("booktitle = {Proceedings of the Example Conference on Accessibility}", out)
        self.assertIn("series = {Lecture Notes in Example Science}", out)

    def test_publisher_elided_abstract_note(self):
        ab, src, note = scopus.get_abstract("10.5555/chapter.001")
        self.assertIsNone(ab)
        self.assertIn("editorial", note)
        code, out, _ = self.run_cli("abstract", "10.5555/chapter.001")
        self.assertTrue(out.startswith("no aparece ("))

    def test_scopus_abstract_retrieval_used_and_disabled_on_403(self):
        calls = {"n": 0}

        def fake(url, headers=None, tries=4, base_wait=2.0):
            if "/content/abstract/" in url:
                calls["n"] += 1
                if "eid/2-s2.0-1" in url:
                    return {"abstracts-retrieval-response": {"coredata": {
                        "dc:description": "Resumen desde Scopus. © 2026 Elsevier Ltd"}}}
                raise scopus.ApiError("HTTP 403 en api.elsevier.com: sin permiso")
            return fake_http_get(url, headers, tries, base_wait)
        scopus.http_get = fake
        scopus.SCOPUS_ABSTRACT_OK[0] = True
        ab, src, _ = scopus.get_abstract("10.9/a", {"eid": "2-s2.0-1"})
        self.assertEqual((ab, src), ("Resumen desde Scopus.", "Scopus"))
        with redirect_stderr(io.StringIO()):
            scopus.get_abstract("10.5555/demo.001", {"eid": "2-s2.0-2"})
            scopus.get_abstract("10.5555/demo.001", {"eid": "2-s2.0-3"})
        self.assertEqual(calls["n"], 2)  # tras el 403 no vuelve a intentar
        scopus.SCOPUS_ABSTRACT_OK[0] = True

    def test_book_series_note_and_journals_only(self):
        recs = [{"title": "Serie", "issn": "1234-5679", "source_type": "Book Series", "year": 2026},
                {"title": "Revista", "issn": "1234-5679", "source_type": "Journal", "year": 2026}]
        f = os.path.join(self.tmp, "s.json")
        scopus.save_json(f, recs)
        self.run_cli("enrich", f, "--no-abstracts")
        enr = rj(f.replace(".json", "_enriched.json"))["records"]
        self.assertIn("serie", enr[0]["quartile_note"])
        self.assertNotIn("quartile_note", enr[1])
        self.run_cli("filter", f.replace(".json", "_enriched.json"), "--journals-only",
                     "--out", os.path.join(self.tmp, "j.json"))
        self.assertEqual([r["title"] for r in rj(os.path.join(self.tmp, "j.json"))["records"]], ["Revista"])

    def test_no_double_punctuation(self):
        m = {"type": "proceedings-article", "title": ["Is there evidence?"], "container-title": ["Proc. X"],
             "author": [{"given": "Ana", "family": "Ruiz"}], "issued": {"date-parts": [[2023]]}, "page": "1-4",
             "publisher": "IEEE", "DOI": "10.1/x"}
        self.assertIn("Is there evidence? En Proc. X (pp. 1–4). IEEE.", scopus.apa(m, italics=False))

    def test_query_file(self):
        q = os.path.join(self.tmp, "q.txt")
        with open(q, "w", encoding="utf-8-sig") as fh:
            fh.write('TITLE-ABS-KEY("cognitive accessibility")\n  AND PUBYEAR > 2019\n')
        out = os.path.join(self.tmp, "r.json")
        code, _, err = self.run_cli("search", "--query-file", q, "--out", out, "--show", "0")
        self.assertEqual(code, 0, err)
        self.assertEqual(rj(out)["meta"]["query"], 'TITLE-ABS-KEY("cognitive accessibility") AND PUBYEAR > 2019')
        self.assertEqual(rj(out)["meta"]["sort"], "relevancy")


class TestHttp(unittest.TestCase):
    """http_get contra un servidor local: reintento ante 429 y mensaje claro ante 400."""

    def setUp(self):
        import http.server
        import threading
        self.calls = {"n": 0}
        calls = self.calls

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/retry"):
                    calls["n"] += 1
                    if calls["n"] == 1:
                        self.send_response(429)
                        self.send_header("Retry-After", "0")
                        self.end_headers()
                        return
                    body = b'{"ok": true}'
                    code = 200
                else:
                    body = b'{"service-error": {"status": {"statusText": "Error translating query"}}}'
                    code = 400
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"
        os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_retry_on_429(self):
        with redirect_stderr(io.StringIO()):
            d = scopus.http_get(self.base + "/retry", base_wait=0.01)
        self.assertEqual(d, {"ok": True})
        self.assertEqual(self.calls["n"], 2)

    def test_400_message(self):
        with self.assertRaises(scopus.ApiError) as cm:
            scopus.http_get(self.base + "/bad", base_wait=0.01)
        self.assertIn("consulta mal formada", str(cm.exception))
        self.assertIn("Error translating query", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
