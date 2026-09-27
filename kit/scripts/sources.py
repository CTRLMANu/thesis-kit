#!/usr/bin/env python3
"""Keyless source lookup and DOI checking for thesis-kit.

No API key. Crossref, OpenAlex and DataCite are open endpoints. Every printed
DOI is checked against Crossref, then DataCite, and a source whose DOI does not
resolve is never returned as verified.

    sources.py find "topic" [--n 12] [--json] [--no-preprints]
    sources.py verify 10.1038/s41598-023-41032-5 [more DOIs...]
    sources.py check items.json          (or "-" to read the JSON from stdin)
    sources.py details 10.1038/s41598-023-41032-5 [more DOIs...]

find     searches for papers on a topic (human-readable list, or --json).
verify   says whether each DOI exists, with the registry's title, authors,
         year and any retraction or correction notice.
check    compares what a student or a tool *claims* about a paper
         ([{"doi", "title", "authors", "year"}, ...]) with the registry, and
         says per paper whether title, authors and year match. Items without
         a DOI are looked up by title.
details  adds the abstract (when a registry has one) and a free full-text
         link (when OpenAlex knows one) to what verify returns.

Derived from scripts/sources.py in getedgehq/skills (autonomous-research,
commit 34df0477, Apache-2.0, Copyright 2026 Floom), itself ported from
OpenDraft (MIT, Copyright (c) 2025 SCAILE Technologies GmbH).
Modified for thesis-kit: renamed the user agent and contact variable, extended
verify with authors, year, venue and update notices, and added the check and
details commands. See kit/scripts/THIRD_PARTY_NOTICES.md.
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

# Crossref runs a "polite pool" with better rate limits for requests that carry a
# contact address. That address should be the person actually making the requests,
# so it is opt-in through the environment and never a baked-in default: shipping
# one address would pool every installer into a single identity and route their
# rate-limit problems to a stranger's inbox.
_CONTACT = (os.environ.get("THESIS_KIT_CONTACT_EMAIL") or "").strip()
UA = "thesis-kit/1.0 (+https://github.com/CTRLMANu/thesis-kit)"
if _CONTACT:
    UA += " (mailto:%s)" % _CONTACT


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _get_patient(url, timeout=20, max_wait=45):
    """_get, but wait once and retry when the service says it is rate-limiting.

    OpenAlex rate-limits anonymous search under load and says how long to wait
    (HTTP 429 with Retry-After, or a JSON body with retryAfter)."""
    try:
        data = _get(url, timeout)
    except urllib.error.HTTPError as e:
        if e.code not in (429, 503):
            raise
        wait = e.headers.get("Retry-After") if e.headers else None
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            wait = body.get("retryAfter", wait)
        except Exception:
            pass
        time.sleep(min(float(wait or 10), max_wait))
        return _get(url, timeout)
    if isinstance(data, dict) and data.get("error") and data.get("retryAfter"):
        time.sleep(min(float(data["retryAfter"]), max_wait))
        return _get(url, timeout)
    return data


def _openalex_url(path, params):
    """OpenAlex URL with the optional contact address and API key."""
    params = dict(params)
    if _CONTACT:
        params["mailto"] = _CONTACT
    key = (os.environ.get("THESIS_KIT_OPENALEX_KEY") or "").strip()
    if key:
        params["api_key"] = key
    return f"https://api.openalex.org/{path}?" + urllib.parse.urlencode(params)


def _norm_doi(doi):
    """Lower-case and strip a DOI down to its bare form (no scheme/host)."""
    d = (doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d


# 10.<registrant>/<suffix> is the whole of DOI grammar that can be checked
# without asking a registry: a numeric registrant code (optionally with
# dot-separated sub-codes, an older but still-valid form) followed by a slash
# and a non-empty, non-whitespace suffix. The suffix itself is opaque by
# design: DOI syntax (ANSI/NISO Z39.84) allows almost any character in it,
# including the slashes, dots, parentheses, angle brackets, colons and
# semicolons that show up in real DOIs like
# 10.1002/(SICI)1099-1050(199806)7:3<233::AID-HEC343>3.0.CO;2-Y, so this only
# rejects what genuinely cannot be a DOI at all: no "10." prefix, no
# registrant digits, or nothing after the slash.
_DOI_SHAPE = re.compile(r"^10\.\d{2,9}(?:\.\d+)*/\S+$")


def _shape_invalid_reason(d):
    """None when `d` could plausibly be a DOI, else why it cannot be one."""
    if not d.startswith("10."):
        return "does not start with the DOI prefix '10.'"
    if not _DOI_SHAPE.match(d):
        if "/" not in d:
            return "has no '/' separating the registrant code from the suffix"
        return "does not match DOI grammar 10.<registrant>/<suffix>"
    return None


# Crossref indexes peer-review reports, decision letters, corrections and
# component parts as first-class works. A bibliographic query returns them
# ranked alongside the papers, so an unfiltered `find` can hand back a citation
# list made entirely of review artifacts. Only these types are citable.
# journal-article / proceedings-article / book-chapter / monograph / report are
# always in scope; posted-content (arXiv, SSRN, bioRxiv preprints) is gated by
# --include-preprints / --no-preprints because it is also the type Crossref
# uses for non-scholarly "posted" content such as blog notes (see
# _BLOG_PUBLISHERS below).
PUBLISHED_TYPES = {"journal-article", "proceedings-article", "book-chapter",
                    "monograph", "report"}
PREPRINT_TYPES = {"posted-content"}


def citable_types(include_preprints=True):
    return PUBLISHED_TYPES | (PREPRINT_TYPES if include_preprints else set())


# Titles Crossref gives review/decision/correction records, matched case-folded.
_JUNK_PREFIXES = ("review for ", "decision letter for ", "author response",
                  "reviewer report", "peer review of ", "correction to",
                  "corrigendum", "erratum", "retraction")


def _citable(title, doi):
    t = (title or "").strip().lower()
    if not t or t.startswith(_JUNK_PREFIXES):
        return False
    # Review artifacts hang off the parent DOI as /vN/reviewN or /vN/decisionN.
    tail = doi.rsplit("/", 2)[-2:] if doi.count("/") >= 2 else []
    return not any(s.startswith(("review", "decision", "sup")) for s in tail)


# DOI-minting services that register works for blog posts and research notes,
# not peer-reviewed or preprint-server output. Rogue Scholar mints DOIs for
# science blog posts under Crossref publisher "Front Matter" (prefix
# 10.59350) and files them as type "posted-content", which is otherwise
# indistinguishable from a real arXiv/SSRN preprint by type alone. Checked
# case-insensitively.
_BLOG_PUBLISHERS = {"front matter"}


def _is_low_quality(authors, venue, publisher=""):
    """Strong signal that a hit is blog/note content, not a citable work.

    Two independent triggers, both conditioned on an empty venue (no
    container-title / no journal / no conference proceedings recorded):
      1. Published through a known blog-DOI-minting service (Rogue Scholar's
         "Front Matter"), regardless of author count.
      2. A single author with no recorded given name -- a bare mononym like
         "Pi" with nothing else to distinguish it, which is what an author
         list looks like when Crossref/OpenAlex return sparse metadata for
         low-effort posts. A multi-author work, or one where a given name is
         on record, is not touched by this rule.

    A non-empty venue always clears a source: whatever the author situation,
    a work that names its journal/conference/book series is not the pattern
    this filter targets.
    """
    if (venue or "").strip():
        return False
    if (publisher or "").strip().lower() in _BLOG_PUBLISHERS:
        return True
    if len(authors) == 1 and not (authors[0].get("given") or "").strip():
        return True
    return False


def _crossref_authors(item):
    out = []
    for a in item.get("author") or []:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        if family or given:
            out.append({"family": family or given, "given": given if family else ""})
    return out


def _openalex_authors(w):
    """OpenAlex only exposes a single display_name per author, so split it
    into a best-effort given/family pair the same way a human would read it:
    last token is the family name, everything before it is the given name.
    A single-token name (a mononym) yields an empty given name."""
    out = []
    for a in w.get("authorships") or []:
        name = ((a.get("author") or {}).get("display_name") or "").strip()
        if not name:
            continue
        parts = name.split()
        if len(parts) >= 2:
            out.append({"family": parts[-1], "given": " ".join(parts[:-1])})
        else:
            out.append({"family": parts[0], "given": ""})
    return out


def _display_name(author):
    given, family = author.get("given", ""), author.get("family", "")
    return f"{given} {family}".strip() if given else family


_PREFERRED_TYPES = ("journal-article", "proceedings-article", "book-chapter")


def _title_key(title):
    """Collapse a title to a comparison key: letters and digits only, lowercased.

    Catches the common case of one paper deposited twice, for example an SSRN
    preprint and the journal version, which carry different DOIs and so survive
    DOI-based deduplication."""
    return "".join(c for c in (title or "").lower() if c.isalnum())


def _preferable(new, old):
    """True when `new` is the better record of the same work.

    A published version beats a preprint, and a record naming its venue beats one
    that does not. Anything else is a tie and the incumbent stays."""
    new_pub = new.get("type") in _PREFERRED_TYPES
    old_pub = old.get("type") in _PREFERRED_TYPES
    if new_pub != old_pub:
        return new_pub
    return bool(new.get("venue")) and not old.get("venue")


def _absorb(out, by_title, rec):
    """Add `rec` unless the same work is already present, keeping the better copy.

    Returns True when the caller's result count changed."""
    key = _title_key(rec.get("title"))
    if key and key in by_title:
        i = by_title[key]
        if _preferable(rec, out[i]):
            out[i] = rec
        return False
    if key:
        by_title[key] = len(out)
    out.append(rec)
    return True


def find(topic, n=12, include_preprints=True, status=None):
    """Search Crossref then OpenAlex for citable sources on `topic`.

    `status`, when given, is filled in with two lists: `attempted` names every
    API this call actually reached for, and `failed` names those that raised.
    An empty result means two different things -- "the APIs answered and had
    nothing" and "nothing answered at all" -- and only the caller holding this
    dict can tell them apart. `main` uses it to exit non-zero on the second,
    because an exit code of 0 with zero sources reads to an orchestrating model
    as a successful search of a topic with no literature, and the next stage
    then writes a paper without any."""
    if status is None:
        status = {}
    status.setdefault("attempted", [])
    status.setdefault("failed", [])
    out, seen, by_title = [], set(), {}
    types = citable_types(include_preprints)
    status["attempted"].append("crossref")
    try:
        # Over-fetch: the type and quality filters remove a large share of
        # Crossref hits.
        q = urllib.parse.urlencode({
            "query.bibliographic": topic, "rows": max(n * 6, 60),
            "filter": ",".join(f"type:{t}" for t in sorted(types)),
            "select": "DOI,title,author,issued,container-title,type,publisher"})
        for it in _get(f"https://api.crossref.org/works?{q}")["message"]["items"]:
            if len(out) >= n: break
            doi = _norm_doi(it.get("DOI"))
            title = (it.get("title") or [""])[0]
            if not doi or doi in seen: continue
            if it.get("type") not in types: continue
            if not _citable(title, doi): continue
            au = _crossref_authors(it)
            if not au: continue          # a paper with no named author is not citable
            venue = (it.get("container-title") or [""])[0]
            publisher = it.get("publisher") or ""
            if _is_low_quality(au, venue, publisher): continue
            seen.add(doi)
            _absorb(out, by_title, {
                "doi": doi, "title": title, "authors": au[:6],
                "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                "venue": venue, "publisher": publisher,
                "type": it.get("type"), "source": "crossref"})
    except Exception as e:
        status["failed"].append("crossref")
        print(f"# crossref failed: {e}", file=sys.stderr)
    if len(out) < n:
        status["attempted"].append("openalex")
        try:
            url = _openalex_url("works", {"search": topic, "per-page": (n - len(out)) * 3,
                                          "filter": "type:article"})
            for w in _get_patient(url).get("results", []):
                if len(out) >= n: break
                doi = _norm_doi(w.get("doi"))
                title = w.get("title") or ""
                if not doi or doi in seen or not _citable(title, doi): continue
                au = _openalex_authors(w)
                if not au: continue
                source = ((w.get("primary_location") or {}).get("source") or {})
                venue = source.get("display_name", "")
                publisher = source.get("host_organization_name", "") or ""
                if _is_low_quality(au, venue, publisher): continue
                # OpenAlex indexes DOIs that neither Crossref nor DataCite
                # resolves. Dropping one silently made a rate-limited verify
                # look identical to a genuinely absent record, so say which
                # DOI went and why: "unknown" is a network problem to retry,
                # "absent" is a bad DOI to leave out.
                verification = verify(doi)
                if verification["status"] != "resolved":
                    print(f"# dropped openalex hit {doi}: verification "
                          f"{verification['status']}"
                          + (f" ({verification['error']})" if verification.get("error") else ""),
                          file=sys.stderr)
                    continue
                seen.add(doi)
                _absorb(out, by_title, {
                    "doi": doi, "title": title, "authors": au[:6],
                    "year": w.get("publication_year"),
                    "venue": venue, "publisher": publisher,
                    "type": w.get("type"), "source": "openalex"})
        except Exception as e:
            status["failed"].append("openalex")
            print(f"# openalex failed: {e}", file=sys.stderr)
    return out


VERIFY_ATTEMPTS = 3
VERIFY_BASE_DELAY = 0.3

# Crossref records editorial notices on the original work under `updated-by`
# (fed by Retraction Watch among others). A retraction-type notice means "do
# not cite this as sound work"; every other notice (correction, expression of
# concern, ...) means "read the notice before citing" and is listed as-is.
_RETRACTION_NOTICES = {"retraction", "withdrawal", "removal"}


def _crossref_record(msg):
    """The fields thesis-kit shows a student, from a Crossref /works/{doi} message."""
    notices = []
    for u in msg.get("updated-by") or []:
        kind = (u.get("type") or "").strip().lower()
        if kind:
            notices.append({"type": kind, "notice_doi": _norm_doi(u.get("DOI"))})
    date = (msg.get("issued") or msg.get("published") or {}).get("date-parts") or [[None]]
    return {
        "title": (msg.get("title") or [""])[0],
        "authors": _crossref_authors(msg),
        "year": date[0][0] if date and date[0] else None,
        "venue": (msg.get("container-title") or [""])[0],
        "volume": msg.get("volume") or "",
        "issue": msg.get("issue") or "",
        "pages": msg.get("page") or "",
        "publisher": msg.get("publisher") or "",
        "type": msg.get("type") or "",
        "notices": notices,
        "retracted": any(n["type"] in _RETRACTION_NOTICES for n in notices),
        "abstract": _strip_markup(msg.get("abstract") or ""),
    }


def _strip_markup(text):
    """Crossref abstracts arrive as JATS XML; keep the words only."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower().startswith("abstract "):
        text = text[len("abstract "):]
    return text


def _datacite_record(attrs):
    """The same fields from a DataCite /dois/{doi} `attributes` object."""
    authors = []
    for c in attrs.get("creators") or []:
        family = (c.get("familyName") or "").strip()
        given = (c.get("givenName") or "").strip()
        if not family:
            family = (c.get("name") or "").strip()
        if family:
            authors.append({"family": family, "given": given})
    return {
        "title": ((attrs.get("titles") or [{}])[0] or {}).get("title", ""),
        "authors": authors,
        "year": attrs.get("publicationYear"),
        "venue": ((attrs.get("container") or {}).get("title") or ""),
        "volume": "", "issue": "", "pages": "",
        "publisher": attrs.get("publisher") if isinstance(attrs.get("publisher"), str)
        else ((attrs.get("publisher") or {}).get("name") or ""),
        "type": ((attrs.get("types") or {}).get("resourceTypeGeneral") or "").lower(),
        "notices": [],
        "retracted": False,
        "abstract": next((_strip_markup(x.get("description", ""))
                          for x in attrs.get("descriptions") or []
                          if x.get("descriptionType") == "Abstract"), ""),
    }


def verify(doi):
    """resolved | absent | unknown | invalid. Unknown never becomes absent.

    Crossref is asked first, then DataCite. A non-404 answer from Crossref, a
    429 or a 5xx or a dropped connection, is not evidence about the record: it
    is evidence about Crossref. Returning "unknown" there used to end the
    function, so a DataCite-only DOI (every arXiv and Zenodo deposit) came back
    unverifiable whenever Crossref was rate-limiting, and the caller had no way
    to tell that from a real failure. Both agencies are now always tried, and
    only if neither could answer is the last "unknown" returned.
    """
    d = _norm_doi(doi)
    if not d:
        return {"doi": d, "status": "invalid", "agency": None,
                "error": "DOI is empty"}
    shape_problem = _shape_invalid_reason(d)
    if shape_problem:
        return {"doi": d, "status": "invalid", "agency": None,
                "error": f"{d!r} is not a well-formed DOI: {shape_problem}"}
    last_unknown = None
    for name, url in (("crossref", f"https://api.crossref.org/works/{urllib.parse.quote(d)}"),
                      ("datacite", f"https://api.datacite.org/dois/{urllib.parse.quote(d)}")):
        for attempt in range(1, VERIFY_ATTEMPTS + 1):
            try:
                j = _get(url)
                rec = _crossref_record(j.get("message", {})) if name == "crossref" \
                    else _datacite_record(j.get("data", {}).get("attributes", {}))
                out = {"doi": d, "status": "resolved", "agency": name}
                out.update(rec)
                return out
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # Definitive "no such record" at this agency. No retry, and
                    # it does not clear an earlier agency's unknown: one 404 plus
                    # one unreachable agency is still unknown, never absent.
                    break
                error = f"HTTP {e.code}"
            except Exception as e:  # transport error, timeout, malformed JSON
                error = str(e)
            if attempt < VERIFY_ATTEMPTS:
                # Exponential backoff: a flat 0.3s retry against a 429 is a
                # second 429, which is how a rate limit turned into a verdict.
                time.sleep(VERIFY_BASE_DELAY * (2 ** (attempt - 1)))
                continue
            last_unknown = {"doi": d, "status": "unknown", "agency": name,
                            "error": error}
            break
        time.sleep(0.1)
    if last_unknown:
        return last_unknown
    return {"doi": d, "status": "absent", "agency": None}


# ---------------------------------------------------------------------------
# check: does the paper someone describes match the registry record?
# ---------------------------------------------------------------------------

def _fold(text):
    """Lower-case, accents removed: 'Müller' and 'Muller' compare equal."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _claimed_family_names(authors):
    """Family names from whatever shape a claim gives: dicts, 'Müller, J.',
    'J. Müller', 'Müller & Schmidt', or one comma-separated string."""
    if isinstance(authors, str):
        authors = re.split(r";| & | and |, (?=[A-ZÄÖÜ][a-zäöüß])", authors)
    names = []
    for a in authors or []:
        if isinstance(a, dict):
            fam = a.get("family") or a.get("name") or ""
            if fam:
                names.append(_fold(fam))
            continue
        a = str(a).strip()
        if not a:
            continue
        if "," in a:                      # "Müller, J." -> family first
            fam = a.split(",")[0]
        else:                             # "J. Müller" / "Jana Müller" -> last token
            tokens = [t for t in a.split() if len(t.strip(".")) > 1]
            fam = tokens[-1] if tokens else a
        names.append(_fold(fam.strip(" .")))
    return [n for n in names if n and n not in ("et al", "et al.")]


def _title_similarity(claimed, registry):
    a, b = _title_key(_fold(claimed)), _title_key(_fold(registry))
    if not a or not b:
        return 0.0
    if a in b or b in a:                  # main title vs. title with subtitle
        return 1.0 if min(len(a), len(b)) >= 20 else 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def _match_title(claimed, registry):
    if not (claimed or "").strip():
        return "not given"
    s = _title_similarity(claimed, registry)
    return "yes" if s >= 0.9 else "partly" if s >= 0.6 else "no"


def _match_authors(claimed, registry_authors):
    names = _claimed_family_names(claimed)
    if not names:
        return "not given"
    reg = {_fold(a.get("family", "")) for a in registry_authors or []}
    reg |= {part for r in reg for part in r.split()}   # "van der Berg" -> "berg"
    if names[0] in reg or names[0].split()[-1] in reg:
        return "yes"
    if any(n in reg for n in names):
        return "partly"
    return "no"


def _match_year(claimed, registry_year):
    if claimed in (None, ""):
        return "not given"
    try:
        diff = abs(int(str(claimed)[:4]) - int(registry_year))
    except (TypeError, ValueError):
        return "no"
    # Online-first and print years often differ by one.
    return "yes" if diff == 0 else "close" if diff == 1 else "no"


def _title_candidates(title):
    """Registry records whose title resembles `title`, DOI-bearing only.

    OpenAlex's title search ranks an exact title first; Crossref's
    bibliographic search buries famous papers under review notices, so it
    only fills in when OpenAlex is unreachable or finds nothing."""
    out = []
    try:
        url = _openalex_url("works", {"filter": "title.search:" + title.replace(",", " "),
                                      "per-page": 10})
        for w in _get_patient(url).get("results", []):
            doi = _norm_doi(w.get("doi"))
            if doi and _citable(w.get("title") or "", doi):
                out.append({"doi": doi, "title": w.get("title") or "",
                            "authors": _openalex_authors(w),
                            "year": w.get("publication_year")})
    except Exception as e:
        print(f"# openalex title search failed: {e}", file=sys.stderr)
    if not out:
        try:
            q = urllib.parse.urlencode({"query.bibliographic": title, "rows": 20,
                                        "select": "DOI,title,author,issued,type"})
            for it in _get(f"https://api.crossref.org/works?{q}")["message"]["items"]:
                doi = _norm_doi(it.get("DOI"))
                t = (it.get("title") or [""])[0]
                if doi and _citable(t, doi):
                    out.append({"doi": doi, "title": t, "authors": _crossref_authors(it),
                                "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0]})
        except Exception as e:
            print(f"# crossref title search failed: {e}", file=sys.stderr)
    return out


def _find_by_title(title, authors=None, year=None):
    """(match, closest) for a claim with no DOI.

    `match` is a registry hit whose title matches AND whose authors match when
    the claim names any; a famous title is often reused by unrelated papers
    ("Attention is all you need: an analysis of ..."), so a title alone is not
    enough. `closest` is the best title hit, reported when nothing matched."""
    hits = _title_candidates(title)
    ranked = sorted(hits, key=lambda h: _title_similarity(title, h.get("title", "")),
                    reverse=True)
    closest = ranked[0] if ranked else None
    for h in ranked:
        if _title_similarity(title, h.get("title", "")) < 0.9:
            break
        if _match_authors(authors, h.get("authors")) in ("yes", "not given") and \
                _match_year(year, h.get("year")) != "no":
            return h, closest
    return None, closest


def check(item):
    """Compare one claimed paper with its registry record.

    verdict is one of: ok, mismatch, retracted, not-found, no-doi, unknown.
    `reason` says why in one plain sentence, for the student."""
    claimed = {"doi": _norm_doi(item.get("doi")), "title": item.get("title") or "",
               "authors": item.get("authors") or [], "year": item.get("year")}
    result = {"claimed": claimed}
    doi, found_by_title = claimed["doi"], False
    if not doi:
        hit, closest = (_find_by_title(claimed["title"], claimed["authors"], claimed["year"])
                        if claimed["title"] else (None, None))
        if not hit:
            reason = ("No DOI given and no registry record with this title and these "
                      "authors was found. Books, reports, laws and web pages often have "
                      "no DOI; the student has to confirm this source by hand.")
            if closest:
                names = ", ".join(a.get("family", "") for a in closest.get("authors", [])[:3])
                reason += (f" Closest record, probably a different work: \"{closest.get('title')}\""
                           f" ({names}, {closest.get('year')}, doi {closest.get('doi')}).")
            result.update(verdict="no-doi", reason=reason)
            return result
        doi, found_by_title = hit["doi"], True
    v = verify(doi)
    v.pop("abstract", None)
    result["registry"] = v
    result["doi_found_by_title"] = found_by_title
    if v["status"] in ("absent", "invalid"):
        result.update(verdict="not-found", reason=(
            f"The DOI {doi} does not exist at Crossref or DataCite"
            + (f" ({v['error']})" if v.get("error") else "")
            + ". The paper may be invented, or the DOI mistyped."))
        return result
    if v["status"] != "resolved":
        result.update(verdict="unknown", reason=(
            "The registries could not be reached (" + (v.get("error") or "network")
            + "). Nothing is known about this DOI yet; try again later."))
        return result
    m = {"title": _match_title(claimed["title"], v.get("title", "")),
         "authors": _match_authors(claimed["authors"], v.get("authors")),
         "year": _match_year(claimed["year"], v.get("year"))}
    result["match"] = m
    if v.get("retracted"):
        kinds = ", ".join(n["type"] for n in v.get("notices", []))
        result.update(verdict="retracted", reason=(
            f"The registry lists a notice on this paper ({kinds}). "
            "A retracted paper cannot support a claim in a thesis."))
    elif "no" in m.values() or "partly" in m.values():
        wrong = ", ".join(k for k, val in m.items() if val in ("no", "partly"))
        result.update(verdict="mismatch", reason=(
            f"The DOI exists, but the {wrong} do not match the registry record "
            f"(\"{v.get('title', '')}\", {v.get('year')}). "
            "Either the DOI or the description is wrong."))
    else:
        note = " (found by title)" if found_by_title else ""
        extra = ""
        if v.get("notices"):
            extra = " Note: the registry lists " + ", ".join(
                n["type"] for n in v["notices"]) + " notice(s); read them before citing."
        result.update(verdict="ok", reason=(
            f"The DOI exists and matches the registry record{note}." + extra))
    return result


# ---------------------------------------------------------------------------
# details: abstract and free full-text link
# ---------------------------------------------------------------------------

def _openalex_abstract(inverted):
    """OpenAlex stores abstracts as {word: [positions]}; put the words back."""
    slots = []
    for word, positions in (inverted or {}).items():
        for p in positions:
            slots.append((p, word))
    return " ".join(w for _, w in sorted(slots))


def details(doi):
    v = verify(doi)
    if v["status"] != "resolved":
        return v
    try:
        w = _get_patient(_openalex_url("works/doi:" + urllib.parse.quote(v["doi"]), {}))
        oa = w.get("open_access") or {}
        v["free_fulltext_url"] = oa.get("oa_url")
        v["cited_by_count"] = w.get("cited_by_count")
        if w.get("is_retracted"):
            v["retracted"] = True
        if not v.get("abstract"):
            v["abstract"] = _openalex_abstract(w.get("abstract_inverted_index"))
    except Exception as e:
        v["free_fulltext_url"] = None
        v["openalex_error"] = str(e)
    v["abstract_source"] = "registry" if v.get("abstract") else "none"
    return v


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="sources.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    p_find = sub.add_parser(
        "find", help="Search Crossref/OpenAlex for citable sources on a topic.")
    p_find.add_argument("topic", help="Topic to search for, e.g. 'retrieval augmented generation'")
    p_find.add_argument("--n", type=int, default=12, help="Maximum results to return (default: 12)")
    p_find.add_argument("--json", action="store_true",
                         help="Print the raw JSON array instead of a human-readable list. "
                              "This is the format scripts/citations.py build expects.")
    preprint_group = p_find.add_mutually_exclusive_group()
    preprint_group.add_argument(
        "--include-preprints", dest="include_preprints", action="store_true", default=True,
        help="Include Crossref posted-content such as arXiv/SSRN preprints (default).")
    preprint_group.add_argument(
        "--no-preprints", dest="include_preprints", action="store_false",
        help="Exclude posted-content entirely (journal articles, proceedings, "
             "chapters, reports, monographs only).")

    p_verify = sub.add_parser(
        "verify", help="Verify one or more DOIs resolve via Crossref then DataCite.")
    p_verify.add_argument("dois", nargs="+", help="One or more DOIs to verify")

    p_check = sub.add_parser(
        "check", help="Compare claimed papers (JSON list) with their registry records.")
    p_check.add_argument(
        "file", help='JSON file with [{"doi", "title", "authors", "year"}, ...], or - for stdin')

    p_details = sub.add_parser(
        "details", help="verify plus abstract and free full-text link, per DOI.")
    p_details.add_argument("dois", nargs="+", help="One or more DOIs")

    return parser


def _print_human(results):
    if not results:
        print("No citable sources found.")
        return
    for r in results:
        names = ", ".join(_display_name(a) for a in r["authors"][:3])
        if len(r["authors"]) > 3:
            names += " et al."
        venue = r.get("venue") or "(no venue)"
        print(f"{r['doi']}  [{r.get('type')}]")
        print(f"    {r['title']}")
        print(f"    {names} ({r.get('year')}) - {venue}")


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "find":
        status = {}
        results = find(args.topic, n=args.n,
                       include_preprints=args.include_preprints, status=status)
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            _print_human(results)
        # "No sources exist for this topic" and "no search reached an API" are
        # different facts and must not share an exit code. If every API this
        # call tried raised, the search never happened.
        attempted, failed = status.get("attempted", []), status.get("failed", [])
        if attempted and len(failed) == len(attempted):
            print(f"# no source API could be reached ({', '.join(failed)}); "
                  "this is a failed search, not an empty topic", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "verify":
        res = [verify(d) for d in args.dois]
        for r in res:
            r.pop("abstract", None)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in res) else 0

    if args.cmd == "check":
        raw = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        items = json.loads(raw)
        if isinstance(items, dict):
            items = [items]
        res = [check(it) for it in items]
        print(json.dumps(res, indent=2, ensure_ascii=False))
        counts = {}
        for r in res:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        print("# " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)
        # Exit 1 only when the registries could not be asked: a mismatch is an
        # answer, "unknown" is not.
        return 1 if counts.get("unknown") else 0

    if args.cmd == "details":
        res = [details(d) for d in args.dois]
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in res) else 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
