#!/usr/bin/env python3
"""Find papers and check references against the scholarly registries.

Part of thesis-kit. Standard library only, no API key: Crossref, DataCite
and OpenAlex are open services.

    sources.py find "topic" [--n 12] [--json] [--no-preprints]
    sources.py verify DOI [DOI ...]
    sources.py check FILE          (a JSON list, or - to read it from stdin)
    sources.py details DOI [DOI ...]

find     searches Crossref, then OpenAlex, for citable works on a topic.
         Every result carries a DOI that resolves.
verify   says whether each DOI exists (Crossref, then DataCite), with the
         registry's title, authors, year, venue and any retraction or
         correction notice.
check    compares what someone claims about works,
         [{"doi", "title", "authors", "year"}, ...], with the registry
         records and gives one verdict per work: ok, mismatch, retracted,
         not-found, no-doi or unknown. Works without a DOI are looked up by
         title and authors.
details  verify, plus the abstract and a free full-text link where the
         registries or OpenAlex know one.

Exit codes: find exits 1 when no service could be reached, which is not the
same as "nothing found"; verify and details exit 1 when a DOI did not
resolve; check exits 1 only when the registries could not be asked.

Optional environment variables: THESIS_KIT_CONTACT_EMAIL (passed to Crossref
and OpenAlex, which serve requests with a contact address faster) and
THESIS_KIT_OPENALEX_KEY.
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

CONTACT = os.environ.get("THESIS_KIT_CONTACT_EMAIL", "").strip()
OPENALEX_KEY = os.environ.get("THESIS_KIT_OPENALEX_KEY", "").strip()
USER_AGENT = "thesis-kit/1.0 (+https://github.com/CTRLMANu/thesis-kit)"
if CONTACT:
    USER_AGENT += f" (mailto:{CONTACT})"

CROSSREF = "https://api.crossref.org"
DATACITE = "https://api.datacite.org"
OPENALEX = "https://api.openalex.org"


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class NotFound(Exception):
    """The service answered clearly: there is no such record."""


def _wait_seconds(err):
    """How long a rate-limited service asks us to wait, capped at 45 s."""
    seconds = None
    try:
        seconds = float(err.headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        body = json.loads(err.read().decode("utf-8", "replace"))
        seconds = float(body.get("retryAfter", seconds))
    except Exception:
        pass
    return min(seconds if seconds and seconds > 0 else 10.0, 45.0)


def fetch_json(url, attempts=3, timeout=20):
    """GET a JSON document.

    Raises NotFound on 404. A rate limit (429, 503, or an OpenAlex body with
    `retryAfter`) is waited out once; other failures are retried with a short
    backoff, then raised."""
    waited = False
    last_error = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise NotFound(url)
            last_error = err
            if err.code in (429, 503) and not waited:
                waited = True
                time.sleep(_wait_seconds(err))
                continue
        except (urllib.error.URLError, OSError, ValueError) as err:
            last_error = err
        else:
            if isinstance(data, dict) and data.get("retryAfter") and data.get("error"):
                last_error = RuntimeError(data.get("error"))
                if not waited:
                    waited = True
                    time.sleep(min(float(data["retryAfter"]), 45.0))
                    continue
            else:
                return data
        if attempt < attempts - 1:
            time.sleep(0.5 * 2 ** attempt)
    raise last_error


def openalex_url(path, **params):
    if CONTACT:
        params["mailto"] = CONTACT
    if OPENALEX_KEY:
        params["api_key"] = OPENALEX_KEY
    return f"{OPENALEX}/{path}?" + urllib.parse.urlencode(params)


# --------------------------------------------------------------------------
# Text and DOI helpers
# --------------------------------------------------------------------------

DOI_SHAPE = re.compile(r"^10\.\d+(\.\d+)*/\S+$")


def bare_doi(value):
    """'https://doi.org/10.1/AbC', 'doi:10.1/AbC' -> '10.1/abc'."""
    doi = (value or "").strip().lower()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi)
    return doi.rstrip(".,;")


def fold(text):
    """Lower case without accents, so 'Müller' and 'Muller' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def title_key(text):
    """Letters and digits only: two spellings of one title compare equal."""
    return "".join(c for c in fold(text) if c.isalnum())


def plain_text(markup):
    """Registry abstracts arrive as JATS or HTML; keep the words."""
    text = re.sub(r"<[^>]+>", " ", markup or "")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^abstract\s*[:.]?\s+", "", text, flags=re.I)


def _first(value):
    if isinstance(value, list):
        return (value[0] if value else "") or ""
    return value or ""


def _person(family, given="", name=""):
    family, given, name = (family or "").strip(), (given or "").strip(), (name or "").strip()
    if family:
        return {"family": family, "given": given}
    if name or given:
        return {"family": name or given, "given": ""}
    return None


# --------------------------------------------------------------------------
# Records: every service's answer becomes the same dictionary
# --------------------------------------------------------------------------

RETRACTION_TYPES = {"retraction", "withdrawal", "removal"}


def _empty_record():
    return {"doi": "", "title": "", "authors": [], "year": None, "venue": "",
            "volume": "", "issue": "", "pages": "", "publisher": "", "type": "",
            "notices": [], "retracted": False, "abstract": ""}


def from_crossref(msg):
    rec = _empty_record()
    notices = [{"type": (u.get("type") or "").lower(), "notice_doi": bare_doi(u.get("DOI"))}
               for u in msg.get("updated-by") or [] if u.get("type")]
    date = ((msg.get("issued") or msg.get("published") or {}).get("date-parts") or [[None]])[0]
    rec.update(
        doi=bare_doi(msg.get("DOI")),
        title=_first(msg.get("title")),
        authors=[p for p in (_person(a.get("family"), a.get("given"), a.get("name"))
                             for a in msg.get("author") or []) if p],
        year=date[0] if date else None,
        venue=_first(msg.get("container-title")),
        volume=msg.get("volume") or "", issue=msg.get("issue") or "",
        pages=msg.get("page") or "", publisher=msg.get("publisher") or "",
        type=msg.get("type") or "", notices=notices,
        retracted=any(n["type"] in RETRACTION_TYPES for n in notices),
        abstract=plain_text(msg.get("abstract")),
    )
    return rec


def from_datacite(attrs):
    rec = _empty_record()
    publisher = attrs.get("publisher")
    if isinstance(publisher, dict):
        publisher = publisher.get("name")
    abstract = next((d.get("description", "") for d in attrs.get("descriptions") or []
                     if d.get("descriptionType") == "Abstract"), "")
    rec.update(
        doi=bare_doi(attrs.get("doi")),
        title=((attrs.get("titles") or [{}])[0] or {}).get("title", ""),
        authors=[p for p in (_person(c.get("familyName"), c.get("givenName"), c.get("name"))
                             for c in attrs.get("creators") or []) if p],
        year=attrs.get("publicationYear"),
        venue=(attrs.get("container") or {}).get("title") or "",
        publisher=publisher or "",
        type=((attrs.get("types") or {}).get("resourceTypeGeneral") or "").lower(),
        abstract=plain_text(abstract),
    )
    return rec


def _openalex_abstract(inverted):
    """OpenAlex stores an abstract as {word: [positions]}."""
    placed = sorted((pos, word) for word, positions in (inverted or {}).items()
                    for pos in positions)
    return " ".join(word for _, word in placed)


def from_openalex(work):
    rec = _empty_record()
    authors = []
    for a in work.get("authorships") or []:
        parts = ((a.get("author") or {}).get("display_name") or "").split()
        if parts:
            # OpenAlex gives one display name; read the last word as the family name.
            authors.append({"family": parts[-1], "given": " ".join(parts[:-1])})
    source = (work.get("primary_location") or {}).get("source") or {}
    rec.update(
        doi=bare_doi(work.get("doi")),
        title=work.get("title") or work.get("display_name") or "",
        authors=authors,
        year=work.get("publication_year"),
        venue=source.get("display_name") or "",
        publisher=source.get("host_organization_name") or "",
        type=work.get("type") or "",
        retracted=bool(work.get("is_retracted")),
        abstract=_openalex_abstract(work.get("abstract_inverted_index")),
    )
    return rec


# --------------------------------------------------------------------------
# Registry lookup
# --------------------------------------------------------------------------

def lookup(doi):
    """Resolve one DOI at Crossref, then DataCite.

    status is resolved, absent, unknown or invalid. 'absent' needs a clear
    'no such record' from both registries; when either could not be asked,
    the answer is 'unknown', never 'absent'."""
    doi = bare_doi(doi)
    if not DOI_SHAPE.match(doi):
        return {"doi": doi, "status": "invalid",
                "error": "not a DOI (a DOI looks like 10.1234/something)"}
    registries = (
        ("crossref", f"{CROSSREF}/works/{urllib.parse.quote(doi)}",
         lambda data: from_crossref(data["message"])),
        ("datacite", f"{DATACITE}/dois/{urllib.parse.quote(doi)}",
         lambda data: from_datacite(data["data"]["attributes"])),
    )
    problem = None
    for agency, url, convert in registries:
        try:
            record = convert(fetch_json(url))
        except NotFound:
            continue
        except Exception as err:
            problem = f"{agency}: {err}"
            continue
        record.update(doi=doi, status="resolved", agency=agency)
        return record
    if problem:
        return {"doi": doi, "status": "unknown", "error": problem}
    return {"doi": doi, "status": "absent"}


# --------------------------------------------------------------------------
# find: search for works on a topic
# --------------------------------------------------------------------------

PUBLISHED = {"journal-article", "proceedings-article", "book-chapter", "book",
             "monograph", "edited-book", "report", "article", "review"}
PREPRINTS = {"posted-content", "preprint"}
# The same types in Crossref's vocabulary ("article", "review" and "preprint"
# are OpenAlex's names).
CROSSREF_CITABLE = {"journal-article", "proceedings-article", "book-chapter", "book",
                    "monograph", "edited-book", "report", "posted-content"}

# Registries index peer-review reports, decision letters, corrections and
# recommendation notes as works of their own; none of them is citable.
NOT_A_WORK = re.compile(
    r"^(review (for|of)|decision letter|author response|reviewer report|peer review"
    r"|correction|corrigendum|erratum|retraction|expression of concern"
    r"|faculty opinions recommendation)", re.I)
REVIEW_ARTIFACT_DOI = re.compile(r"/(review|decision)\d+$")


def citable(rec, allowed_types):
    if not rec["doi"] or not rec["title"].strip() or not rec["authors"]:
        return False
    if rec["type"] not in allowed_types or rec["retracted"]:
        return False
    if NOT_A_WORK.match(rec["title"].strip()) or REVIEW_ARTIFACT_DOI.search(rec["doi"]):
        return False
    if not rec["venue"]:
        # Without a journal or book: blog-post DOIs, and bare one-name records.
        if rec["publisher"].strip().lower() == "front matter":
            return False
        if len(rec["authors"]) == 1 and not rec["authors"][0]["given"]:
            return False
    return True


def _add(found, rec):
    """Add unless the same work is already there. A preprint and its journal
    version have different DOIs but the same title; keep the journal one."""
    key = title_key(rec["title"])
    for i, other in enumerate(found):
        if other["doi"] == rec["doi"] or (key and key == title_key(other["title"])):
            if other["type"] in PREPRINTS and rec["type"] not in PREPRINTS:
                found[i] = rec
            return
    found.append(rec)


def search(topic, n=12, preprints=True):
    """Citable works on `topic`: Crossref first, topped up from OpenAlex.

    Returns (works, reached). An empty `reached` means no service answered,
    so the search did not happen at all."""
    allowed = PUBLISHED | (PREPRINTS if preprints else set())
    found, reached = [], []
    crossref_types = sorted(t for t in allowed if t in CROSSREF_CITABLE)
    try:
        params = urllib.parse.urlencode({
            "query.bibliographic": topic,
            "rows": max(5 * n, 50),
            "filter": ",".join("type:" + t for t in crossref_types),
            "select": "DOI,title,author,issued,published,container-title,type,"
                      "publisher,volume,issue,page,updated-by",
        })
        items = fetch_json(f"{CROSSREF}/works?{params}")["message"]["items"]
        reached.append("crossref")
        for item in items:
            if len(found) >= n:
                break
            rec = from_crossref(item)
            if citable(rec, allowed):
                rec["source"] = "crossref"
                _add(found, rec)
    except Exception as err:
        print(f"# crossref search failed: {err}", file=sys.stderr)
    if len(found) < n:
        types = "article|review" + ("|preprint" if preprints else "")
        try:
            data = fetch_json(openalex_url("works", search=topic, filter=f"type:{types}",
                                           **{"per-page": min(3 * (n - len(found)), 100)}))
            reached.append("openalex")
            for work in data.get("results", []):
                if len(found) >= n:
                    break
                rec = from_openalex(work)
                if not citable(rec, allowed) or any(f["doi"] == rec["doi"] for f in found):
                    continue
                # OpenAlex lists some DOIs that no registry resolves.
                resolved = lookup(rec["doi"])
                if resolved["status"] != "resolved":
                    print(f"# skipped {rec['doi']} from OpenAlex: DOI {resolved['status']}",
                          file=sys.stderr)
                    continue
                rec["source"] = "openalex"
                _add(found, rec)
        except Exception as err:
            print(f"# openalex search failed: {err}", file=sys.stderr)
    for rec in found:
        rec.pop("abstract", None)       # abstracts come from `details`
    return found[:n], reached


# --------------------------------------------------------------------------
# check: does a claimed work match its registry record?
# --------------------------------------------------------------------------

# "et al." and the German "u. a." stand for authors not listed; they are not names.
OTHERS = re.compile(r"\bet\.?\s*al\b\.?|\bu\.\s*a\.|\band others\b", re.I)


def claimed_families(authors):
    """Family names from any shape: dicts, 'Müller, J.', 'J. Müller',
    'Müller & Schmidt', 'Jumper et al.', or one comma-separated string."""
    if isinstance(authors, str):
        authors = re.split(r";| & | and |, (?=[A-ZÄÖÜ][a-zäöüß])", OTHERS.sub("", authors))
    names = []
    for a in authors or []:
        if isinstance(a, dict):
            name = a.get("family") or a.get("name") or ""
        else:
            a = OTHERS.sub("", str(a)).strip(" ,;")
            if "," in a:
                name = a.split(",")[0]
            else:
                words = [w for w in a.split() if len(w.strip(".")) > 1]
                name = words[-1] if words else a
        name = fold(name.strip(" ."))
        if name:
            names.append(name)
    return names


def main_title(text):
    """The part before a subtitle: 'Cooling the cities – A review of …' -> 'Cooling the cities'."""
    return re.split(r"\s+[–—-]\s+|[:?!]\s+|\.\s+", text or "", maxsplit=1)[0]


def title_similarity(a, b):
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb:
        return 1.0
    ma, mb = title_key(main_title(a)), title_key(main_title(b))
    if ma and ma == mb and len(ma) >= 10:          # same main title, subtitle left out
        return 1.0
    if (ka in kb or kb in ka) and min(len(ka), len(kb)) >= 20:
        return 0.95
    # A short fragment ("Introduction") is not a title; only near-identical text counts.
    return difflib.SequenceMatcher(None, ka, kb).ratio()


def match_title(claimed, registry):
    if not (claimed or "").strip():
        return "not given"
    score = title_similarity(claimed, registry)
    return "yes" if score >= 0.9 else "partly" if score >= 0.6 else "no"


def match_authors(claimed, registry_authors):
    names = claimed_families(claimed)
    if not names:
        return "not given"
    known = {fold(a.get("family", "")) for a in registry_authors or []}
    known |= {part for name in known for part in name.split()}   # "van der Berg"
    if names[0] in known or names[0].split()[-1] in known:
        return "yes"
    return "partly" if any(n in known for n in names) else "no"


def match_year(claimed, registry_year):
    if claimed in (None, ""):
        return "not given"
    try:
        gap = abs(int(str(claimed)[:4]) - int(registry_year))
    except (TypeError, ValueError):
        return "no"
    # Online-first and print years of one paper can be two years apart
    # (Santamouris: online 2012, issue 2014).
    return "yes" if gap == 0 else "close" if gap <= 2 else "no"


def title_candidates(title, authors=None):
    """Registry records whose title resembles `title`.

    OpenAlex's title search ranks an exact title first. Crossref fills in when
    OpenAlex is unreachable; its search buries famous papers under reviews of
    them, so it gets the first author's name and the citable types too."""
    found = []
    try:
        data = fetch_json(openalex_url("works", filter="title.search:" + title.replace(",", " "),
                                       **{"per-page": 10}))
        found = [r for r in (from_openalex(w) for w in data.get("results", [])) if r["doi"]]
    except Exception as err:
        print(f"# openalex title search failed, trying crossref: {err}", file=sys.stderr)
    if not found:
        params = {"query.bibliographic": title, "rows": 20,
                  "filter": ",".join("type:" + t for t in sorted(CROSSREF_CITABLE)),
                  "select": "DOI,title,author,issued,published,container-title,type"}
        families = claimed_families(authors)
        if families:
            params["query.author"] = families[0]
        try:
            items = fetch_json(f"{CROSSREF}/works?{urllib.parse.urlencode(params)}")["message"]["items"]
            found = [r for r in (from_crossref(i) for i in items) if r["doi"]]
        except Exception as err:
            print(f"# crossref title search failed: {err}", file=sys.stderr)
    return [r for r in found if not NOT_A_WORK.match(r["title"].strip())]


def find_by_title(title, authors=None, year=None):
    """(match, closest) for a claim without a DOI. A title alone is not
    enough: famous titles get reused ('Attention is all you need: ...'), so
    the authors (and roughly the year) have to fit as well."""
    ranked = sorted(title_candidates(title, authors),
                    key=lambda r: title_similarity(title, r["title"]), reverse=True)
    for rec in ranked:
        if title_similarity(title, rec["title"]) < 0.9:
            break
        if match_authors(authors, rec["authors"]) in ("yes", "not given") \
                and match_year(year, rec["year"]) != "no":
            return rec, ranked[0]
    return None, (ranked[0] if ranked else None)


def check(item):
    claimed = {"doi": bare_doi(item.get("doi")), "title": item.get("title") or "",
               "authors": item.get("authors") or [], "year": item.get("year")}
    result = {"claimed": claimed}
    doi, by_title = claimed["doi"], False
    if not doi:
        match, closest = (find_by_title(claimed["title"], claimed["authors"], claimed["year"])
                          if claimed["title"] else (None, None))
        if not match:
            reason = ("No DOI given, and no registry record with this title and these "
                      "authors was found. Books, reports, laws and web pages often have no "
                      "DOI; the student confirms such a source by hand.")
            if closest:
                names = ", ".join(a["family"] for a in closest["authors"][:3])
                reason += (f" Closest record, probably a different work: \"{closest['title']}\" "
                           f"({names}, {closest['year']}, doi {closest['doi']}).")
            result.update(verdict="no-doi", reason=reason)
            return result
        doi, by_title = match["doi"], True
    rec = lookup(doi)
    rec.pop("abstract", None)
    result.update(registry=rec, doi_found_by_title=by_title)
    if rec["status"] in ("absent", "invalid"):
        result.update(verdict="not-found", reason=(
            f"The DOI {doi} does not exist at Crossref or DataCite"
            + (f" ({rec['error']})" if rec.get("error") else "")
            + ". The work may be invented, or the DOI mistyped."))
        return result
    if rec["status"] != "resolved":
        result.update(verdict="unknown", reason=(
            f"The registries could not be reached ({rec.get('error', 'network')}). "
            "Nothing is known about this DOI yet; try again later."))
        return result
    match = {"title": match_title(claimed["title"], rec["title"]),
             "authors": match_authors(claimed["authors"], rec["authors"]),
             "year": match_year(claimed["year"], rec["year"])}
    result["match"] = match
    if rec["retracted"]:
        kinds = ", ".join(n["type"] for n in rec["notices"]) or "retraction"
        result.update(verdict="retracted", reason=(
            f"The registry lists a notice on this work ({kinds}). "
            "A retracted work cannot support a claim in a thesis."))
    elif any(v in ("no", "partly") for v in match.values()):
        wrong = ", ".join(k for k, v in match.items() if v in ("no", "partly"))
        result.update(verdict="mismatch", reason=(
            f"The DOI exists, but the {wrong} do not match the registry record "
            f"(\"{rec['title']}\", {rec['year']}). Either the DOI or the description is wrong."))
    else:
        note = " (found by title)" if by_title else ""
        if rec["notices"]:
            note += (". Note: the registry lists " + ", ".join(n["type"] for n in rec["notices"])
                     + " notice(s); read them before citing")
        result.update(verdict="ok", reason=f"The DOI exists and matches the registry record{note}.")
    return result


# --------------------------------------------------------------------------
# details: abstract and free full text
# --------------------------------------------------------------------------

def details(doi):
    rec = lookup(doi)
    if rec["status"] != "resolved":
        return rec
    rec["free_fulltext_url"] = None
    try:
        work = fetch_json(openalex_url("works/doi:" + urllib.parse.quote(rec["doi"])))
        rec["free_fulltext_url"] = (work.get("open_access") or {}).get("oa_url")
        rec["cited_by_count"] = work.get("cited_by_count")
        rec["retracted"] = rec["retracted"] or bool(work.get("is_retracted"))
        if not rec["abstract"]:
            rec["abstract"] = _openalex_abstract(work.get("abstract_inverted_index"))
    except NotFound:
        pass
    except Exception as err:
        rec["openalex_error"] = str(err)
    rec["abstract_source"] = "registry" if rec["abstract"] else "none"
    return rec


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def _print_readable(works):
    if not works:
        print("No citable works found.")
    for w in works:
        names = ", ".join((f"{a['given']} {a['family']}").strip() for a in w["authors"][:3])
        if len(w["authors"]) > 3:
            names += " et al."
        print(f"{w['doi']}  [{w['type']}]")
        print(f"    {w['title']}")
        print(f"    {names} ({w['year']}) - {w['venue'] or '(no venue)'}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sources.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    p_find = sub.add_parser("find", help="Search for citable works on a topic.")
    p_find.add_argument("topic")
    p_find.add_argument("--n", type=int, default=12, help="Maximum results (default 12)")
    p_find.add_argument("--json", action="store_true", help="Print JSON instead of a list")
    p_find.add_argument("--no-preprints", action="store_true",
                        help="Leave out preprints (SSRN, arXiv, Research Square, ...)")
    p_verify = sub.add_parser("verify", help="Does each DOI exist?")
    p_verify.add_argument("dois", nargs="+")
    p_check = sub.add_parser("check", help="Compare claimed works with the registries.")
    p_check.add_argument("file", help="JSON file, or - for stdin")
    p_details = sub.add_parser("details", help="verify plus abstract and free full text.")
    p_details.add_argument("dois", nargs="+")
    args = parser.parse_args(argv)

    if args.cmd == "find":
        works, reached = search(args.topic, n=args.n, preprints=not args.no_preprints)
        if args.json:
            print(json.dumps(works, indent=2, ensure_ascii=False))
        else:
            _print_readable(works)
        if not reached:
            print("# no search service could be reached: this is a failed search, "
                  "not an empty topic", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "verify":
        results = [lookup(d) for d in args.dois]
        for r in results:
            r.pop("abstract", None)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in results) else 0

    if args.cmd == "check":
        raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        items = json.loads(raw)
        results = [check(i) for i in (items if isinstance(items, list) else [items])]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        counts = {}
        for r in results:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print("# " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)
        return 1 if counts.get("unknown") else 0

    if args.cmd == "details":
        results = [details(d) for d in args.dois]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in results) else 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
