"""Tests for kit/scripts/sources.py.

No network: every request is answered by a fake registry, and a request the
test did not expect fails the test. Run from the repository root:

    python3 -m unittest discover -s tests

Two live tests against the real services run only when
THESIS_KIT_NETWORK_TESTS=1 is set.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "kit" / "scripts" / "sources.py"
_spec = importlib.util.spec_from_file_location("sources", SCRIPT)
sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sources)

ALPHAFOLD = "10.1038/s41586-021-03819-2"


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
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.addCleanup(stack.close)
        return fake


def unreachable():
    return urllib.error.URLError("connection refused")


# --------------------------------------------------------------------------
# Sample registry answers
# --------------------------------------------------------------------------

def crossref_msg(doi=ALPHAFOLD, title="Highly accurate protein structure prediction with AlphaFold",
                 authors=(("Jumper", "John"), ("Evans", "Richard")), year=2021, venue="Nature",
                 type_="journal-article", publisher="Springer Science and Business Media LLC",
                 updated_by=None, abstract=None, **extra):
    msg = {"DOI": doi, "title": [title] if title else [],
           "author": [{"family": f, "given": g} for f, g in authors],
           "issued": {"date-parts": [[year]]}, "container-title": [venue] if venue else [],
           "type": type_, "publisher": publisher, "volume": "596", "issue": "7873",
           "page": "583-589"}
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


def openalex_work(doi=ALPHAFOLD, title="Highly accurate protein structure prediction with AlphaFold",
                  authors=("John Jumper", "Richard Evans"), year=2021, type_="article",
                  venue="Nature", retracted=False, abstract=None, oa_url=None):
    inverted = {}
    for position, word in enumerate((abstract or "").split()):
        inverted.setdefault(word, []).append(position)
    return {"doi": f"https://doi.org/{doi}" if doi else None, "title": title,
            "authorships": [{"author": {"display_name": a}} for a in authors],
            "publication_year": year, "type": type_, "is_retracted": retracted,
            "primary_location": {"source": {"display_name": venue}},
            "abstract_inverted_index": inverted or None,
            "open_access": {"oa_url": oa_url}, "cited_by_count": 100}


def openalex_list(*works):
    return {"meta": {}, "results": list(works)}


RETRACTION = [{"DOI": "10.1016/s0140-6736(10)60175-4", "type": "retraction"}]
CORRECTION = [{"DOI": "10.1016/s0140-6736(04)15715-2", "type": "correction"}]


# --------------------------------------------------------------------------
# DOIs and text
# --------------------------------------------------------------------------

class DoiTests(WebTestCase):
    def test_resolver_prefixes_case_and_trailing_punctuation_are_removed(self):
        self.assertEqual(sources.bare_doi("https://doi.org/10.1038/ABC"), "10.1038/abc")
        self.assertEqual(sources.bare_doi("http://dx.doi.org/10.5/Y"), "10.5/y")
        self.assertEqual(sources.bare_doi("doi: 10.1/X."), "10.1/x")

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
# HTTPS certificates
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


# --------------------------------------------------------------------------
# HTTP: retries and rate limits
# --------------------------------------------------------------------------

class FetchTests(WebTestCase):
    URL = "https://api.crossref.org/works/10.1/x"

    def test_404_raises_not_found_without_retrying(self):
        web = self.web([("crossref", 404)])
        with self.assertRaises(sources.NotFound):
            sources.fetch_json(self.URL)
        self.assertEqual(len(web.calls), 1)

    def test_rate_limit_is_waited_out_once_as_the_service_asks(self):
        self.web([("crossref", [(429, {"Retry-After": "7"}, {}), {"ok": True}])])
        self.assertEqual(sources.fetch_json(self.URL), {"ok": True})
        self.assertEqual(self.sleeps, [7.0])

    def test_rate_limit_wait_is_capped_at_45_seconds(self):
        self.web([("crossref", [(503, {"Retry-After": "600"}, {}), {"ok": True}])])
        sources.fetch_json(self.URL)
        self.assertEqual(self.sleeps, [45.0])

    def test_rate_limit_reported_in_a_json_body_is_honoured(self):
        self.web([("openalex", [{"error": "Rate limit exceeded", "retryAfter": 3}, {"ok": True}])])
        self.assertEqual(sources.fetch_json("https://api.openalex.org/works?search=x"), {"ok": True})
        self.assertEqual(self.sleeps, [3.0])

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

    def test_both_registries_saying_no_is_absent(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404)])
        self.assertEqual(sources.lookup("10.1234/abc")["status"], "absent")

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
# search (the `find` command)
# --------------------------------------------------------------------------

class SearchTests(WebTestCase):
    def test_non_works_and_weak_records_are_filtered_out(self):
        good = crossref_msg(doi="10.1/good", title="Green roofs cool cities")
        junk = [
            crossref_msg(doi="10.1/rev", title="Review for: Green roofs cool cities"),
            crossref_msg(doi="10.1/paper/v1/review2", title="Referee comments"),
            crossref_msg(doi="10.1/f1000", title="Faculty Opinions recommendation of Green roofs"),
            crossref_msg(doi="10.1/anon", title="A paper nobody wrote", authors=()),
            crossref_msg(doi="10.59350/blog", title="A blog post", venue="",
                         publisher="Front Matter", type_="posted-content"),
            crossref_msg(doi="10.1/mononym", title="A lonely note", authors=(("Pi", ""),),
                         venue="", type_="posted-content"),
            crossref_msg(doi="10.1/retracted", title="Retracted study", updated_by=RETRACTION),
        ]
        self.web([("crossref.org/works?", crossref_list(good, *junk)),
                  ("openalex.org/works?", openalex_list())])
        works, reached = sources.search("green roofs", n=5)
        self.assertEqual([w["doi"] for w in works], ["10.1/good"])
        self.assertIn("crossref", reached)

    def test_a_record_without_venue_but_with_several_authors_is_kept(self):
        rec = crossref_msg(doi="10.1/preprint", title="An honest preprint", venue="",
                           type_="posted-content")
        self.web([("crossref.org/works?", crossref_list(rec)),
                  ("openalex.org/works?", openalex_list())])
        self.assertEqual(len(sources.search("x", n=5)[0]), 1)

    def test_the_journal_version_replaces_its_preprint(self):
        preprint = crossref_msg(doi="10.2139/ssrn.1", type_="posted-content", venue="")
        journal = crossref_msg(doi="10.1016/j.x.1")
        for order in ([preprint, journal], [journal, preprint]):
            with self.subTest(first=order[0]["DOI"]):
                self.web([("crossref.org/works?", crossref_list(*order)),
                          ("openalex.org/works?", openalex_list())])
                works, _ = sources.search("x", n=5)
                self.assertEqual([w["doi"] for w in works], ["10.1016/j.x.1"])

    def test_openalex_tops_up_but_only_with_dois_that_resolve(self):
        web = self.web([
            ("crossref.org/works?", crossref_list(crossref_msg(doi="10.1/a", title="First paper"))),
            ("openalex.org/works?", openalex_list(
                openalex_work(doi="10.1/b", title="Second paper"),
                openalex_work(doi="10.1/ghost", title="Paper with a dead DOI"))),
            ("crossref.org/works/10.1/b", crossref_one(doi="10.1/b", title="Second paper")),
            ("crossref.org/works/10.1/ghost", 404),
            ("datacite.org/dois/10.1/ghost", 404),
        ])
        works, reached = sources.search("x", n=5)
        self.assertEqual([w["doi"] for w in works], ["10.1/a", "10.1/b"])
        self.assertEqual([w["source"] for w in works], ["crossref", "openalex"])
        self.assertEqual(reached, ["crossref", "openalex"])
        self.assertTrue(web.called("datacite.org/dois/10.1/ghost"))

    def test_results_leave_out_abstracts(self):
        self.web([("crossref.org/works?", crossref_list(crossref_msg(abstract="<p>Words</p>"))),
                  ("openalex.org/works?", openalex_list())])
        self.assertNotIn("abstract", sources.search("x", n=5)[0][0])

    def test_no_preprints_keeps_preprint_types_out_of_both_searches(self):
        web = self.web([("crossref.org/works?", crossref_list()),
                        ("openalex.org/works?", openalex_list())])
        sources.search("x", n=5, preprints=False)
        self.assertNotIn("posted-content", web.called("crossref.org/works?")[0])
        self.assertNotIn("preprint", web.called("openalex.org/works?")[0])

    def test_nothing_reachable_is_reported_as_no_service_answered(self):
        self.web([("crossref.org", unreachable()), ("openalex.org", unreachable())])
        self.assertEqual(sources.search("x", n=5), ([], []))


# --------------------------------------------------------------------------
# Comparing a claim with a record
# --------------------------------------------------------------------------

class MatchingTests(unittest.TestCase):
    def test_family_names_are_read_from_every_common_shape(self):
        f = sources.claimed_families
        self.assertEqual(f(["Müller, J.", "Jana Schmidt"]), ["muller", "schmidt"])
        self.assertEqual(f("Müller & Schmidt"), ["muller", "schmidt"])
        self.assertEqual(f("Vaswani, Shazeer, Parmar"), ["vaswani", "shazeer", "parmar"])
        self.assertEqual(f([{"family": "Chen", "given": "Mei"}]), ["chen"])
        self.assertEqual(f([]), [])

    def test_et_al_and_u_a_are_not_read_as_names(self):
        f = sources.claimed_families
        self.assertEqual(f("Jumper et al."), ["jumper"])
        self.assertEqual(f(["Ortiz", "et al."]), ["ortiz"])
        self.assertEqual(f("Müller u. a."), ["muller"])
        self.assertEqual(f("Chen, M., et al."), ["chen"])

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
        self.assertEqual(sources.match_authors(["Smith", "Müller"], registry), "partly")
        self.assertEqual(sources.match_authors(["Smith"], registry), "no")
        self.assertEqual(sources.match_authors([], registry), "not given")

    def test_years(self):
        self.assertEqual(sources.match_year(2021, 2021), "yes")
        self.assertEqual(sources.match_year("2020", 2021), "close")
        self.assertEqual(sources.match_year(2014, 2012), "close")     # print vs. online-first
        self.assertEqual(sources.match_year(2018, 2021), "no")
        self.assertEqual(sources.match_year("n.d.", 2021), "no")
        self.assertEqual(sources.match_year(None, 2021), "not given")


class CheckTests(WebTestCase):
    CLAIM = {"doi": ALPHAFOLD, "title": "Highly accurate protein structure prediction with AlphaFold",
             "authors": ["Jumper, J."], "year": 2021}

    def test_a_matching_claim_is_ok(self):
        self.web([("crossref.org/works/", crossref_one())])
        self.assertEqual(sources.check(self.CLAIM)["verdict"], "ok")

    def test_authors_written_as_et_al_still_match(self):
        self.web([("crossref.org/works/", crossref_one())])
        claim = dict(self.CLAIM, authors="Jumper et al.")
        self.assertEqual(sources.check(claim)["verdict"], "ok")

    def test_a_real_doi_with_the_wrong_description_is_a_mismatch(self):
        self.web([("crossref.org/works/", crossref_one())])
        result = sources.check({"doi": ALPHAFOLD, "title": "Deep learning for climate adaptation",
                                "authors": "Müller & Schmidt", "year": 2019})
        self.assertEqual(result["verdict"], "mismatch")
        self.assertIn("AlphaFold", result["reason"])

    def test_a_doi_nobody_knows_is_not_found(self):
        self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404)])
        self.assertEqual(sources.check({"doi": "10.1234/made-up"})["verdict"], "not-found")

    def test_a_retracted_work_is_flagged_even_when_everything_matches(self):
        self.web([("crossref.org/works/", crossref_one(updated_by=RETRACTION))])
        self.assertEqual(sources.check(self.CLAIM)["verdict"], "retracted")

    def test_unreachable_registries_give_unknown(self):
        self.web([("crossref.org", unreachable()), ("datacite.org", unreachable())])
        self.assertEqual(sources.check(self.CLAIM)["verdict"], "unknown")

    def test_a_work_without_doi_is_found_by_title_and_author(self):
        self.web([("openalex.org/works?filter=title.search", openalex_list(openalex_work())),
                  ("crossref.org/works/", crossref_one())])
        result = sources.check({"title": self.CLAIM["title"], "authors": ["John Jumper"],
                                "year": 2021})
        self.assertEqual(result["verdict"], "ok")
        self.assertTrue(result["doi_found_by_title"])

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
        result = sources.check({"title": self.CLAIM["title"], "authors": ["John Jumper"],
                                "year": 2021})
        self.assertEqual(result["verdict"], "ok")
        self.assertIn("query.author=jumper", web.called("crossref.org/works?")[0])

    def test_no_doi_and_nothing_found_asks_for_a_check_by_hand(self):
        self.web([("openalex.org/works?filter=title.search", openalex_list())
                  , ("crossref.org/works?", crossref_list())])
        result = sources.check({"title": "Einführung in die qualitative Sozialforschung",
                                "authors": ["Flick"]})
        self.assertEqual(result["verdict"], "no-doi")


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
        self.assertEqual(rec["abstract_source"], "registry")

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
        self.assertEqual(rec["abstract_source"], "none")

    def test_an_unresolved_doi_comes_back_unchanged(self):
        web = self.web([("crossref.org/works/", 404), ("datacite.org/dois/", 404)])
        self.assertEqual(sources.details("10.1234/nope")["status"], "absent")
        self.assertFalse(web.called("openalex.org"))


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
        self.assertEqual(self.run_main(["find", "x", "--json"])[0], 1)

    def test_find_exits_0_when_the_services_answer_with_nothing(self):
        self.web([("crossref.org/works?", crossref_list()), ("openalex.org/works?", openalex_list())])
        code, out = self.run_main(["find", "x", "--json"])
        self.assertEqual((code, json.loads(out)), (0, []))

    def test_verify_exits_1_when_a_doi_does_not_resolve_and_hides_abstracts(self):
        self.web([("crossref.org/works/10.1038", crossref_one(abstract="<p>Words</p>")),
                  ("crossref.org/works/10.1234", 404), ("datacite.org/dois/10.1234", 404)])
        code, out = self.run_main(["verify", ALPHAFOLD, "10.1234/nope"])
        results = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in results], ["resolved", "absent"])
        self.assertNotIn("abstract", results[0])

    def test_check_reads_stdin_and_a_mismatch_still_exits_0(self):
        self.web([("crossref.org/works/", crossref_one())])
        claim = json.dumps([{"doi": ALPHAFOLD, "title": "Something else entirely", "year": 2019}])
        code, out = self.run_main(["check", "-"], stdin=claim)
        self.assertEqual((code, json.loads(out)[0]["verdict"]), (0, "mismatch"))

    def test_check_exits_1_when_the_registries_cannot_be_asked(self):
        self.web([("crossref.org", unreachable()), ("datacite.org", unreachable())])
        code, _ = self.run_main(["check", "-"], stdin=json.dumps([{"doi": ALPHAFOLD}]))
        self.assertEqual(code, 1)

    def test_the_script_runs_as_a_program(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "verify", "not-a-doi"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)[0]["status"], "invalid")


# --------------------------------------------------------------------------
# Live services (opt-in)
# --------------------------------------------------------------------------

@unittest.skipUnless(os.environ.get("THESIS_KIT_NETWORK_TESTS"),
                     "live test: set THESIS_KIT_NETWORK_TESTS=1 to run against the real services")
class LiveTests(unittest.TestCase):
    def test_a_real_doi_resolves_and_a_made_up_one_does_not(self):
        self.assertEqual(sources.lookup(ALPHAFOLD)["status"], "resolved")
        self.assertEqual(sources.lookup("10.1234/thesis-kit-made-up")["status"], "absent")

    def test_a_live_search_returns_distinct_citable_works(self):
        works, reached = sources.search("green roof cooling urban heat island", n=8)
        self.assertTrue(reached and works)
        keys = [sources.title_key(w["title"]) for w in works]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
