"""Tests for kit/scripts/sources.py.

No network: every request is answered by a fake registry, and a request the
test did not expect fails the test. Run from the repository root:

    python3 -m unittest discover -s tests

Two live tests against the real services run only when
THESIS_KIT_NETWORK_TESTS=1 is set. The PDF test with macOS's own reader runs
on macOS only.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "kit" / "scripts" / "sources.py"
_spec = importlib.util.spec_from_file_location("sources", SCRIPT)
sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sources)

ALPHAFOLD = "10.1038/s41586-021-03819-2"
ALPHAFOLD_TITLE = "Highly accurate protein structure prediction with AlphaFold"
ALPHAFOLD_REF = ("Jumper, J., Evans, R., et al. (2021). Highly accurate protein structure "
                 "prediction with AlphaFold. Nature, 596, 583–589. https://doi.org/" + ALPHAFOLD)
TODAY = datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# A fake web
# --------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def http_error(url, status, headers=None, body=None):
    return urllib.error.HTTPError(url, status, "error", headers or {},
                                  io.BytesIO(json.dumps(body or {}).encode("utf-8")))


class FakeWeb:
    """Answers each request from `routes`, a list of (url substring, answer).

    An answer is a dict (JSON body), an int (HTTP error status), a tuple
    (status, headers, body) for an HTTP error with details, or an exception
    to raise. A list of answers is given out in order; its last one repeats."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.contexts = []

    def __call__(self, request, timeout=None, context=None):
        url = request.full_url
        self.calls.append(url)
        self.contexts.append(context)
        for pattern, answer in self.routes:
            if pattern in url:
                if isinstance(answer, list):
                    answer = answer.pop(0) if len(answer) > 1 else answer[0]
                if isinstance(answer, BaseException):
                    raise answer
                if isinstance(answer, int):
                    raise http_error(url, answer)
                if isinstance(answer, tuple):
                    raise http_error(url, *answer)
                return FakeResponse(answer)
        raise AssertionError(f"unexpected request: {url}")

    def called(self, pattern):
        return [u for u in self.calls if pattern in u]


class WebTestCase(unittest.TestCase):
    """Patches the network and the clock; `self.sleeps` records every wait."""

    def web(self, routes):
        fake = FakeWeb(routes)
        self.sleeps = []
        stack = contextlib.ExitStack()
        stack.enter_context(patch("urllib.request.urlopen", fake))
        stack.enter_context(patch.object(sources.time, "sleep", side_effect=self.sleeps.append))
        stack.enter_context(patch.object(sources, "RATE_LIMITED", set()))
        stack.enter_context(patch.object(sources, "WAITED", set()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(stack.close)
        return fake


def unreachable():
    return urllib.error.URLError("connection refused")


# --------------------------------------------------------------------------
# Sample registry answers
# --------------------------------------------------------------------------

def crossref_msg(doi=ALPHAFOLD, title=ALPHAFOLD_TITLE,
                 authors=(("Jumper", "John"), ("Evans", "Richard")), year=2021, venue="Nature",
                 type_="journal-article", publisher="Springer Science and Business Media LLC",
                 updated_by=None, abstract=None, **extra):
    msg = {"DOI": doi, "title": [title] if title else [],
           "author": [{"family": f, "given": g} for f, g in authors],
           "issued": {"date-parts": [[year]]}, "container-title": [venue] if venue else [],
           "type": type_, "publisher": publisher, "volume": "596", "issue": "7873",
           "page": "583-589", "is-referenced-by-count": 30000}
    if updated_by:
        msg["updated-by"] = updated_by
    if abstract:
        msg["abstract"] = abstract
    msg.update(extra)
    return msg


def crossref_one(**kw):
    return {"message": crossref_msg(**kw)}


def crossref_list(*msgs):
    return {"message": {"items": list(msgs)}}


def datacite_one(title="Attention Is All You Need", creators=None, year=2017, publisher="arXiv"):
    creators = creators or [{"name": "Vaswani, Ashish", "familyName": "Vaswani", "givenName": "Ashish"}]
    return {"data": {"attributes": {"titles": [{"title": title}], "creators": creators,
                                    "publicationYear": year, "publisher": publisher,
                                    "types": {"resourceTypeGeneral": "Preprint"}}}}


def openalex_work(doi=ALPHAFOLD, title=ALPHAFOLD_TITLE,
                  authors=("John Jumper", "Richard Evans"), year=2021, type_="article",
                  venue="Nature", retracted=False, abstract=None, oa_url=None,
                  openalex_id="W3177828909", cited_by_count=100):
    inverted = {}
    for position, word in enumerate((abstract or "").split()):
        inverted.setdefault(word, []).append(position)
    return {"id": f"https://openalex.org/{openalex_id}",
            "doi": f"https://doi.org/{doi}" if doi else None, "title": title,
            "authorships": [{"author": {"display_name": a}} for a in authors],
            "publication_year": year, "type": type_, "is_retracted": retracted,
            "primary_location": {"source": {"display_name": venue}},
            "abstract_inverted_index": inverted or None,
            "open_access": {"oa_url": oa_url}, "cited_by_count": cited_by_count}


def openalex_list(*works):
    return {"meta": {}, "results": list(works)}


RETRACTION = [{"DOI": "10.1016/s0140-6736(10)60175-4", "type": "retraction"}]
CORRECTION = [{"DOI": "10.1016/s0140-6736(04)15715-2", "type": "correction"}]
NOTHING_BY_TITLE = [("openalex.org/works?filter=title.search", openalex_list()),
                    ("crossref.org/works?", crossref_list())]


# --------------------------------------------------------------------------
# DOIs and text
# --------------------------------------------------------------------------

class DoiTests(WebTestCase):
    def test_resolver_prefixes_case_and_trailing_punctuation_are_removed(self):
        self.assertEqual(sources.bare_doi("https://doi.org/10.1038/ABC"), "10.1038/abc")
        self.assertEqual(sources.bare_doi("http://dx.doi.org/10.5/Y"), "10.5/y")
        self.assertEqual(sources.bare_doi("doi: 10.1/X."), "10.1/x")

    def test_dois_are_found_in_running_text_links_and_exports(self):
        f = sources.dois_in
        self.assertEqual(f(ALPHAFOLD_REF), [ALPHAFOLD])
        self.assertEqual(f("See doi:10.1234/ABC.def; and https://doi.org/10.5555/x-1."),
                         ["10.1234/abc.def", "10.5555/x-1"])
        self.assertEqual(f("doi = {10.1038/s41586-021-03819-2},"), [ALPHAFOLD])
        self.assertEqual(f("no identifier here, only 10.12/short"), [])

    def test_brackets_around_a_doi_are_not_part_of_it_but_brackets_inside_are(self):
        f = sources.dois_in
        self.assertEqual(f("The Lancet, 351 (doi:10.1016/S0140-6736(97)11096-0)."),
                         ["10.1016/s0140-6736(97)11096-0"])
        self.assertEqual(f("[https://doi.org/10.1000/xyz123]"), ["10.1000/xyz123"])
        self.assertEqual(f("[link](https://doi.org/10.1000/abc)"), ["10.1000/abc"])
        self.assertEqual(f("<https://doi.org/10.1016/S0140-6736(97)11096-0>"),
                         ["10.1016/s0140-6736(97)11096-0"])

    def test_closing_quotes_and_an_ellipsis_are_not_part_of_a_doi(self):
        f = sources.dois_in
        self.assertEqual(f("“Title.” https://doi.org/10.1037/0021-9010.86.3.499”"),
                         ["10.1037/0021-9010.86.3.499"])
        self.assertEqual(f("see 10.1038/s41562-018-0506-1…"), ["10.1038/s41562-018-0506-1"])

    def test_malformed_dois_are_invalid_without_any_request(self):
        web = self.web([])
        for bad in ["", "   ", "not-a-doi", "10.1234", "10.1234/", "10.abcd/xyz", "11.1234/abc"]:
            with self.subTest(doi=bad):
                self.assertEqual(sources.lookup(bad)["status"], "invalid")
        self.assertEqual(web.calls, [])

    def test_unusual_but_real_dois_are_not_rejected_by_shape(self):
        self.web([("crossref.org/works/", crossref_one())])
        for doi in ["10.1002/(SICI)1099-1050(199806)7:3<233::AID-HEC343>3.0.CO;2-Y",
                    "10.1000.100/182"]:
            with self.subTest(doi=doi):
                self.assertEqual(sources.lookup(doi)["status"], "resolved")

    def test_fold_and_title_key_ignore_accents_case_and_punctuation(self):
        self.assertEqual(sources.fold("Müller"), sources.fold("MULLER"))
        self.assertEqual(sources.title_key("Cooling the cities – a review!"),
                         sources.title_key("cooling the Cities: A Review"))

    def test_markup_is_stripped_from_abstracts(self):
        jats = "<jats:title>Abstract</jats:title><jats:p>Proteins are  essential.</jats:p>"
        self.assertEqual(sources.plain_text(jats), "Proteins are essential.")


# --------------------------------------------------------------------------
# HTTPS certificates and the OpenAlex key
# --------------------------------------------------------------------------

class CertificateTests(WebTestCase):
    def fake_context(self, trusted_certificates):
        context = MagicMock()
        context.cert_store_stats.return_value = {"x509_ca": trusted_certificates}
        return context

    def test_an_empty_certificate_store_falls_back_to_the_system_file(self):
        # python.org's Python on macOS, before "Install Certificates" was run.
        context = self.fake_context(0)
        with patch.object(sources.ssl, "create_default_context", return_value=context), \
                patch.object(sources.os.path, "exists", lambda p: p == "/etc/ssl/cert.pem"):
            sources.ssl_context()
        context.load_verify_locations.assert_called_once_with(cafile="/etc/ssl/cert.pem")

    def test_a_filled_certificate_store_is_left_alone(self):
        context = self.fake_context(128)
        with patch.object(sources.ssl, "create_default_context", return_value=context):
            sources.ssl_context()
        context.load_verify_locations.assert_not_called()

    def test_every_request_uses_that_context(self):
        web = self.web([("crossref.org/works/", crossref_one())])
        sources.lookup(ALPHAFOLD)
        self.assertEqual(web.contexts, [sources.SSL_CONTEXT])


class OpenAlexKeyTests(unittest.TestCase):
    def test_the_key_comes_from_the_environment_else_from_the_tools_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sources, "REPO", Path(tmp)), \
                patch.dict(os.environ):
            os.environ.pop("THESIS_KIT_OPENALEX_KEY", None)
            self.assertEqual(sources._openalex_key(), "")
            (Path(tmp) / ".tools").mkdir()
            (Path(tmp) / ".tools" / "openalex-key").write_text("abc123\nsecond line\n")
            self.assertEqual(sources._openalex_key(), "abc123")
            os.environ["THESIS_KIT_OPENALEX_KEY"] = "from-env"
            self.assertEqual(sources._openalex_key(), "from-env")


# --------------------------------------------------------------------------
# HTTP: retries and rate limits
# --------------------------------------------------------------------------

class FetchTests(WebTestCase):
    URL = "https://api.crossref.org/works/10.1/x"
    OPENALEX = "https://api.openalex.org/works?search=x"

    def test_404_raises_not_found_without_retrying(self):
        web = self.web([("crossref", 404)])
        with self.assertRaises(sources.NotFound):
            sources.fetch_json(self.URL)
        self.assertEqual(len(web.calls), 1)

    def test_rate_limit_is_waited_out_once_as_the_service_asks(self):
        self.web([("crossref", [(429, {"Retry-After": "7"}, {}), {"ok": True}])])
        self.assertEqual(sources.fetch_json(self.URL), {"ok": True})
        self.assertEqual(self.sleeps, [7.0])

    def test_a_service_is_waited_for_only_once_per_run(self):
        # Anonymous OpenAlex answers 429 with a short Retry-After over and over;
        # waiting on every request made one `add` take 86 s.
        web = self.web([("openalex", [(429, {"Retry-After": "35"}, {}), {"ok": True},
                                      (429, {"Retry-After": "35"}, {})])])
        self.assertEqual(sources.fetch_json(self.OPENALEX), {"ok": True})
        with self.assertRaises(sources.RateLimited):
            sources.fetch_json(self.OPENALEX)
        self.assertEqual((self.sleeps, len(web.calls)), ([35.0], 3))

    def test_without_a_retry_after_the_wait_is_10_seconds(self):
        self.web([("crossref", [503, {"ok": True}])])
        sources.fetch_json(self.URL)
        self.assertEqual(self.sleeps, [10.0])

    def test_rate_limit_reported_in_a_json_body_is_honoured(self):
        self.web([("openalex", [{"error": "Rate limit exceeded", "retryAfter": 3}, {"ok": True}])])
        self.assertEqual(sources.fetch_json(self.OPENALEX), {"ok": True})
        self.assertEqual(self.sleeps, [3.0])

    def test_a_wait_longer_than_45_seconds_raises_at_once(self):
        # OpenAlex, pausing anonymous search under heavy load, asks for 60 s.
        for answer in [(503, {"Retry-After": "60"}, {"error": "Search temporarily unavailable"}),
                       (429, {"Retry-After": "3600"}, {}),
                       (429, {}, {"error": "Rate limit exceeded", "retryAfter": 86400}),
                       {"error": "Rate limit exceeded", "retryAfter": 600}]:
            with self.subTest(answer=answer):
                web = self.web([("openalex", answer)])
                with self.assertRaises(sources.RateLimited):
                    sources.fetch_json(self.OPENALEX)
                self.assertEqual((self.sleeps, len(web.calls)), ([], 1))

    def test_a_used_up_budget_raises_at_once(self):
        self.web([("openalex", (429, {"Retry-After": "5"},
                                {"error": "Rate limit exceeded",
                                 "message": "Your daily budget is exhausted."}))])
        with self.assertRaises(sources.RateLimited):
            sources.fetch_json(self.OPENALEX)
        self.assertEqual(self.sleeps, [])

    def test_after_one_rate_limit_the_service_is_not_asked_again(self):
        web = self.web([("openalex", (429, {"Retry-After": "3600"}, {})),
                        ("crossref", {"ok": True})])
        for _ in range(3):
            with self.assertRaises(sources.RateLimited):
                sources.fetch_json(self.OPENALEX)
        self.assertEqual(len(web.called("openalex")), 1)
        self.assertEqual(sources.fetch_json(self.URL), {"ok": True})   # other services still work

    def test_transport_errors_are_retried_with_growing_pauses_then_raised(self):
        web = self.web([("crossref", unreachable())])
        with self.assertRaises(urllib.error.URLError):
            sources.fetch_json(self.URL)
        self.assertEqual(len(web.calls), 3)
        self.assertEqual(len(self.sleeps), 2)
        self.assertLess(self.sleeps[0], self.sleeps[1])


# --------------------------------------------------------------------------
# lookup: does a DOI exist?
# --------------------------------------------------------------------------

class LookupTests(WebTestCase):
    def test_crossref_record_resolves_with_its_details(self):
        self.web([("crossref.org/works/", crossref_one())])
        rec = sources.lookup(ALPHAFOLD)
        self.assertEqual((rec["status"], rec["agency"]), ("resolved", "crossref"))
        self.assertEqual(rec["authors"][0], {"family": "Jumper", "given": "John"})
        self.assertEqual((rec["year"], rec["venue"], rec["volume"], rec["pages"]),
                         (2021, "Nature", "596", "583-589"))
        self.assertFalse(rec["retracted"])

    def test_datacite_answers_when_crossref_has_no_record(self):
        self.web([("crossref.org/works/", 404),
                  ("datacite.org/dois/", datacite_one(publisher={"name": "arXiv"}))])
        rec = sources.lookup("10.48550/arXiv.1706.03762")
        self.assertEqual((rec["status"], rec["agency"]), ("resolved", "datacite"))
        self.assertEqual(rec["authors"][0]["family"], "Vaswani")
        self.assertEqual(rec["publisher"], "arXiv")

    def test_every_registry_saying_no_is_absent(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404), ("://doi.org/", 404)])
        self.assertEqual(sources.lookup("10.1234/abc")["status"], "absent")

    def test_doi_org_answers_for_dois_registered_elsewhere(self):
        # The EU Publications Office, JaLC and others register DOIs outside
        # Crossref and DataCite; doi.org serves their records as CSL-JSON.
        web = self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404),
                        ("://doi.org/", {"type": "book", "title": "DigComp 2.2",
                                         "author": [{"literal": "European Commission"}],
                                         "issued": {"date-parts": [[2022]]},
                                         "publisher": "Publications Office"})])
        rec = sources.lookup("10.2760/115376")
        self.assertEqual((rec["status"], rec["agency"], rec["doi"], rec["year"]),
                         ("resolved", "doi.org", "10.2760/115376", 2022))
        self.assertEqual(rec["authors"], [{"family": "European Commission", "given": ""}])
        self.assertEqual(web.called("://doi.org/"), ["https://doi.org/10.2760/115376"])

    def test_an_unreachable_doi_org_makes_it_unknown_never_absent(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404),
                  ("://doi.org/", unreachable())])
        self.assertEqual(sources.lookup("10.2760/115376")["status"], "unknown")

    def test_a_doi_copied_from_a_publisher_link_is_tried_without_the_link_tail(self):
        for junk, doi in [("10.1080/02673843.2019.1590851?scroll=top&needaccess=true",
                           "10.1080/02673843.2019.1590851"),
                          ("10.1108/02683940710733115/full/html", "10.1108/02683940710733115"),
                          ("10.1038/s41562-018-0506-1.pdf", "10.1038/s41562-018-0506-1")]:
            with self.subTest(doi=junk):
                web = self.web([("crossref.org/works/", [404, crossref_one(doi=doi)]),
                                ("datacite.org/dois/", 404), ("://doi.org/", 404)])
                rec = sources.lookup(junk)
                self.assertEqual((rec["status"], rec["doi"]), ("resolved", doi))
                self.assertEqual(len(web.called("crossref.org/works/")), 2)

    def test_a_made_up_doi_with_a_link_tail_is_still_absent(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404), ("://doi.org/", 404)])
        self.assertEqual(sources.lookup("10.1234/made-up/full")["status"], "absent")

    def test_an_unreachable_registry_makes_it_unknown_never_absent(self):
        web = self.web([("crossref.org/works/", unreachable()), ("datacite.org/dois/", 404)])
        rec = sources.lookup("10.1234/abc")
        self.assertEqual(rec["status"], "unknown")
        self.assertTrue(web.called("datacite.org"), "DataCite must still be asked")

    def test_a_rate_limited_crossref_still_lets_datacite_answer(self):
        self.web([("crossref.org/works/", 429), ("datacite.org/dois/", datacite_one())])
        self.assertEqual(sources.lookup("10.48550/arxiv.1706.03762")["agency"], "datacite")

    def test_a_retraction_notice_marks_the_record_retracted(self):
        self.web([("crossref.org/works/", crossref_one(updated_by=CORRECTION + RETRACTION))])
        rec = sources.lookup("10.1016/S0140-6736(97)11096-0")
        self.assertTrue(rec["retracted"])
        self.assertEqual([n["type"] for n in rec["notices"]], ["correction", "retraction"])

    def test_a_correction_alone_is_listed_but_not_a_retraction(self):
        self.web([("crossref.org/works/", crossref_one(updated_by=CORRECTION))])
        rec = sources.lookup(ALPHAFOLD)
        self.assertFalse(rec["retracted"])
        self.assertEqual(rec["notices"][0]["type"], "correction")

    def test_an_organisation_as_author_is_kept(self):
        msg = crossref_msg()
        msg["author"] = [{"name": "World Health Organization"}]
        self.web([("crossref.org/works/", {"message": msg})])
        self.assertEqual(sources.lookup(ALPHAFOLD)["authors"],
                         [{"family": "World Health Organization", "given": ""}])


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

class RecordTests(unittest.TestCase):
    def test_crossref_gives_the_print_year_when_there_is_one(self):
        online_first = crossref_msg(year=2012, **{"published-print": {"date-parts": [[2014, 3]]}})
        self.assertEqual(sources.from_crossref(online_first)["year"], 2014)
        self.assertEqual(sources.from_crossref(crossref_msg(year=2012))["year"], 2012)

    def test_titles_and_venues_are_cleaned_in_every_converter(self):
        messy = "  The <i>E. coli</i> genome &amp; its\n  proteins*† "
        want = "The E. coli genome & its proteins"
        self.assertEqual(sources.from_crossref(crossref_msg(title=messy, venue="Cell &amp; Bio"))
                         ["title"], want)
        self.assertEqual(sources.from_crossref(crossref_msg(venue="Cell &amp; Bio"))["venue"],
                         "Cell & Bio")
        attrs = datacite_one(title=messy)["data"]["attributes"]
        self.assertEqual(sources.from_datacite(attrs)["title"], want)
        rec = sources.from_openalex(openalex_work(title=messy, venue="Nature ‡"))
        self.assertEqual((rec["title"], rec["venue"]), (want, "Nature"))

    def test_a_closing_period_is_not_part_of_a_title(self):
        self.assertEqual([sources.clean_title(t) for t in (
            "Meta-analysis of individual consequences.", "Consequences.*", "Is it true?", "Wait...")],
            ["Meta-analysis of individual consequences", "Consequences", "Is it true?", "Wait..."])

    def test_openalex_records_keep_the_citation_count_and_their_id(self):
        rec = sources.from_openalex(openalex_work(openalex_id="W2741809807", cited_by_count=42))
        self.assertEqual((rec["openalex_id"], rec["cited_by_count"]), ("W2741809807", 42))

    def test_crossref_records_keep_the_citation_count(self):
        self.assertEqual(sources.from_crossref(crossref_msg())["cited_by_count"], 30000)


# --------------------------------------------------------------------------
# search (the `find` command)
# --------------------------------------------------------------------------

class SearchTests(WebTestCase):
    def test_openalex_ranks_and_its_order_is_kept_without_checking_each_doi(self):
        web = self.web([("openalex.org/works?search", openalex_list(
            openalex_work(doi="10.1/b", title="Most relevant paper", cited_by_count=900),
            openalex_work(doi="10.1/a", title="Second paper", cited_by_count=5)))])
        works, ranked_by = sources.search("green roofs", n=5)
        self.assertEqual(ranked_by, "openalex")
        self.assertEqual([w["doi"] for w in works], ["10.1/b", "10.1/a"])
        self.assertEqual([w["cited_by_count"] for w in works], [900, 5])
        self.assertEqual(web.calls, web.called("openalex.org/works?search"))   # no crossref at all

    def test_the_openalex_request_asks_for_citable_types_and_only_the_needed_fields(self):
        web = self.web([("openalex.org/works?search", openalex_list())])
        sources.search("x", n=4)
        url = urllib.parse.unquote(web.calls[0])
        self.assertIn("type:article|review|book|book-chapter|preprint", url)
        self.assertIn("select=" + sources.OPENALEX_FIELDS, url)
        self.assertIn("per-page=12", url)

    def test_non_works_and_weak_records_are_filtered_out(self):
        good = openalex_work(doi="10.1/good", title="Green roofs cool cities")
        junk = [
            openalex_work(doi="10.1/rev", title="Review for: Green roofs cool cities"),
            openalex_work(doi="10.1/book-review", title="Book review: Green roofs"),
            openalex_work(doi="10.1/paper/v1/review2", title="Referee comments"),
            openalex_work(doi="10.1/f1000", title="Faculty Opinions recommendation of Green roofs"),
            openalex_work(doi="10.1/anon", title="A paper nobody wrote", authors=()),
            openalex_work(doi=None, title="A work without a DOI"),
            openalex_work(doi="10.1/mononym", title="A lonely note", authors=("Pi",), venue=None),
            openalex_work(doi="10.1/retracted", title="Retracted study", retracted=True),
            openalex_work(doi="10.1/dataset", title="Green roof data", type_="dataset"),
        ]
        self.web([("openalex.org/works?search", openalex_list(good, *junk))])
        self.assertEqual([w["doi"] for w in sources.search("green roofs", n=5)[0]], ["10.1/good"])

    def test_the_journal_version_replaces_its_preprint(self):
        preprint = openalex_work(doi="10.2139/ssrn.1", type_="preprint", venue="SSRN")
        journal = openalex_work(doi="10.1016/j.x.1")
        for order in ([preprint, journal], [journal, preprint]):
            with self.subTest(first=order[0]["doi"]):
                self.web([("openalex.org/works?search", openalex_list(*order))])
                works, _ = sources.search("x", n=5)
                self.assertEqual([w["doi"] for w in works], ["10.1016/j.x.1"])

    def test_crossref_answers_only_when_openalex_cannot(self):
        self.web([("openalex.org", unreachable()),
                  ("crossref.org/works?", crossref_list(
                      crossref_msg(doi="10.1/a", title="First paper"),
                      crossref_msg(doi="10.1/rev", title="Review for: First paper")))])
        works, ranked_by = sources.search("x", n=5)
        self.assertEqual(ranked_by, "crossref")
        self.assertEqual([w["doi"] for w in works], ["10.1/a"])
        self.assertEqual(works[0]["cited_by_count"], 30000)

    def test_a_rate_limited_openalex_falls_back_to_crossref_without_waiting(self):
        web = self.web([("openalex.org", (429, {"Retry-After": "86400"}, {})),
                        ("crossref.org/works?", crossref_list(crossref_msg(doi="10.1/a")))])
        works, ranked_by = sources.search("x", n=5)
        self.assertEqual((ranked_by, len(works), self.sleeps), ("crossref", 1, []))
        self.assertIn("is-referenced-by-count", urllib.parse.unquote(web.called("crossref")[0]))

    def test_crossref_never_tops_up_a_short_openalex_list(self):
        web = self.web([("openalex.org/works?search", openalex_list(openalex_work()))])
        works, _ = sources.search("x", n=10)
        self.assertEqual(len(works), 1)
        self.assertFalse(web.called("crossref"))

    def test_no_preprints_keeps_preprint_types_out_of_both_searches(self):
        web = self.web([("openalex.org", unreachable()), ("crossref.org/works?", crossref_list())])
        sources.search("x", n=5, preprints=False)
        self.assertNotIn("preprint", web.called("openalex.org/works?")[0])
        self.assertNotIn("posted-content", web.called("crossref.org/works?")[0])

    def test_nothing_reachable_is_reported_as_no_service_answered(self):
        self.web([("crossref.org", unreachable()), ("openalex.org", unreachable())])
        self.assertEqual(sources.search("x", n=5), ([], None))


# --------------------------------------------------------------------------
# Comparing a claim with a record
# --------------------------------------------------------------------------

class MatchingTests(unittest.TestCase):
    def test_family_names_are_read_from_every_common_shape(self):
        f = sources.claimed_families
        self.assertEqual(f(["Müller, J.", "Jana Schmidt"]), ["Müller", "Schmidt"])
        self.assertEqual(f("Müller & Schmidt"), ["Müller", "Schmidt"])
        self.assertEqual(f("Vaswani, Shazeer, Parmar"), ["Vaswani", "Shazeer", "Parmar"])
        self.assertEqual(f([{"family": "Chen", "given": "Mei"}]), ["Chen"])
        self.assertEqual(f([]), [])

    def test_vancouver_names_put_the_initials_after_the_family_name(self):
        f = sources.claimed_families
        self.assertEqual(f("Wakefield AJ, Murch SH, Anthony A"), ["Wakefield", "Murch", "Anthony"])
        self.assertEqual(f(["Topol EJ", "Topol E. J.", "Kim J-H", "van der Berg AB"]),
                         ["Topol", "Topol", "Kim", "van der Berg"])
        self.assertEqual(f(["John SMITH", "E. J. Topol"]), ["SMITH", "Topol"])
        self.assertEqual(f(["Topol  EJ\n", "\tKim J-H"]), ["Topol", "Kim"])
        self.assertEqual(sources.match_authors(["Topol EJ"], [{"family": "Topol", "given": "Eric J."}]),
                         "yes")

    def test_et_al_and_u_a_are_not_read_as_names(self):
        f = sources.claimed_families
        self.assertEqual(f("Jumper et al."), ["Jumper"])
        self.assertEqual(f(["Ortiz", "et al."]), ["Ortiz"])
        self.assertEqual(f("Müller u. a."), ["Müller"])
        self.assertEqual(f("Chen, M., et al."), ["Chen"])

    def test_titles(self):
        registry = "Cooling the cities – A review of reflective and green roof mitigation technologies"
        self.assertEqual(sources.match_title(registry, registry), "yes")
        self.assertEqual(sources.match_title("Cooling the cities", registry), "yes")   # main title
        self.assertEqual(sources.match_title("Cooling the city: a review of reflective and "
                                             "green roof mitigation technology", registry), "yes")
        self.assertEqual(sources.match_title("Deep learning for cities", registry), "no")
        self.assertEqual(sources.match_title("", registry), "not given")

    def test_a_short_fragment_is_not_a_title_match(self):
        registry = "Introduction to urban climate: models and methods"
        self.assertEqual(sources.match_title("Introduction", registry), "no")
        self.assertEqual(sources.match_title("green roof", "Cooling the cities – a review of "
                                             "reflective and green roof mitigation"), "no")

    def test_authors(self):
        registry = [{"family": "Müller", "given": "Jana"}, {"family": "van den Berg", "given": "Tom"}]
        self.assertEqual(sources.match_authors(["Muller"], registry), "yes")
        self.assertEqual(sources.match_authors(["T. Berg"], registry), "yes")
        self.assertEqual(sources.match_authors(["van den Berg, T."], registry), "yes")
        self.assertEqual(sources.match_authors(["Smith", "Müller"], registry), "partly")
        self.assertEqual(sources.match_authors(["Smith"], registry), "no")
        self.assertEqual(sources.match_authors([], registry), "not given")

    def test_hyphenated_and_compound_names_match_any_of_their_parts(self):
        m = sources.match_authors
        self.assertEqual(m(["Keles, S."], [{"family": "Keles-Gordesli", "given": "Sevda"}]), "yes")
        self.assertEqual(m(["Keles-Gordesli, S."], [{"family": "Keles", "given": "S."}]), "yes")
        self.assertEqual(m(["García Márquez, G."], [{"family": "Márquez", "given": "Gabriel García"}]),
                         "yes")

    def test_a_name_whose_parts_the_registry_swapped_still_matches(self):
        # OpenAlex reads the last word of "Zhang Wei" as the family name.
        self.assertEqual(sources.match_authors(["Zhang, W."], [{"family": "Wei", "given": "Zhang"}]),
                         "yes")

    def test_particles_alone_do_not_make_a_match(self):
        self.assertEqual(sources.match_authors(["van Dijk"], [{"family": "van den Berg", "given": "Tom"}]),
                         "no")
        self.assertEqual(sources.match_authors(["de la Cruz"], [{"family": "Cruz", "given": "Ana"}]),
                         "yes")

    def test_a_family_name_that_is_a_particle_still_matches(self):
        self.assertEqual(sources.match_authors(["Du, J."], [{"family": "Du", "given": "Jian"}]), "yes")
        self.assertEqual(sources.match_authors(["Le, Q. V."], [{"family": "Le", "given": "Quoc V."}]),
                         "yes")

    def test_years(self):
        self.assertEqual(sources.match_year(2021, 2021), "yes")
        self.assertEqual(sources.match_year("2020", 2021), "close")
        self.assertEqual(sources.match_year(2014, 2012), "close")     # print vs. online-first
        self.assertEqual(sources.match_year(2018, 2021), "no")
        self.assertEqual(sources.match_year("n.d.", 2021), "not given")
        self.assertEqual(sources.match_year("in press", 2021), "not given")
        self.assertEqual(sources.match_year("2021a", 2018), "no")
        self.assertEqual(sources.match_year(None, 2021), "not given")


class CheckTests(WebTestCase):
    CLAIM = {"ref": ALPHAFOLD_REF, "title": ALPHAFOLD_TITLE, "authors": ["Jumper, J."], "year": 2021}

    def test_a_matching_claim_is_ok_with_the_doi_from_the_reference(self):
        web = self.web([("crossref.org/works/", crossref_one())])
        result = sources.check(self.CLAIM)
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "ref"))
        self.assertEqual(result["reason"], "The DOI exists and matches the registry record.")
        self.assertEqual(len(web.calls), 1)

    def test_a_bare_doi_is_ok_with_nothing_to_compare(self):
        self.web([("crossref.org/works/", crossref_one())])
        result = sources.check({"ref": "https://doi.org/" + ALPHAFOLD})
        self.assertEqual((result["verdict"], result["reason"]),
                         ("ok", "The DOI exists; no title, authors or year were given to compare."))

    def test_authors_written_as_et_al_still_match(self):
        self.web([("crossref.org/works/", crossref_one())])
        claim = dict(self.CLAIM, authors="Jumper et al.")
        self.assertEqual(sources.check(claim)["verdict"], "ok")

    def test_a_doi_in_parentheses_is_looked_up_whole(self):
        lancet = "10.1016/s0140-6736(97)11096-0"
        self.web([("crossref.org/works/", crossref_one(doi=lancet))])
        result = sources.check({"ref": "The Lancet, 351, 637–641 (doi:10.1016/S0140-6736(97)11096-0)."})
        self.assertEqual(result["registry"]["doi"], lancet)

    def test_a_doi_field_is_ignored(self):
        web = self.web(NOTHING_BY_TITLE)
        result = sources.check({"doi": ALPHAFOLD, "title": "A work the AI made up",
                                "authors": ["Nobody"]})
        self.assertEqual((result["verdict"], result["doi_source"]), ("no-doi", None))
        self.assertFalse(web.called("crossref.org/works/"))

    def test_a_real_doi_with_the_wrong_description_is_a_mismatch(self):
        self.web([("crossref.org/works/", crossref_one())])
        result = sources.check({"ref": "Müller & Schmidt (2019). Deep learning for climate "
                                       "adaptation. doi:" + ALPHAFOLD,
                                "title": "Deep learning for climate adaptation",
                                "authors": "Müller & Schmidt", "year": 2019})
        self.assertEqual(result["verdict"], "mismatch")
        self.assertIn("AlphaFold", result["reason"])
        self.assertEqual(result["short"], "title and authors differ from the DOI's record")

    def test_a_doi_nobody_knows_is_not_found(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404), ("://doi.org/", 404)])
        result = sources.check({"ref": "https://doi.org/10.1234/made-up"})
        self.assertEqual((result["verdict"], result["short"]), ("not-found", "the DOI does not exist"))
        self.assertTrue(result["reason"].startswith("The DOI 10.1234/made-up does not exist. "))

    def test_an_in_press_reference_is_not_a_wrong_year(self):
        self.web([("crossref.org/works/", crossref_one())])
        result = sources.check(dict(self.CLAIM, year="in press"))
        self.assertEqual((result["verdict"], result["match"]["year"]), ("ok", "not given"))

    def test_a_retracted_work_is_flagged_even_when_everything_matches(self):
        self.web([("crossref.org/works/", crossref_one(updated_by=RETRACTION))])
        self.assertEqual(sources.check(self.CLAIM)["verdict"], "retracted")

    def test_unreachable_registries_give_unknown(self):
        self.web([("crossref.org", unreachable()), ("datacite.org", unreachable())])
        self.assertEqual(sources.check(self.CLAIM)["verdict"], "unknown")

    def test_details_the_reference_text_does_not_contain_are_noted(self):
        self.web([("crossref.org/works/", crossref_one())])
        result = sources.check({"ref": "https://doi.org/" + ALPHAFOLD, "title": ALPHAFOLD_TITLE,
                                "authors": ["Jumper"], "year": 2021})
        self.assertEqual(result["verdict"], "ok")
        self.assertTrue(result["reason"].endswith(
            "(some details were not found in the reference text)"))

    def test_a_work_without_doi_is_found_by_title_and_author(self):
        self.web([("openalex.org/works?filter=title.search", openalex_list(openalex_work())),
                  ("crossref.org/works/", crossref_one())])
        result = sources.check({"title": ALPHAFOLD_TITLE, "authors": ["John Jumper"], "year": 2021})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "title search"))

    def test_a_short_main_title_with_the_print_year_finds_the_online_first_record(self):
        santamouris = "10.1016/j.solener.2012.07.003"
        long_title = ("Cooling the cities – A review of reflective and green roof mitigation "
                      "technologies to fight heat island and improve comfort in urban environments")
        self.web([("openalex.org/works?filter=title.search", openalex_list(
                      openalex_work(doi=santamouris, title=long_title,
                                    authors=("M. Santamouris",), year=2012))),
                  ("crossref.org/works/", crossref_one(doi=santamouris, title=long_title,
                                                        authors=(("Santamouris", "M."),),
                                                        year=2014))])
        result = sources.check({"title": "Cooling the cities", "authors": "Santamouris",
                                "year": 2014})
        self.assertEqual(result["verdict"], "ok")
        self.assertEqual(result["registry"]["doi"], santamouris)

    def test_a_same_titled_chapter_from_another_year_does_not_stand_in_for_a_book(self):
        chapter = "10.1007/978-3-531-18939-0_38"
        self.web([("openalex.org/works?filter=title.search", openalex_list(
                      openalex_work(doi=chapter, title="Qualitative Inhaltsanalyse",
                                    authors=("Philipp Mayring", "Thomas Fenzl"), year=2014,
                                    type_="book-chapter"))),
                  ("crossref.org/works/", crossref_one(doi=chapter, title="Qualitative Inhaltsanalyse",
                                                        authors=(("Mayring", "Philipp"),),
                                                        year=2014, type_="book-chapter"))])
        result = sources.check({"title": "Qualitative Inhaltsanalyse",
                                "authors": ["Mayring, Philipp"], "year": 2015})
        self.assertEqual((result["verdict"], result["doi_source"]), ("no-doi", None))
        self.assertNotIn("registry", result)
        self.assertIn(chapter, result["reason"])

    def test_a_reused_famous_title_by_other_authors_is_not_accepted(self):
        web = self.web([("openalex.org/works?filter=title.search", openalex_list(
            openalex_work(doi="10.9/other", title="Attention Is All You Need",
                          authors=("Maria Other",), year=2025)))])
        result = sources.check({"title": "Attention is all you need", "authors": ["Vaswani"],
                                "year": 2017})
        self.assertEqual(result["verdict"], "no-doi")
        self.assertIn("10.9/other", result["reason"])
        self.assertFalse(web.called("crossref.org/works/"))

    def test_the_crossref_fallback_searches_with_the_author_when_openalex_is_down(self):
        web = self.web([("openalex.org", unreachable()),
                        ("crossref.org/works?", crossref_list(crossref_msg())),
                        ("crossref.org/works/", crossref_one())])
        result = sources.check({"title": ALPHAFOLD_TITLE, "authors": ["John Jumper"], "year": 2021})
        self.assertEqual(result["verdict"], "ok")
        self.assertIn("query.author=Jumper", web.called("crossref.org/works?")[0])

    def test_no_title_search_service_answering_is_unknown_not_no_doi(self):
        self.web([("openalex.org", unreachable()), ("crossref.org", unreachable())])
        result = sources.check({"title": "Qualitative Sozialforschung", "authors": ["Flick"]})
        self.assertEqual(result["verdict"], "unknown")

    def test_an_openalex_record_without_doi_is_no_doi_with_its_id(self):
        web = self.web([("openalex.org/works?filter=title.search", openalex_list(
            openalex_work(doi=None, title="Qualitative Sozialforschung", authors=("Uwe Flick",),
                          year=2019, openalex_id="W123456")))])
        result = sources.check({"title": "Qualitative Sozialforschung", "authors": ["Flick, U."],
                                "year": 2019})
        self.assertEqual(result["verdict"], "no-doi")
        self.assertEqual(result["reason"],
                         "OpenAlex lists this work (W123456) without a DOI; confirm it by hand.")
        self.assertEqual(result["short"], "OpenAlex lists it without a DOI")
        self.assertFalse(web.called("crossref"))

    def test_a_record_with_doi_wins_over_its_duplicate_without(self):
        self.web([("openalex.org/works?filter=title.search", openalex_list(
                      openalex_work(doi=None), openalex_work())),
                  ("crossref.org/works/", crossref_one())])
        result = sources.check({"title": ALPHAFOLD_TITLE, "authors": ["Jumper"], "year": 2021})
        self.assertEqual((result["verdict"], result["registry"]["doi"]), ("ok", ALPHAFOLD))

    def test_no_doi_and_nothing_found_asks_for_a_check_by_hand(self):
        self.web(NOTHING_BY_TITLE)
        result = sources.check({"title": "Einführung in die qualitative Sozialforschung",
                                "authors": ["Flick"]})
        self.assertEqual((result["verdict"], result["short"]), ("no-doi", "no registry record found"))
        self.assertIn("Books, reports", result["reason"])

    def test_no_doi_and_no_title_asks_for_them_without_any_request(self):
        web = self.web([])
        result = sources.check({"ref": "Müller (2020), a talk I heard"})
        self.assertEqual(result["verdict"], "no-doi")
        self.assertIn("give its title and authors", result["reason"])
        self.assertEqual(web.calls, [])

    JOURNAL_CLAIM = {"ref": "Schneider, T., & Wu, L. (2021). Remote work and the hidden cost of "
                            "flexible schedules. Journal of Business Research, 131, 44–58.",
                     "title": "Remote work and the hidden cost of flexible schedules",
                     "authors": ["Schneider, T.", "Wu, L."], "year": 2021,
                     "journal": "Journal of Business Research"}
    JBR = {"results": [{"id": "https://openalex.org/S2764689644",
                        "display_name": "Journal of Business Research - Turk"},
                       {"id": "https://openalex.org/S93284759",
                        "display_name": "Journal of Business Research"}]}

    def test_an_article_missing_from_an_indexed_journal_is_not_found(self):
        web = self.web(NOTHING_BY_TITLE + [
            ("openalex.org/sources?", self.JBR),
            ("openalex.org/works?filter=primary_location", {"meta": {"count": 874}, "results": []})])
        result = sources.check(self.JOURNAL_CLAIM)
        self.assertEqual(result["verdict"], "not-found")
        self.assertIn("Journal of Business Research is indexed (874 works in 2021)", result["reason"])
        self.assertIn("It may be invented", result["reason"])
        self.assertNotIn("some details", result["reason"])
        count_url = urllib.parse.unquote(web.called("source.id")[0])
        self.assertIn("primary_location.source.id:S93284759,publication_year:2021", count_url)

    def test_a_journal_openalex_does_not_index_gives_no_doi(self):
        self.web(NOTHING_BY_TITLE + [("openalex.org/sources?", {"results": [
            {"id": "https://openalex.org/S1", "display_name": "Journal of Something Else"}]})])
        result = sources.check(self.JOURNAL_CLAIM)
        self.assertEqual(result["verdict"], "no-doi")
        self.assertIn("is not indexed in OpenAlex", result["reason"])

    def test_an_indexed_journal_without_works_that_year_gives_no_doi(self):
        self.web(NOTHING_BY_TITLE + [
            ("openalex.org/sources?", self.JBR),
            ("openalex.org/works?filter=primary_location", {"meta": {"count": 0}, "results": []})])
        self.assertEqual(sources.check(self.JOURNAL_CLAIM)["verdict"], "no-doi")

    def test_without_a_year_the_journal_is_not_looked_up(self):
        web = self.web(NOTHING_BY_TITLE)
        claim = {k: v for k, v in self.JOURNAL_CLAIM.items() if k != "year"}
        self.assertEqual(sources.check(claim)["verdict"], "no-doi")
        self.assertFalse(web.called("sources?"))


class PdfCheckTests(WebTestCase):
    PAGE_1 = ("Commentary on doi:10.5555/cited\n"
              "Highly accurate protein structure\nprediction with AlphaFold\n"
              "John Jumper, Richard Evans\nhttps://doi.org/10.1038/s41586-021-03819-2")

    def pdf(self, pages=None, error=None):
        mock = patch.object(sources, "pdf_pages", return_value=pages, side_effect=error)
        mock.start()
        self.addCleanup(mock.stop)

    def test_the_pdfs_own_doi_wins_over_a_cited_one_on_page_1(self):
        self.pdf([self.PAGE_1, "1 Introduction"])
        self.web([("crossref.org/works/10.5555/cited", crossref_one(doi="10.5555/cited",
                                                                title="Protein folding, a review")),
                  ("crossref.org/works/10.1038", crossref_one())])
        result = sources.check({"pdf": "thesis/papers/jumper.pdf"})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "pdf"))
        self.assertEqual(result["registry"]["doi"], ALPHAFOLD)

    def test_when_no_doi_on_the_pages_matches_the_title_search_takes_over(self):
        self.pdf(["Commentary on doi:10.5555/cited\nHighly accurate protein structure prediction"
                  " with AlphaFold", ""])
        web = self.web([("crossref.org/works/10.5555/cited", crossref_one(doi="10.5555/cited",
                                                                      title="Protein folding")),
                        ("openalex.org/works?filter=title.search", openalex_list(openalex_work())),
                        ("crossref.org/works/10.1038", crossref_one())])
        result = sources.check({"pdf": "x.pdf", "title": ALPHAFOLD_TITLE, "authors": ["Jumper"]})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "title search"))
        self.assertTrue(web.called("title.search"))

    def test_a_pdf_without_matching_doi_or_title_asks_for_them(self):
        self.pdf(["Commentary on doi:10.5555/cited", ""])
        self.web([("crossref.org/works/10.5555/cited", crossref_one(doi="10.5555/cited"))])
        result = sources.check({"pdf": "x.pdf"})
        self.assertEqual(result["verdict"], "no-doi")
        self.assertIn("give its title and authors", result["reason"])

    def test_a_short_main_title_is_matched_by_the_whole_title(self):
        grit = "10.1037/0022-3514.92.6.1087"
        grit_title = "Grit: Perseverance and passion for long-term goals"
        self.pdf([f"DOI: {grit}\nGrit: Perseverance and Passion for Long-Term Goals\n"
                  "Angela L. Duckworth", ""])
        self.web([("crossref.org/works/", crossref_one(doi=grit, title=grit_title))])
        result = sources.check({"pdf": "x.pdf"})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "pdf"))

    def test_a_cited_work_with_a_short_main_title_is_not_taken_for_the_pdf(self):
        self.pdf(["As shown by doi:10.1037/0022-3514.92.6.1087, grit predicts success.", ""])
        self.web([("crossref.org/works/", crossref_one(
            doi="10.1037/0022-3514.92.6.1087",
            title="Grit: Perseverance and passion for long-term goals"))])
        self.assertIsNone(sources.record_in_pdf("x.pdf"))

    def test_an_arxiv_pdf_is_found_by_the_identifier_arxiv_prints_on_page_1(self):
        self.pdf(["arXiv:1706.03762v7 [cs.CL] 2 Aug 2023\nAttention Is All You Need\n"
                  "Ashish Vaswani", ""])
        web = self.web([("crossref.org/works/", 404), ("datacite.org/dois/", datacite_one())])
        result = sources.check({"pdf": "thesis/papers/vaswani.pdf"})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "pdf"))
        self.assertEqual(result["registry"]["doi"], "10.48550/arxiv.1706.03762")
        self.assertEqual(web.called("datacite.org"),
                         ["https://api.datacite.org/dois/10.48550/arxiv.1706.03762"])

    def test_an_arxiv_link_in_a_reference_is_looked_up_as_its_datacite_doi(self):
        web = self.web([("crossref.org/works/", 404), ("datacite.org/dois/", datacite_one())])
        result = sources.check({"ref": "https://arxiv.org/abs/1706.03762v7"})
        self.assertEqual((result["verdict"], result["doi_source"]), ("ok", "ref"))
        self.assertEqual(web.called("datacite.org"),
                         ["https://api.datacite.org/dois/10.48550/arxiv.1706.03762"])

    def test_an_unreadable_pdf_is_no_doi_with_the_reason(self):
        self.pdf(error=sources.PdfError(3, "scanned PDF, no text to read"))
        web = self.web([])
        result = sources.check({"pdf": "scan.pdf"})
        self.assertEqual(result["verdict"], "no-doi")
        self.assertIn("scanned PDF, no text to read", result["reason"])
        self.assertIn("give its title and authors", result["reason"])
        self.assertEqual(web.calls, [])


# --------------------------------------------------------------------------
# details
# --------------------------------------------------------------------------

class DetailsTests(WebTestCase):
    def test_openalex_supplies_the_abstract_and_a_free_full_text_link(self):
        self.web([("crossref.org/works/", crossref_one()),
                  ("openalex.org/works/doi:", openalex_work(abstract="Proteins are essential",
                                                           oa_url="https://example.org/a.pdf"))])
        rec = sources.details(ALPHAFOLD)
        self.assertEqual(rec["abstract"], "Proteins are essential")
        self.assertEqual(rec["free_fulltext_url"], "https://example.org/a.pdf")
        self.assertNotIn("abstract_source", rec)

    def test_the_registry_abstract_is_kept_over_openalex(self):
        self.web([("crossref.org/works/", crossref_one(abstract="<p>From Crossref</p>")),
                  ("openalex.org/works/doi:", openalex_work(abstract="From OpenAlex"))])
        self.assertEqual(sources.details(ALPHAFOLD)["abstract"], "From Crossref")

    def test_openalex_can_mark_a_work_retracted(self):
        self.web([("crossref.org/works/", crossref_one()),
                  ("openalex.org/works/doi:", openalex_work(retracted=True))])
        self.assertTrue(sources.details(ALPHAFOLD)["retracted"])

    def test_an_openalex_failure_keeps_the_registry_answer(self):
        self.web([("crossref.org/works/", crossref_one()), ("openalex.org", unreachable())])
        rec = sources.details(ALPHAFOLD)
        self.assertEqual(rec["status"], "resolved")
        self.assertIn("openalex_error", rec)

    def test_an_unresolved_doi_comes_back_unchanged(self):
        web = self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404),
                        ("://doi.org/", 404)])
        self.assertEqual(sources.details("10.1234/nope")["status"], "absent")
        self.assertFalse(web.called("openalex.org"))


# --------------------------------------------------------------------------
# add: into thesis/sources.md
# --------------------------------------------------------------------------

TEMPLATE = "# My sources\n\nIntro from the template.\n"


class AddTests(WebTestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "thesis").mkdir()
        (self.root / "kit" / "templates").mkdir(parents=True)
        (self.root / "kit" / "templates" / "sources.md").write_text(TEMPLATE, encoding="utf-8")
        self.file = self.root / "thesis" / "sources.md"

    def add(self, items, found_via="Consensus"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sources.add(items, found_via, root=self.root)
        return code, out.getvalue()

    def existing(self, *entries):
        self.file.write_text(TEMPLATE + "\n" + "\n".join(entries), encoding="utf-8")

    def test_a_checked_work_is_written_in_the_entry_format_into_a_new_file(self):
        self.web([("crossref.org/works/", crossref_one()),
                  ("openalex.org/works/doi:", openalex_work(oa_url="https://example.org/a.pdf"))])
        code, out = self.add([{"ref": ALPHAFOLD_REF, "title": ALPHAFOLD_TITLE,
                               "authors": "Jumper et al.", "year": 2021}])
        self.assertEqual(code, 0)
        self.assertEqual(self.file.read_text(encoding="utf-8"), TEMPLATE + f"""
### Jumper & Evans (2021) · Highly accurate protein structure prediction with AlphaFold
- Cite as: [@jumper2021]
- Status: unchecked
- DOI: 10.1038/s41586-021-03819-2
- Registry check: ok · {TODAY}
- Published in: Nature 596(7873), 583–589
- Found via: Consensus
- Free full text: https://example.org/a.pdf
- In my own words:
- Notes:
""")
        self.assertEqual(out, "added 1 · already there 0\nadded (unchecked): Jumper & Evans (2021) · "
                              "Highly accurate protein structure prediction with AlphaFold [@jumper2021]\n")

    def test_a_work_without_registry_record_keeps_the_reference_as_given(self):
        self.web(NOTHING_BY_TITLE)
        code, out = self.add([{"ref": "Flick, U. (2019).  Qualitative Sozialforschung.\nRowohlt.",
                               "title": "Qualitative Sozialforschung", "authors": ["Flick, U."],
                               "year": 2019, "journal": ""}], found_via="my supervisor")
        entry = self.file.read_text(encoding="utf-8")[len(TEMPLATE):]
        self.assertEqual(entry, f"""
### Flick (2019) · Qualitative Sozialforschung
- Cite as: [@flick2019]
- Status: unchecked
- Registry check: no-doi: no registry record found · {TODAY}
- Found via: my supervisor
- Reference as given: Flick, U. (2019). Qualitative Sozialforschung. Rowohlt.
- In my own words:
- Notes:
""")
        self.assertEqual(out.splitlines()[1:3], [
            "added (unchecked): Flick (2019) · Qualitative Sozialforschung [@flick2019]",
            'Flick (2019) "Qualitative Sozialforschung": no-doi — No DOI found, and no registry '
            "record with this title and these authors. Books, reports, laws and web pages often have "
            "no DOI; the student confirms such a source by hand."])

    def test_found_via_is_left_out_when_no_tool_or_person_was_named(self):
        self.web(NOTHING_BY_TITLE)
        self.add([{"title": "Qualitative Sozialforschung", "authors": ["Flick, U."], "year": 2019}],
                 found_via="")
        entry = sources.read_entries(self.file.read_text(encoding="utf-8"))[0]
        self.assertNotIn("found via", entry["fields"])

    def test_a_preprint_says_so_in_the_entry_and_the_report(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", datacite_one()),
                  ("openalex.org/works/doi:", 404)])
        _, out = self.add([{"ref": "arXiv:1706.03762 https://doi.org/10.48550/arXiv.1706.03762"}])
        entry = sources.read_entries(self.file.read_text(encoding="utf-8"))[0]
        self.assertEqual(entry["fields"]["published in"], "arXiv (preprint)")
        self.assertEqual(out.splitlines()[1:], [
            "added (unchecked): Vaswani (2017) · Attention Is All You Need [@vaswani2017]",
            'Vaswani (2017) "Attention Is All You Need": preprint, not peer-reviewed; '
            "a journal version may exist"])

    def test_a_mismatch_keeps_the_reference_as_given_next_to_the_registry_record(self):
        self.web([("crossref.org/works/", crossref_one()), ("openalex.org/works/doi:", 404)])
        ref = "Müller & Schmidt (2019). Deep learning for climate adaptation. doi:" + ALPHAFOLD
        self.add([{"ref": ref, "title": "Deep learning for climate adaptation",
                   "authors": "Müller & Schmidt", "year": 2019}])
        entry = sources.read_entries(self.file.read_text(encoding="utf-8"))[0]
        self.assertEqual(entry["title"], ALPHAFOLD_TITLE)
        self.assertEqual(entry["fields"]["reference as given"], ref)

    def test_keys_get_a_suffix_when_taken_in_the_file_or_in_this_run(self):
        self.existing("### Müller (2021) · An older paper\n- Cite as: [@muller2021]\n")
        self.web(NOTHING_BY_TITLE)
        items = [{"ref": f"Müller, J. (2021). {title}.", "title": title, "authors": ["Müller, J."],
                  "year": 2021} for title in ("Führung im Wandel", "Arbeit und Zeit")]
        self.add(items)
        keys = [e["key"] for e in sources.read_entries(self.file.read_text(encoding="utf-8"))]
        self.assertEqual(keys, ["muller2021", "muller2021a", "muller2021b"])

    def test_keys_stay_unique_after_all_26_letters_are_used(self):
        taken = {"anon2020"} | {"anon2020" + c for c in "abcdefghijklmnopqrstuvwxyz"}
        self.assertEqual(sources.make_key("李", 2020, taken), "anona2020")
        self.assertEqual(sources.make_key("李", 2020, taken | {"anona2020"}), "anona2020a")

    def test_a_work_already_there_is_not_added_twice(self):
        self.existing("### Jumper et al. (2021) · Highly accurate protein structure prediction "
                      "with AlphaFold\n- Cite as: [@jumper2021]\n- Status: unchecked\n"
                      f"- DOI: {ALPHAFOLD}\n",
                      "### Flick (2019) · Qualitative Sozialforschung\n- Cite as: [@flick2019]\n"
                      "- Status: checked · 2026-01-02\n")
        before = self.file.read_text(encoding="utf-8")
        self.web([("crossref.org/works/", crossref_one())] + NOTHING_BY_TITLE)
        code, out = self.add([{"ref": "doi:" + ALPHAFOLD},
                              {"ref": "Flick, U. (2019). Qualitative Sozialforschung.",
                               "title": "Qualitative Sozialforschung", "authors": ["Flick, U."],
                               "year": 2019}])
        self.assertEqual(code, 0)
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)
        self.assertEqual(out.splitlines(), [
            "added 0 · already there 2",
            'Jumper & Evans (2021) "Highly accurate protein structure prediction with AlphaFold": '
            "already there as [@jumper2021]",
            'Flick (2019) "Qualitative Sozialforschung": already there as [@flick2019]'])

    def test_another_edition_or_another_doi_is_a_work_of_its_own(self):
        self.existing("### Mayring (2015) · Qualitative Inhaltsanalyse\n- Cite as: [@mayring2015]\n"
                      "- Status: unchecked\n",
                      "### Döring (2016) · Forschungsmethoden\n- Cite as: [@doring2016]\n"
                      "- Status: unchecked\n- DOI: 10.1007/978-3-642-41089-5\n")
        self.web(NOTHING_BY_TITLE + [
            ("crossref.org/works/", crossref_one(doi="10.1007/978-3-662-64762-2",
                                                 title="Forschungsmethoden",
                                                 authors=(("Döring", "Nicola"),), year=2023)),
            ("openalex.org/works/doi:", 404)])
        _, out = self.add([{"title": "Qualitative Inhaltsanalyse", "authors": ["Mayring, P."],
                            "year": 2022},
                           {"ref": "doi:10.1007/978-3-662-64762-2"}])
        keys = [e["key"] for e in sources.read_entries(self.file.read_text(encoding="utf-8"))]
        self.assertEqual(keys, ["mayring2015", "doring2016", "mayring2022", "doring2023"])
        self.assertTrue(out.startswith("added 2 · already there 0"))

    def test_a_hand_written_label_is_read_like_the_scripts_own(self):
        self.existing("### Flick und Kardorff (2019) · Qualitative Forschung\n- Status: unchecked\n")
        self.web(NOTHING_BY_TITLE)
        _, out = self.add([{"title": "Qualitative Forschung",
                            "authors": ["Flick, U.", "Kardorff, E."], "year": 2019}])
        self.assertEqual(out.splitlines(), [
            "added 0 · already there 1",
            'Flick & Kardorff (2019) "Qualitative Forschung": already there (line 5, no Cite as yet)'])

    def test_the_same_work_twice_in_one_run_is_added_once(self):
        self.web([("crossref.org/works/", crossref_one()), ("openalex.org/works/doi:", 404)])
        _, out = self.add([{"ref": ALPHAFOLD_REF}, {"ref": "https://doi.org/" + ALPHAFOLD}])
        self.assertTrue(out.startswith("added 1 · already there 1"))

    def test_a_dropped_work_is_reported_with_the_reason_it_was_dropped(self):
        self.existing(f"### Jumper et al. (2021) · AlphaFold\n- Cite as: [@jumper2021]\n"
                      f"- Status: dropped · 2026-01-10 · off topic\n- DOI: {ALPHAFOLD}\n")
        self.web([("crossref.org/works/", crossref_one())])
        _, out = self.add([{"ref": ALPHAFOLD_REF}])
        self.assertIn(": dropped before: off topic", out)

    def test_a_retracted_work_is_added_as_dropped(self):
        self.web([("crossref.org/works/", crossref_one(updated_by=RETRACTION)),
                  ("openalex.org/works/doi:", 404)])
        _, out = self.add([{"ref": ALPHAFOLD_REF}])
        entry = sources.read_entries(self.file.read_text(encoding="utf-8"))[0]
        self.assertEqual(entry["fields"]["status"], f"dropped · {TODAY} · retracted")
        self.assertEqual(entry["fields"]["registry check"],
                         f"retracted: the registry lists a retraction · {TODAY}")
        self.assertTrue(out.splitlines()[1].startswith("added (dropped): Jumper & Evans (2021) · "))
        self.assertIn(": retracted — ", out.splitlines()[2])

    def test_a_pdf_is_recorded_relative_to_the_thesis_folder(self):
        pdf = str(self.root / "thesis" / "papers" / "jumper.pdf")
        self.web([("crossref.org/works/10.5555/cited", crossref_one(doi="10.5555/cited",
                                                                   title="Protein folding")),
                  ("crossref.org/works/", crossref_one()), ("openalex.org/works/doi:", 404)])
        with patch.object(sources, "pdf_pages", return_value=[PdfCheckTests.PAGE_1, ""]):
            _, out = self.add([{"pdf": pdf}])
        entry = sources.read_entries(self.file.read_text(encoding="utf-8"))[0]
        self.assertEqual(entry["fields"]["pdf"], "papers/jumper.pdf")
        self.assertEqual(entry["doi"], ALPHAFOLD)
        self.assertEqual(out.splitlines()[1], "added (unchecked): Jumper & Evans (2021) · Highly accurate "
                                              "protein structure prediction with AlphaFold [@jumper2021] · "
                                              "papers/jumper.pdf")

    def test_a_work_without_any_title_is_not_added(self):
        self.web([])
        with patch.object(sources, "pdf_pages",
                          side_effect=sources.PdfError(3, "scanned PDF, no text to read")):
            _, out = self.add([{"pdf": "thesis/papers/scan.pdf"}])
        self.assertFalse(self.file.exists())
        self.assertIn('"thesis/papers/scan.pdf": not added — The PDF could not be read', out)

    def test_nothing_is_written_when_no_registry_could_be_reached(self):
        self.web([("crossref.org", unreachable()), ("datacite.org", unreachable())])
        code, out = self.add([{"ref": ALPHAFOLD_REF}])
        self.assertEqual(code, 1)
        self.assertFalse(self.file.exists())
        self.assertIn("nothing added", out)

    def write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8-sig")
        return str(path)

    def test_bibtex_exports_are_read_with_the_entry_as_the_reference(self):
        bib = self.write("export.bib", """@comment{jabref-meta: x}
@article{jumper2021,
  title = {Highly accurate protein structure prediction with {AlphaFold}},
  author = {Jumper, John and Evans, Richard and M{\\"u}ller, Anna},
  journal = {Nature},
  year = {2021},
  doi = {10.1038/s41586-021-03819-2},
}

@book{flick2019, title = "Qualitative Sozialforschung", author = {Flick, Uwe},
  year = 2019, publisher = {Rowohlt}}
""")
        first, second = sources.read_items(bib)
        self.assertEqual({k: v for k, v in first.items() if k != "ref"},
                         {"title": ALPHAFOLD_TITLE, "authors": ["Jumper, John", "Evans, Richard",
                                                                "Müller, Anna"],
                          "year": "2021", "journal": "Nature"})
        self.assertTrue(first["ref"].startswith("@article{jumper2021,"))
        self.assertEqual(sources.dois_in(first["ref"]), [ALPHAFOLD])
        self.assertEqual((second["title"], second["authors"], second["year"], second["journal"]),
                         ("Qualitative Sozialforschung", ["Flick, Uwe"], "2019", ""))
        self.assertEqual(sources.dois_in(second["ref"]), [])

    def test_bibtex_accents_nested_braces_and_quoted_values_are_read(self):
        bib = self.write("mendeley.bib", """@article{m2019,
  author = {M{\\"{u}}ller, Jan and Sch{\\"{o}}n, Karl},
  journal = {Zeitschrift f{\\"{u}}r Arbeitswissenschaft},
  title = {{Homeoffice und Zufriedenheit: Eine {\\"{U}}bersicht}},
  year = {2019}
}
@book{s2018, title = "Zur {\\"A}sthetik der Gro{\\ss}stadt", author = "Schr{\\"o}der, A.",
  year = 2018}
""")
        first, second = sources.read_items(bib)
        self.assertEqual({k: v for k, v in first.items() if k != "ref"},
                         {"title": "Homeoffice und Zufriedenheit: Eine Übersicht",
                          "authors": ["Müller, Jan", "Schön, Karl"], "year": "2019",
                          "journal": "Zeitschrift für Arbeitswissenschaft"})
        self.assertEqual((second["title"], second["authors"]),
                         ("Zur Ästhetik der Großstadt", ["Schröder, A."]))

    def test_a_braced_organisation_is_one_author(self):
        bib = self.write("org.bib", "@report{nice, author = {{National Institute for Health and "
                                    "Care Excellence} and Smith, J.}, title = {Guideline}, "
                                    "year = {2022}}")
        item = sources.read_items(bib)[0]
        self.assertEqual(item["authors"],
                         [{"name": "National Institute for Health and Care Excellence"}, "Smith, J."])
        self.assertEqual(sources.claimed_families(item["authors"]),
                         ["National Institute for Health and Care Excellence", "Smith"])

    def test_ris_exports_are_read_with_the_entry_as_the_reference(self):
        ris = self.write("export.ris", "TY  - JOUR\nAU  - Jumper, John\nAU  - Evans, Richard\n"
                         f"TI  - {ALPHAFOLD_TITLE}\nJO  - Nature\nPY  - 2021/08/26\n"
                         f"DO  - {ALPHAFOLD}\nER  - \n\n"
                         "TY  - BOOK\nAU  - Flick, Uwe\nT1  - Qualitative Sozialforschung\n"
                         "PY  - 2019\nER  - \n")
        first, second = sources.read_items(ris)
        self.assertEqual({k: v for k, v in first.items() if k != "ref"},
                         {"title": ALPHAFOLD_TITLE, "authors": ["Jumper, John", "Evans, Richard"],
                          "year": "2021", "journal": "Nature"})
        self.assertEqual(sources.dois_in(first["ref"]), [ALPHAFOLD])
        self.assertEqual((second["title"], second["year"]), ("Qualitative Sozialforschung", "2019"))

    def test_the_doi_field_of_an_export_beats_a_doi_in_its_link_or_abstract(self):
        bib = self.write("z.bib", f"@article{{a,\n  title = {{{ALPHAFOLD_TITLE}}},\n"
                         f"  url = {{https://www.nature.com/doi/{ALPHAFOLD}?casa_token=Xy:z}},\n"
                         f"  doi = {{{ALPHAFOLD}}},\n  author = {{Jumper, John}},\n  year = {{2021}},\n}}")
        ris = self.write("z.ris", f"TY  - JOUR\nTI  - {ALPHAFOLD_TITLE}\nAU  - Jumper, John\n"
                         "AB  - Preregistered at https://doi.org/10.17605/OSF.IO/HV3FA.\n"
                         f"PY  - 2021\nDO  - {ALPHAFOLD}\nER  - \n")
        web = self.web([("crossref.org/works/10.1038", crossref_one())])
        for item in sources.read_items(bib) + sources.read_items(ris):
            result = sources.check(item)
            self.assertEqual((result["verdict"], result["registry"]["doi"]), ("ok", ALPHAFOLD))
        self.assertEqual(len(web.calls), 2)

    def test_a_bibtex_export_can_be_added_directly(self):
        bib = self.write("one.bib", f"@article{{a, title={{{ALPHAFOLD_TITLE}}}, "
                                    f"author={{Jumper, John}}, year={{2021}}, doi={{{ALPHAFOLD}}}}}")
        self.web([("crossref.org/works/", crossref_one()), ("openalex.org/works/doi:", 404)])
        code, out = self.add(sources.read_items(bib), found_via="Zotero")
        self.assertEqual((code, out.splitlines()[0]), (0, "added 1 · already there 0"))


# --------------------------------------------------------------------------
# pdf: text from a PDF
# --------------------------------------------------------------------------

class PdfCommandTests(unittest.TestCase):
    PAGES = ["Title page\ndoi:10.1/x", "Intro about heat islands.",
             "Methods\n\nWe measured albedo\non roofs.\n\nMore text.", "Results: Albedo rose."]

    def run_pdf(self, *args, pages=PAGES):
        def extract(path, first, last):
            return len(pages), pages[first - 1:last]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"%PDF-1.4")
            out = io.StringIO()
            with patch.object(sources, "_extract", side_effect=extract), \
                    contextlib.redirect_stdout(out):
                code = sources.main(["pdf", str(path), *args])
        return code, out.getvalue()

    def test_the_first_two_pages_are_printed_by_default(self):
        code, out = self.run_pdf()
        self.assertEqual(code, 0)
        self.assertEqual(out, "pages: 4\n--- PDF page 1 ---\nTitle page\ndoi:10.1/x\n"
                              "--- PDF page 2 ---\nIntro about heat islands.\n")

    def test_pages_picks_a_range(self):
        _, out = self.run_pdf("--pages", "3-4")
        self.assertIn("--- PDF page 3 ---", out)
        self.assertIn("--- PDF page 4 ---\nResults: Albedo rose.", out)
        self.assertNotIn("--- PDF page 1 ---", out)

    def test_find_prints_matching_paragraphs_with_their_page(self):
        _, out = self.run_pdf("--find", "albedo|heat island")
        self.assertEqual(out.splitlines(), ["PDF page 2: Intro about heat islands.",
                                            "PDF page 3: We measured albedo on roofs.",
                                            "PDF page 4: Results: Albedo rose.", "3 matches"])

    def test_find_sees_words_split_at_a_ligature(self):
        _, out = self.run_pdf("--find", "significance|findings",
                              pages=["statistical signifi cance\n\nnew ﬁ ndings"])
        self.assertEqual(out.splitlines(), ["PDF page 1: statistical signifi cance",
                                            "PDF page 1: new ﬁ ndings", "2 matches"])

    def test_a_path_as_sources_md_gives_it_is_found_in_the_thesis_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "thesis" / "papers").mkdir(parents=True)
            (Path(tmp) / "thesis" / "papers" / "chen.pdf").write_bytes(b"%PDF-1.4")
            with patch.object(sources, "REPO", Path(tmp)), \
                    patch.object(sources, "_extract", return_value=(1, ["Albedo of roofs"])):
                self.assertEqual(sources.pdf_pages("papers/chen.pdf"), ["Albedo of roofs"])

    def test_find_shows_at_most_20_matches(self):
        _, out = self.run_pdf("--find", "roof", pages=["a green roof\n" * 25])
        lines = out.splitlines()
        self.assertEqual(len(lines), 21)
        self.assertEqual(lines[-1], "25 matches, showing 20")

    def test_a_scanned_pdf_exits_3(self):
        code, out = self.run_pdf(pages=[" \n", ""])
        self.assertEqual((code, out.strip()), (3, "scanned PDF, no text to read"))

    def test_without_any_pdf_reader_it_exits_4_with_install_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            path.write_bytes(b"%PDF-1.4")
            out = io.StringIO()
            with patch.object(sources.sys, "platform", "linux"), \
                    patch.dict(sys.modules, {"pypdf": None}), contextlib.redirect_stdout(out):
                code = sources.main(["pdf", str(path)])
        self.assertEqual(code, 4)
        self.assertIn("python3 -m pip install --target .tools/python pypdf", out.getvalue())
        self.assertIn("py -3 -m pip install --target .tools/python pypdf", out.getvalue())

    def test_a_missing_file_exits_1(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(sources.main(["pdf", "no/such/file.pdf"]), 1)


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------

class CommandLineTests(WebTestCase):
    def run_main(self, argv, stdin=""):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), patch.object(sys, "stdin", io.StringIO(stdin)):
            code = sources.main(argv)
        return code, out.getvalue()

    def test_find_exits_1_when_no_service_answers(self):
        self.web([("crossref.org", unreachable()), ("openalex.org", unreachable())])
        code, out = self.run_main(["find", "x"])
        self.assertEqual((code, json.loads(out)), (1, {"ranked_by": None, "works": []}))

    def test_find_prints_the_ranking_service_and_the_works(self):
        self.web([("openalex.org/works?search", openalex_list(openalex_work()))])
        code, out = self.run_main(["find", "x"])
        result = json.loads(out)
        self.assertEqual((code, result["ranked_by"]), (0, "openalex"))
        self.assertEqual(result["works"][0]["doi"], ALPHAFOLD)

    def test_find_exits_0_when_the_services_answer_with_nothing(self):
        self.web([("openalex.org/works?search", openalex_list())])
        code, out = self.run_main(["find", "x"])
        self.assertEqual((code, json.loads(out)), (0, {"ranked_by": "openalex", "works": []}))

    def test_find_prints_one_compact_line_per_work(self):
        self.web([("openalex.org/works?search", openalex_list(openalex_work(
            authors=("John Jumper", "Richard Evans", "Alexander Pritzel", "Tim Green"))))])
        code, out = self.run_main(["find", "x"])
        work = json.loads(out)["works"][0]
        self.assertEqual(len(out.strip().splitlines()), 3)
        self.assertEqual(work["authors"], "Jumper, Evans, Pritzel et al.")
        self.assertEqual(set(work), {"doi", "title", "authors", "year", "venue", "type",
                                     "cited_by_count"})

    def test_check_reads_stdin_and_a_mismatch_still_exits_0(self):
        self.web([("crossref.org/works/", crossref_one())])
        claim = json.dumps([{"ref": "doi:" + ALPHAFOLD, "title": "Something else entirely"}])
        code, out = self.run_main(["check", "-"], stdin=claim)
        self.assertEqual((code, json.loads(out)[0]["verdict"]), (0, "mismatch"))

    def test_check_exits_1_when_the_registries_cannot_be_asked(self):
        self.web([("crossref.org", unreachable()), ("datacite.org", unreachable())])
        code, _ = self.run_main(["check", "-"], stdin=json.dumps([{"ref": ALPHAFOLD}]))
        self.assertEqual(code, 1)

    def test_a_claim_with_malformed_authors_does_not_stop_the_other_checks(self):
        self.web(NOTHING_BY_TITLE + [("crossref.org/works/", crossref_one())])
        claims = [{"authors": 5}, {"title": "Attention is all you need", "authors": True},
                  {"ref": "doi:" + ALPHAFOLD}]
        _, out = self.run_main(["check", "-"], stdin=json.dumps(claims))
        verdicts = [r["verdict"] for r in json.loads(out)]
        self.assertEqual((len(verdicts), verdicts[0], verdicts[2]), (3, "no-doi", "ok"))

    def test_add_needs_no_found_via(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / "thesis").mkdir()
        with patch.object(sources, "REPO", root), patch.object(sources, "add", return_value=0) as add:
            code, _ = self.run_main(["add", "-"], stdin='[{"ref": "doi:10.1/x"}]')
        self.assertEqual(code, 0)
        add.assert_called_once_with([{"ref": "doi:10.1/x"}], "")

    def test_the_script_runs_as_a_program(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "details", "not-a-doi"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)[0]["status"], "invalid")

    def test_input_and_output_are_utf8_whatever_the_terminal_says(self):
        item = json.dumps([{"ref": "Müller, J. (2020). Führung im Wandel."}], ensure_ascii=False)
        result = subprocess.run([sys.executable, str(SCRIPT), "check", "-"],
                                input=("﻿" + item).encode("utf-8"), capture_output=True,
                                env=dict(os.environ, PYTHONIOENCODING="ascii"), check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Führung", result.stdout.decode("utf-8"))


# --------------------------------------------------------------------------
# Live services (opt-in) and macOS's PDF reader
# --------------------------------------------------------------------------

@unittest.skipUnless(os.environ.get("THESIS_KIT_NETWORK_TESTS"),
                     "live test: set THESIS_KIT_NETWORK_TESTS=1 to run against the real services")
class LiveTests(unittest.TestCase):
    def test_a_real_doi_resolves_and_a_made_up_one_does_not(self):
        self.assertEqual(sources.lookup(ALPHAFOLD)["status"], "resolved")
        self.assertEqual(sources.lookup("10.1234/thesis-kit-made-up")["status"], "absent")

    def test_a_live_search_returns_distinct_citable_works(self):
        works, ranked_by = sources.search("green roof cooling urban heat island", n=8)
        self.assertIn(ranked_by, ("openalex", "crossref"))     # crossref while OpenAlex is down
        self.assertTrue(works)
        keys = [sources.title_key(w["title"]) for w in works]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(isinstance(w["cited_by_count"], int) for w in works))


def tiny_pdf(lines):
    """A one-page PDF with uncompressed text, written by hand."""
    content = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({line}) '" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


@unittest.skipUnless(sys.platform == "darwin", "macOS's own PDF reader")
class MacPdfTests(unittest.TestCase):
    def test_the_pdf_command_reads_text_with_pdfkit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "green roofs.pdf"
            path.write_bytes(tiny_pdf(["Green roofs cool cities", "doi:10.1234/green.2020.1"]))
            run = [sys.executable, str(SCRIPT), "pdf", str(path)]
            printed = subprocess.run(run, capture_output=True, text=True, check=False)
            found = subprocess.run(run + ["--find", "COOL"], capture_output=True, text=True,
                                   check=False)
            self.assertEqual(sources.dois_in("\n".join(sources.pdf_pages(str(path), 1, 2))),
                             ["10.1234/green.2020.1"])
        self.assertEqual(printed.returncode, 0, printed.stdout + printed.stderr)
        self.assertEqual(printed.stdout.splitlines()[:2], ["pages: 1", "--- PDF page 1 ---"])
        self.assertIn("doi:10.1234/green.2020.1", printed.stdout)
        self.assertEqual(found.stdout.splitlines(), ["PDF page 1: Green roofs cool cities",
                                                     "1 match"])


if __name__ == "__main__":
    unittest.main()
