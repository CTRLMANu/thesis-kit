#!/usr/bin/env python3
"""Find papers, check references against the scholarly registries (Crossref,
DataCite, doi.org and OpenAlex: open services, no API key) and add them to
thesis/sources.md. Part of thesis-kit; standard library only.

    sources.py find "topic" [--n 12] [--no-preprints]    prints {"ranked_by", "works"}
    sources.py check FILE          (a JSON list, or - to read it from stdin)
    sources.py add FILE [--found-via TEXT]       (FILE may be a .bib or .ris export)
    sources.py details DOI [DOI ...]   (the record, abstract and free full-text link)
    sources.py pdf FILE [--pages A-B] [--find "term1|term2"]   (pages 1-2 by default)

A check item is {"ref": "<the reference as given>", "title", "authors", "year",
"journal"} or {"pdf": "<file>", ...}. The DOI comes from the reference text or
the PDF, never from a "doi" field; works without one are looked up by title and
authors. Verdicts: ok, mismatch, retracted, not-found, no-doi, unknown.

Exit 1: find when no service could be reached (not the same as "nothing
found"), details when a DOI did not resolve, check when a registry could not be
asked, add when none could; pdf exits 3 for a scanned PDF without text, 4 when
no PDF reader is installed. An optional free OpenAlex API key goes in
THESIS_KIT_OPENALEX_KEY or in the file .tools/openalex-key.
"""
import argparse
import datetime
import difflib
import html
import json
import os
import re
import ssl
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
USER_AGENT = "thesis-kit/1.0 (+https://github.com/CTRLMANu/thesis-kit)"


def _openalex_key():
    path = REPO / ".tools" / "openalex-key"
    key = os.environ.get("THESIS_KIT_OPENALEX_KEY", "").strip()
    return key or ((path.read_text(encoding="utf-8-sig").splitlines() or [""])[0].strip()
                   if path.exists() else "")


OPENALEX_KEY = _openalex_key()


def ssl_context():
    """Python from python.org on macOS has no certificates until its "Install
    Certificates" step is run; then trust the operating system's file instead."""
    context = ssl.create_default_context()
    if not context.cert_store_stats().get("x509_ca"):
        path = next((p for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt",
                                 "/etc/pki/tls/certs/ca-bundle.crt") if os.path.exists(p)), None)
        if path:
            context.load_verify_locations(cafile=path)
    return context


SSL_CONTEXT = ssl_context()


# ---- HTTP -------------------------------------------------------------------

class NotFound(Exception):
    """The service answered clearly: there is no such record."""


class RateLimited(Exception):
    """The service asks us to wait longer than is worth it, or its budget is used up."""


RATE_LIMITED = set()   # hosts that raised RateLimited; later requests to them fail at once
WAITED = set()         # hosts whose rate limit was waited out once in this run


def fetch_json(url, accept="application/json"):
    """GET a JSON document (`accept` picks the format, e.g. CSL-JSON at doi.org).

    Raises NotFound on 404. A rate limit (429, 503, an OpenAlex `retryAfter` body) is waited
    out once per host and run if it asks for at most 45 s (10 s when it does not say); else
    RateLimited is raised. Other failures are retried with a short backoff, then raised."""
    host = urllib.parse.urlsplit(url).netloc
    if host in RATE_LIMITED:
        raise RateLimited(f"{host} is rate-limited for now; try again later")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(3):
        body, retry_after, limited = "", "", False
        try:
            with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
                body = response.read().decode("utf-8", "replace")
            data = json.loads(body)
            if not (isinstance(data, dict) and data.get("retryAfter") and data.get("error")):
                return data
            error, limited = RuntimeError(data["error"]), True
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise NotFound(url)
            error, limited = err, err.code in (429, 503)
            retry_after = (err.headers or {}).get("Retry-After") or ""
            try:
                body = err.read().decode("utf-8", "replace")
            except Exception:
                pass
        except (urllib.error.URLError, OSError, ValueError) as err:
            error = err
        if limited:
            said = (re.findall(r'"retryAfter"\s*:\s*"?(\d+(?:\.\d+)?)', body)
                    or re.findall(r"^\s*(\d+(?:\.\d+)?)\s*$", retry_after))
            seconds = float(said[0]) if said else 0.0
            if seconds > 45 or re.search(r"budget|exhausted|quota", body, re.I) or host in WAITED:
                RATE_LIMITED.add(host)
                raise RateLimited(f"{host} is rate-limited for now; try again later")
            WAITED.add(host)
            time.sleep(seconds or 10.0)
        elif attempt < 2:
            time.sleep(0.5 * 2 ** attempt)
    raise error


def openalex_url(path, **params):
    if OPENALEX_KEY:
        params["api_key"] = OPENALEX_KEY
    return f"https://api.openalex.org/{path}?" + urllib.parse.urlencode(params)


# ---- Text and DOI helpers ---------------------------------------------------

DOI_SHAPE = re.compile(r"^10\.\d+(\.\d+)*/\S+$")
# A DOI inside running text, a link, a .bib or a .ris entry.
DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[^\s\"{}]+")
# What a publisher link adds after the DOI: ?query, #fragment, /full/html, .pdf.
LINK_TAIL = re.compile(r"[?#].*$|(/(full|html|abstract|abs|pdf|epdf|epub|fulltext))+$|\.pdf$")
# The DOI field of a .bib or .ris entry: it wins over a DOI in its url or abstract.
DOI_FIELD = re.compile(r"\bdoi\s*=\s*[{\"]([^}\"]*)|^DO[ \t]+-[ \t]*(.*)$", re.I | re.M)
OPENER = {")": "(", "]": "[", ">": "<"}


def bare_doi(value):
    """'https://doi.org/10.1/AbC', 'doi:10.1/AbC' -> '10.1/abc'."""
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", (value or "").strip().lower())
    return doi.rstrip(".,;")


def dois_in(text):
    """Every DOI in a piece of text, in order: '(doi:10.1/X(2)1).' -> ['10.1/x(2)1']."""
    found = []
    for match in DOI_IN_TEXT.finditer(text or ""):
        doi = match.group(0).rstrip(".,;'”’…")    # also closing quotes and ...
        # A closing bracket without its opener is around the DOI, not part of it.
        while doi[-1] in OPENER and doi.count(OPENER[doi[-1]]) < doi.count(doi[-1]):
            doi = doi[:-1].rstrip(".,;'”’…")
        found.append(bare_doi(doi))
    return list(dict.fromkeys(found))


def fold(text):
    """Lower case without accents, so 'Müller' and 'Muller' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def title_key(text):
    """Letters and digits only: two spellings of one title compare equal."""
    return "".join(c for c in fold(text) if c.isalnum())


def plain_text(markup):
    """Registry abstracts arrive as JATS or HTML; keep the words."""
    text = " ".join(re.sub(r"<[^>]+>", " ", markup or "").split())
    return re.sub(r"^abstract\s*[:.]?\s+", "", text, flags=re.I)


# The end of a title: footnote marks and a closing period ("...", "?" stay).
TITLE_END = re.compile(r"(?:[\s*†‡]|(?<!\.)\.)+$")


def clean_title(text):
    """Titles and venues arrive with markup, entities, footnote marks and a closing period."""
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    return TITLE_END.sub("", " ".join(text.split()))


def _first(value):
    return ((value or [""])[0] if isinstance(value, list) else value) or ""


def _person(family, given, name):
    """{"family", "given"} or None; a name without a family part (an organisation) is the family."""
    family, given, name = ((s or "").strip() for s in (family, given, name))
    if family or name or given:
        return {"family": family or name or given, "given": given if family else ""}


# ---- thesis/sources.md entries and their cite keys --------------------------

# A cite key: family name folded to a-z, then the year or "nd", then a, b, ...
# when taken. Chapters cite it as [@key]; the kit, not the AI, makes it.
KEY = r"[a-z]+(?:\d{4}|nd)[a-z]?"
_FIELD = re.compile(r"^- ([A-Za-z][A-Za-z ]*?):[ \t]*(.*?)\s*$")
_HEADING_SEP = re.compile(r"\s+[·–—-]\s+")


def read_entries(text):
    """The entries of a sources.md file, in order: {"heading", "label", "title", "fields"
    (lower-case name -> value), "key", "doi", "status" ("unchecked", "checked", "dropped" or
    ""), "line" (of the heading)}. Separators are read leniently ("·", "-", "–")."""
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("### "):
            heading = line[4:].strip()
            label, title = (_HEADING_SEP.split(heading, maxsplit=1) + [""])[:2]
            entries.append({"heading": heading, "label": label.strip(), "title": title.strip(),
                            "fields": {}, "line": number})
        elif entries and (field := _FIELD.match(line)):
            entries[-1]["fields"].setdefault(field.group(1).strip().lower(), field.group(2))
    for entry in entries:
        fields = entry["fields"]
        key = re.search(r"@(" + KEY + r")\b", fields.get("cite as", ""))
        status = re.match(r"(unchecked|checked|dropped)\b", fields.get("status", "").lower())
        entry.update(key=key.group(1) if key else "", doi=bare_doi(fields.get("doi", "")),
                     status=status.group(1) if status else "")
    return entries


def make_key(family, year, taken):
    """A new cite key not in `taken`: make_key("Müller", 2021, {"muller2021"}) -> "muller2021a"."""
    name = re.sub(r"[^a-z]", "", fold(family)) or "anon"
    year = str(year)[:4] if year and str(year)[:4].isdigit() else "nd"
    letters = [""] + list("abcdefghijklmnopqrstuvwxyz")
    # After muller2021z come mullera2021, mullera2021a, ...: KEY allows one letter after the year.
    return next(key for key in (name + more + year + suffix for more in letters for suffix in letters)
                if key not in taken)


# ---- Registry records: every service's answer becomes the same dictionary ---

def _record(**fields):
    return {"doi": "", "title": "", "authors": [], "year": None, "venue": "", "volume": "",
            "issue": "", "pages": "", "publisher": "", "type": "", "notices": [],
            "retracted": False, "abstract": "", **fields}


def _crossref_year(msg):
    """The print year when there is one: the year a reference list gives."""
    dates = (((msg.get(f) or {}).get("date-parts") or [[None]])[0]
             for f in ("published-print", "issued"))
    return next((parts[0] for parts in dates if parts and parts[0]), None)


def from_crossref(msg):
    """A Crossref work, or a CSL-JSON record from doi.org."""
    notices = [{"type": (u.get("type") or "").lower(), "notice_doi": bare_doi(u.get("DOI"))}
               for u in msg.get("updated-by") or [] if u.get("type")]
    return _record(
        doi=bare_doi(msg.get("DOI")), title=clean_title(_first(msg.get("title"))),
        authors=[p for p in (_person(a.get("family"), a.get("given"),
                                     a.get("name") or a.get("literal"))
                             for a in msg.get("author") or []) if p],
        year=_crossref_year(msg), venue=clean_title(_first(msg.get("container-title"))),
        volume=msg.get("volume") or "", issue=msg.get("issue") or "",
        pages=msg.get("page") or "", publisher=msg.get("publisher") or "",
        type=msg.get("type") or "", notices=notices,
        retracted=any(n["type"] in ("retraction", "withdrawal", "removal") for n in notices),
        abstract=plain_text(msg.get("abstract")), cited_by_count=msg.get("is-referenced-by-count"))


def from_datacite(attrs):
    publisher = attrs.get("publisher")
    abstract = next((d.get("description", "") for d in attrs.get("descriptions") or []
                     if d.get("descriptionType") == "Abstract"), "")
    return _record(
        doi=bare_doi(attrs.get("doi")),
        title=clean_title(((attrs.get("titles") or [{}])[0] or {}).get("title", "")),
        authors=[p for p in (_person(c.get("familyName"), c.get("givenName"), c.get("name"))
                             for c in attrs.get("creators") or []) if p],
        year=attrs.get("publicationYear"),
        venue=clean_title((attrs.get("container") or {}).get("title")),
        publisher=(publisher.get("name") if isinstance(publisher, dict) else publisher) or "",
        type=((attrs.get("types") or {}).get("resourceTypeGeneral") or "").lower(),
        abstract=plain_text(abstract))


def from_openalex(work):
    source = (work.get("primary_location") or {}).get("source") or {}
    # OpenAlex gives one display name; read the last word as the family name.
    names = [((a.get("author") or {}).get("display_name") or "").split()
             for a in work.get("authorships") or []]
    return _record(
        doi=bare_doi(work.get("doi")),
        title=clean_title(work.get("title") or work.get("display_name")),
        authors=[{"family": n[-1], "given": " ".join(n[:-1])} for n in names if n],
        year=work.get("publication_year"), venue=clean_title(source.get("display_name")),
        publisher=source.get("host_organization_name") or "", type=work.get("type") or "",
        retracted=bool(work.get("is_retracted")), cited_by_count=work.get("cited_by_count"),
        openalex_id=(work.get("id") or "").rsplit("/", 1)[-1])


def lookup(doi):
    """Resolve one DOI at Crossref, then DataCite, then doi.org: status resolved,
    absent, unknown or invalid. 'absent' needs a clear 'no such record' from all
    three; when one could not be asked, it is 'unknown'. A DOI copied from a
    publisher link ('.../full', '?scroll=top') is tried again without that tail."""
    doi = bare_doi(doi)
    if not DOI_SHAPE.match(doi):
        return {"doi": doi, "status": "invalid",
                "error": "not a DOI (a DOI looks like 10.1234/something)"}
    quoted, problem = urllib.parse.quote(doi), None
    # doi.org knows every DOI, also those registered elsewhere (EU Publications
    # Office, JaLC, ISTIC, KISTI, mEDRA); its 404 means there is none.
    for agency, url, accept, convert in (
            ("crossref", f"https://api.crossref.org/works/{quoted}", "application/json",
             lambda data: from_crossref(data["message"])),
            ("datacite", f"https://api.datacite.org/dois/{quoted}", "application/json",
             lambda data: from_datacite(data["data"]["attributes"])),
            ("doi.org", f"https://doi.org/{quoted}", "application/vnd.citationstyles.csl+json",
             from_crossref)):
        if problem and agency == "doi.org":
            break                       # asked only when both registries said no
        try:
            return dict(convert(fetch_json(url, accept=accept)), doi=doi, status="resolved",
                        agency=agency)
        except NotFound:
            pass
        except Exception as err:
            problem = f"{agency}: {err}"
    if problem:
        return {"doi": doi, "status": "unknown", "error": problem}
    trimmed = LINK_TAIL.sub("", doi)
    if trimmed != doi and DOI_SHAPE.match(trimmed):
        found = lookup(trimmed)
        if found["status"] != "absent":
            return found
    return {"doi": doi, "status": "absent"}


def details(doi, rec=None):
    """The registry record (`rec` when already looked up) with OpenAlex's free
    full-text link, citation count, retraction flag and, if missing, abstract."""
    rec = rec or lookup(doi)
    if rec["status"] != "resolved":
        return rec
    rec["free_fulltext_url"] = None
    try:
        work = fetch_json(openalex_url("works/doi:" + urllib.parse.quote(rec["doi"])))
        rec["free_fulltext_url"] = (work.get("open_access") or {}).get("oa_url")
        rec["cited_by_count"] = work.get("cited_by_count")
        rec["retracted"] = rec["retracted"] or bool(work.get("is_retracted"))
        # OpenAlex stores an abstract as {word: [positions]}.
        words = sorted((pos, word) for word, positions in
                       (work.get("abstract_inverted_index") or {}).items() for pos in positions)
        rec["abstract"] = rec["abstract"] or " ".join(word for _, word in words)
    except NotFound:
        pass
    except Exception as err:
        rec["openalex_error"] = str(err)
    return rec


# ---- find: search for works on a topic --------------------------------------

PREPRINTS = {"posted-content", "preprint"}
PUBLISHED = {"journal-article", "proceedings-article", "book-chapter", "book",
             "monograph", "edited-book", "report", "article", "review"}
# The citable types in Crossref's vocabulary, which has no "article" or "review".
CROSSREF_CITABLE = PUBLISHED - {"article", "review"} | {"posted-content"}
OPENALEX_FIELDS = ("id,doi,title,authorships,publication_year,type,is_retracted,"
                   "primary_location,cited_by_count")
CROSSREF_FIELDS = ("DOI,title,author,issued,published-print,container-title,type,"
                   "publisher,volume,issue,page,updated-by,is-referenced-by-count")
# Registries index peer-review reports, decision letters, corrections and
# recommendation notes as works of their own; none of them is citable.
NOT_A_WORK = re.compile(
    r"^(review (for|of)|book review|decision letter|author response|reviewer report"
    r"|peer review|correction|corrigendum|erratum|retraction|expression of concern"
    r"|faculty opinions recommendation)", re.I)


def citable(rec, allowed_types):
    title = rec["title"].strip()
    # Without a journal or book: blog-post DOIs, and bare one-name records.
    weak = not rec["venue"] and (rec["publisher"].strip().lower() == "front matter"
                                 or len(rec["authors"]) == 1 and not rec["authors"][0]["given"])
    return bool(rec["doi"] and title and rec["authors"] and rec["type"] in allowed_types
                and not rec["retracted"] and not weak and not NOT_A_WORK.match(title)
                and not re.search(r"/(review|decision)\d+$", rec["doi"]))   # review reports


def openalex_works(**params):
    data = fetch_json(openalex_url("works", **params, select=OPENALEX_FIELDS))
    return [from_openalex(work) for work in data.get("results", [])]


def crossref_works(query, rows, types, author=None):
    params = {"query.bibliographic": query, "rows": rows, "select": CROSSREF_FIELDS,
              "filter": ",".join("type:" + t for t in sorted(types))}
    if author:
        params["query.author"] = author
    data = fetch_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
    return [from_crossref(item) for item in data["message"]["items"]]


def search(topic, n=12, preprints=True):
    """Citable works on `topic` as (works, ranked_by): OpenAlex's, ranked by relevance and
    citations, else Crossref's (weaker ranking), else ([], None). The DOIs are not checked
    here: `details` and `add` check them later."""
    allowed = PUBLISHED | (PREPRINTS if preprints else set())
    types = "article|review|book|book-chapter" + ("|preprint" if preprints else "")
    try:
        records, ranked_by = openalex_works(search=topic, filter="type:" + types,
                                            **{"per-page": min(3 * n, 100)}), "openalex"
    except Exception as err:
        print(f"# openalex search failed, trying crossref: {err}", file=sys.stderr)
        try:
            records = crossref_works(topic, max(5 * n, 50), allowed & CROSSREF_CITABLE)
            ranked_by = "crossref"
        except Exception as err2:
            print(f"# crossref search failed: {err2}", file=sys.stderr)
            return [], None
    found = []
    for rec in filter(lambda r: citable(r, allowed), records):
        if len(found) >= n:
            break
        # A preprint and its journal version: other DOIs, same title; keep the journal one.
        key = title_key(rec["title"])
        same = [i for i, other in enumerate(found) if other["doi"] == rec["doi"]
                or (key and key == title_key(other["title"]))]
        if not same:
            found.append(rec)
        elif found[same[0]]["type"] in PREPRINTS and rec["type"] not in PREPRINTS:
            found[same[0]] = rec
    return found, ranked_by


# ---- PDF text ---------------------------------------------------------------

class PdfError(Exception):
    """The PDF's text could not be read; `code` is the command's exit code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


PDF_TOOLS = REPO / ".tools" / "python"
NO_PDF_READER = ("No PDF reader is installed. Install one into the workspace (no admin rights "
                 "needed):\n    python3 -m pip install --target .tools/python pypdf\nOn Windows:\n"
                 "    py -3 -m pip install --target .tools/python pypdf")
# macOS reads PDFs with PDFKit, which JavaScript for Automation can call.
PDFKIT_JS = """ObjC.import("PDFKit");
function run(argv) {
  var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  if (doc.isNil()) return "null";
  var count = Number(doc.pageCount), last = Math.min(Number(argv[2]) || count, count), pages = [];
  for (var i = Number(argv[1]) - 1, text; i < last; i++)
    pages.push((text = doc.pageAtIndex(i).string).isNil() ? "" : text.js);
  return JSON.stringify({count: count, pages: pages});
}"""


def _extract(path, first, last):
    """(page count, [text of pages first..last]) from PDFKit on macOS, else pypdf."""
    if sys.platform == "darwin":
        try:
            data = json.loads(subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", PDFKIT_JS, os.path.abspath(path),
                 str(first), str(last or 0)],
                capture_output=True, encoding="utf-8", errors="replace", timeout=300).stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            data = False            # osascript did not work: try pypdf
        if data is None:
            raise PdfError(1, f"{path} is not a PDF that can be opened")
        if data:
            return int(data["count"]), data["pages"]
    if str(PDF_TOOLS) not in sys.path:
        sys.path.insert(0, str(PDF_TOOLS))
    try:
        from pypdf import PdfReader
    except ImportError:
        raise PdfError(4, NO_PDF_READER)
    try:
        pages = PdfReader(path).pages
        return len(pages), [pages[i].extract_text() or ""
                            for i in range(first - 1, min(last or len(pages), len(pages)))]
    except Exception as err:
        raise PdfError(1, f"{path} could not be read as a PDF ({err})")


def read_pdf(path, first=1, last=None):
    """(page count, [text of pages first..last]); raises PdfError. A path not
    found from here is tried in thesis/, as sources.md's `PDF:` lines give it."""
    if not os.path.isfile(path) and (REPO / "thesis" / path).is_file():
        path = str(REPO / "thesis" / path)
    if not os.path.isfile(path):
        raise PdfError(1, f"no file {path}")
    count, pages = _extract(path, first, last)
    if first > count:
        raise PdfError(1, f"{path} has only {count} pages")
    if not any(page.strip() for page in pages):
        raise PdfError(3, "scanned PDF, no text to read")
    return count, pages


def pdf_pages(path, first=1, last=None):
    """The text of pages first..last (1-based; last=None: to the end)."""
    return read_pdf(path, first, last)[1]


# arXiv prints a paper's identifier on page 1 ("arXiv:1706.03762v7"), and links
# show it too (arxiv.org/abs/1706.03762); DataCite registers it, without the
# version, as the DOI 10.48550/arXiv.1706.03762.
ARXIV_ID = re.compile(r"\barXiv(?::\s*|\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}|[a-z-]+/\d{7})(v\d+)?",
                      re.I)


def record_in_pdf(path):
    """The record of the PDF's own DOI: the first DOI (or arXiv identifier) on pages 1-2
    whose registry title the pages show too, as a first page often names other works'
    DOIs. Else None, or the 'unknown' record of a DOI that could not be looked up."""
    text = "\n".join(pdf_pages(path, 1, 2))
    page, unknown = title_key(text), None
    for doi in dois_in(ARXIV_ID.sub(r"10.48550/arXiv.\1 ", text)):
        rec = lookup(doi)
        key = title_key(main_title(rec.get("title")))
        if len(key) < 10:                       # 'Grit: ...': the main title is too short to tell
            key = title_key(rec.get("title"))
        if rec["status"] == "resolved" and len(key) >= 10 and key in page:
            return rec
        unknown = unknown or (rec if rec["status"] == "unknown" else None)
    return unknown


# ---- check: does a claimed work match its registry record? ------------------

# "et al." and the German "u. a." stand for authors not listed; they are not names.
OTHERS = re.compile(r"\bet\.?\s*al\b\.?|\bu\.\s*a\.|\band others\b", re.I)
PARTICLES = {"van", "von", "der", "den", "de", "da", "di", "du", "la", "le", "del",
             "dos", "das", "el", "al", "bin", "ibn", "ter", "ten", "zu"}
# Vancouver puts the initials after the family name: 'Topol EJ', 'Topol E. J.', 'Kim J-H'.
VANCOUVER = re.compile(r"(.+?)(?:\s+(?:[A-ZÄÖÜ]\.?-?){1,3})+")


def claimed_families(authors):
    """Family names, as written, from any shape: dicts, 'Müller, J.', 'J. Müller',
    'Müller & Schmidt', 'Jumper et al.', 'Topol EJ', or one comma-separated string."""
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
            elif (vancouver := VANCOUVER.fullmatch(" ".join(a.split()))):
                name = vancouver.group(1)
            else:
                words = [w for w in a.split() if len(w.strip(".")) > 1]
                name = words[-1] if words else a
        if name.strip(" ."):
            names.append(name.strip(" ."))
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


def _name_parts(name, particles=PARTICLES):
    """'van den Berg-Keles' -> {'berg', 'keles'}: the words of a name, without
    particles, unless the name is nothing else ('Du', 'Le')."""
    words = {w for w in re.split(r"\W+", fold(name)) if len(w) > 1}
    return (words - particles) or words


def match_authors(claimed, registry_authors):
    """Any word of a claimed family name against any word of a registry name, family or
    given: 'Keles' finds 'Keles-Gordesli', and a name whose parts a registry swapped counts."""
    names = claimed_families(claimed)
    if not names:
        return "not given"
    # All words: family and given are one string here, so 'Du Jian' keeps 'du'.
    known = set().union(*(_name_parts(f"{a.get('family', '')} {a.get('given', '')}", set())
                          for a in registry_authors or []))
    if _name_parts(names[0]) & known:
        return "yes"
    return "partly" if any(_name_parts(n) & known for n in names[1:]) else "no"


def match_year(claimed, registry_year):
    claimed = str(claimed or "")[:4]
    if not claimed.isdigit():
        return "not given"  # 'in press', 'n.d.', 'im Druck': no year to compare
    try:
        gap = abs(int(claimed) - int(registry_year))
    except (TypeError, ValueError):
        return "no"
    # Online-first and print years can be two apart (Santamouris: online 2012, issue 2014).
    return "yes" if gap == 0 else "close" if gap <= 2 else "no"


def find_by_title(title, authors=None, year=None):
    """(match, closest) among the records, with or without a DOI, whose title resembles
    `title`. Famous titles get reused ('Attention is all you need: ...'), so the authors
    (and roughly the year) have to fit too; a match with a DOI wins over one without.
    Raises the error when no search service answered."""
    found, reached = [], False
    try:          # OpenAlex's title search ranks an exact title first
        found = openalex_works(filter="title.search:" + title.replace(",", " "), **{"per-page": 10})
        reached = True
    except Exception as err:
        print(f"# openalex title search failed, trying crossref: {err}", file=sys.stderr)
    if not found:
        # Crossref buries famous papers under reviews of them: add first author and types.
        families = claimed_families(authors)
        try:
            found = crossref_works(title, 20, CROSSREF_CITABLE, families[0] if families else None)
        except Exception as err:
            print(f"# crossref title search failed: {err}", file=sys.stderr)
            if not reached:
                raise
    ranked = sorted((r for r in found if not NOT_A_WORK.match(r["title"].strip())),
                    key=lambda r: title_similarity(title, r["title"]), reverse=True)
    matches = [rec for rec in ranked if title_similarity(title, rec["title"]) >= 0.9
               and match_authors(authors, rec["authors"]) in ("yes", "not given")
               and match_year(year, rec["year"]) != "no"]
    match = next((m for m in matches if m["doi"]), matches[0] if matches else None)
    return match, (ranked[0] if ranked else None)


def indexed_journal(journal, year):
    """(name, number of its works in `year`) when OpenAlex indexes `journal`, else
    None. The exact name wins over a near one ('Journal of Business Research -
    Turk' is 93% like 'Journal of Business Research')."""
    want = title_key(journal)
    results = fetch_json(openalex_url("sources", search=journal, select="id,display_name",
                                      **{"per-page": 10})).get("results", [])
    exact_first = sorted(results, key=lambda s: title_key(s.get("display_name")) != want)
    source = next((s for s in exact_first if difflib.SequenceMatcher(
        None, title_key(s.get("display_name")), want).ratio() >= 0.9), None)
    if not source:
        return None
    source_id = (source.get("id") or "").rsplit("/", 1)[-1]
    works = fetch_json(openalex_url(
        "works", filter=f"primary_location.source.id:{source_id},publication_year:{year}",
        select="id", **{"per-page": 1}))
    return source.get("display_name"), (works.get("meta") or {}).get("count") or 0


UNREACHABLE = ("The registries could not be reached ({}). Nothing is known about this work "
               "yet; try again later.")


def check(item):
    """One verdict for one claimed work, `item` as in the module docstring. The
    DOI comes from the reference text, else from the PDF's first two pages, else
    from a title search. `short` is a reason of a few words for sources.md."""
    ref, pdf = item.get("ref") or "", item.get("pdf") or ""
    title, authors, year = item.get("title") or "", item.get("authors") or [], item.get("year")
    result = {"claimed": {k: item[k] for k in ("ref", "pdf", "title", "authors", "year", "journal")
                          if item.get(k)}, "doi_source": None}
    families, ref_key = (claimed_families(authors), title_key(ref)) if ref else ([], "")
    # Claimed details the reference text does not show were not copied from it.
    unsure = ref and not ((not title or title_key(title) in ref_key)
                          and (not families or title_key(families[0]) in ref_key)
                          and (not year or str(year) in ref))

    def verdict(name, reason, short=""):
        note = " (some details were not found in the reference text)" if unsure else ""
        return dict(result, verdict=name, reason=reason + note, short=short)

    rec = source = None
    try:
        field = DOI_FIELD.search(ref)
        dois = (dois_in(field and "".join(filter(None, field.groups()))) or dois_in(ref)
                or dois_in(ARXIV_ID.sub(r"10.48550/arXiv.\1 ", ref)))
        if dois:
            rec, source = lookup(dois[0]), "ref"
        elif pdf:
            try:
                rec, source = record_in_pdf(pdf), "pdf"
            except PdfError as err:
                if not title:
                    return verdict("no-doi", f"The PDF could not be read ({err}); give its "
                                   "title and authors.", "PDF could not be read")
        if rec is None:
            if not title:
                return verdict("no-doi", "No DOI found and no title given; give its title "
                               "and authors.", "no DOI and no title")
            match, closest = find_by_title(title, authors, year)
            if match and not match["doi"]:
                return verdict("no-doi", f"OpenAlex lists this work ({match['openalex_id']}) "
                               "without a DOI; confirm it by hand.",
                               "OpenAlex lists it without a DOI")
            if not match:
                return verdict(*_no_match(item.get("journal"), year, closest))
            rec, source = lookup(match["doi"]), "title search"
            # Title and author fit every edition of a book and its handbook
            # chapters; a DOI found by title needs the claimed year itself.
            if rec["status"] == "resolved" and match_year(year, rec["year"]) == "close":
                return verdict(*_no_match(None, year, rec))
    except Exception as err:
        return verdict("unknown", UNREACHABLE.format(err), "registries could not be reached")

    rec.pop("abstract", None)
    result.update(doi_source=source, registry=rec)
    if rec["status"] in ("absent", "invalid"):
        error = f" ({rec['error']})" if rec.get("error") else ""
        return verdict("not-found", f"The DOI {rec['doi']} does not exist{error}. The work may "
                       "be invented, or the DOI mistyped.", "the DOI does not exist")
    if rec["status"] != "resolved":
        return verdict("unknown", UNREACHABLE.format(rec.get("error", "network")),
                       "registries could not be reached")
    result["match"] = match = {"title": match_title(title, rec["title"]),
                               "authors": match_authors(authors, rec["authors"]),
                               "year": match_year(year, rec["year"])}
    notices = ", ".join(n["type"] for n in rec["notices"])
    if rec["retracted"]:
        return verdict("retracted", f"The registry lists a notice on this work "
                       f"({notices or 'retraction'}). A retracted work cannot support a claim "
                       "in a thesis.", "the registry lists a retraction")
    wrong = [k for k, v in match.items() if v in ("no", "partly")]
    if wrong:
        listed = " and ".join(filter(None, [", ".join(wrong[:-1]), wrong[-1]]))
        one = len(wrong) == 1
        return verdict("mismatch", (
            f"The DOI exists, but the {listed} {'does' if one else 'do'} not match the registry "
            f"record (\"{rec['title']}\", {rec['year']}). Either the DOI or the description is "
            "wrong."), f"{listed} {'differs' if one else 'differ'} from the DOI's record")
    note = " (found by title)" if source == "title search" else ""
    if notices:
        note += f". Note: the registry lists {notices} notice(s); read them before citing"
    said = ("exists; no title, authors or year were given to compare"
            if set(match.values()) == {"not given"} else "exists and matches the registry record")
    return verdict("ok", f"The DOI {said}{note}.")


def _no_match(journal, year, closest):
    """(verdict, reason, short) for a work no registry record matches: suspicious when
    OpenAlex indexes its journal for that year but not the article; else maybe no DOI."""
    hint = ""
    if closest:
        names = ", ".join(a["family"] for a in closest["authors"][:3])
        where = (f"doi {closest['doi']}" if closest["doi"]
                 else f"OpenAlex {closest.get('openalex_id')}")
        hint = (f" Closest record, probably a different work: \"{closest['title']}\" "
                f"({names}, {closest['year']}, {where}).")
    year = str(year or "")[:4]
    found = indexed_journal(journal, year) if journal and year.isdigit() else None
    if found and found[1]:
        return ("not-found", f"The journal {found[0]} is indexed ({found[1]} works in {year}), "
                "but no article with this title and these authors. It may be invented." + hint,
                "journal indexed, but no such article in it")
    note = (" Books, reports, laws and web pages often have no DOI; the student confirms "
            "such a source by hand." if not journal
            else " No year was given to check the journal with; confirm it by hand."
            if not year.isdigit()
            else f" The journal \"{journal}\" is not indexed in OpenAlex; confirm it by hand."
            if not found
            else f" OpenAlex lists no works of {found[0]} from {year}; confirm it by hand.")
    return ("no-doi", "No DOI found, and no registry record with this title and these "
            "authors." + note + hint, "no registry record found")


# ---- add: check works and append them to thesis/sources.md ------------------

# LaTeX accents as combining marks, and the letters LaTeX writes as commands.
LATEX_ACCENTS = {"`": "\u0300", "'": "\u0301", "^": "\u0302", '"': "\u0308", "~": "\u0303",
                 "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
                 "c": "\u0327", "k": "\u0328", "r": "\u030a"}
LATEX_LETTERS = {"ss": "ß", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å",
                 "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "i": "i"}


def _latex(value):
    """'{M{\\"{u}}ller}' -> 'Müller': apply accents, drop braces and escapes."""
    value = re.sub(r"\\(ss|ae|AE|oe|OE|aa|AA|o|O|l|L|i)(?![A-Za-z])(?:\{\}|\s)?",
                   lambda m: LATEX_LETTERS[m[1]], value)
    value = re.sub(r"\\([`'^\"~=.])\s*\{?([A-Za-z])\}?|\\([uvHckr])(?:\s*\{([A-Za-z])\}|\s+([A-Za-z]))",
                   lambda m: (m[2] or m[4] or m[5]) + LATEX_ACCENTS[m[1] or m[3]], value)
    value = re.sub(r"\\[`'^\"~=.]|\\(?=[&%$#_])|[{}]", "", value)
    return " ".join(unicodedata.normalize("NFC", value).split())


def _close(text, pos, stop="}"):
    """The index of the first `stop` outside braces from `pos` on (len(text) if none)."""
    depth = 0
    for i in range(pos, len(text)):
        if depth == 0 and text[i] == stop:
            return i
        depth += {"{": 1, "}": -1}.get(text[i], 0)
    return len(text)


BIB_FIELD = re.compile(r"(\w+)\s*=\s*([^,}\s{\"][^,}\s]*)?")    # group 2: a bare value (2019, jan)


def bib_fields(raw):
    """{name: value as written} of one BibTeX entry; a quoted value ends outside braces."""
    fields, pos = {}, 0
    while (match := BIB_FIELD.search(raw, pos)):
        value, pos = match.group(2) or "", match.end()
        if not value and raw[pos:pos + 1] in ("{", '"'):
            end = _close(raw, pos + 1, "}" if raw[pos] == "{" else '"')
            value, pos = raw[pos + 1:end], end + 1
        fields[match.group(1).lower()] = value
    return fields


def _bib_names(value):
    """The names of a BibTeX author field: split on 'and' outside braces; a
    wholly {braced} name is an organisation, kept whole as {"name": ...}."""
    parts, depth, last = [], 0, 0
    for match in re.finditer(r"[{}]|\s+and\s+", value):
        depth += {"{": 1, "}": -1}.get(match.group(), 0)
        if depth == 0 and match.group().strip() == "and":
            parts.append(value[last:match.start()])
            last = match.end()
    parts = [p.strip() for p in parts + [value[last:]]]
    whole = [p.startswith("{") and p.endswith("}") and _close(p, 1) >= len(p) - 1 for p in parts]
    return [{"name": _latex(p)} if w else _latex(p) for p, w in zip(parts, whole) if _latex(p)]


def bib_items(text):
    """Check items from a BibTeX export; the raw entry is the reference as given."""
    items = []
    for start in re.finditer(r"@(?!comment\b|string\b|preamble\b)\w+\s*\{", text, re.I):
        raw = text[start.start():_close(text, start.end()) + 1]
        written = bib_fields(raw)
        fields = {name: _latex(value) for name, value in written.items()}
        items.append({"ref": raw, "title": fields.get("title", ""),
                      "authors": _bib_names(written.get("author", "")),
                      "year": (fields.get("year") or fields.get("date", ""))[:4],
                      "journal": fields.get("journal") or fields.get("journaltitle", "")})
    return items


def ris_items(text):
    """Check items from a RIS export; the raw entry is the reference as given."""
    items = []
    for raw in re.findall(r"^TY[ \t]+-.*?^ER[ \t]+-.*?$", text, re.M | re.S):
        tags = re.findall(r"^([A-Z][A-Z0-9])[ \t]+-[ \t]?(.*?)\s*$", raw, re.M)
        one = dict(reversed(tags))              # the first value of each tag
        items.append({"ref": raw, "title": one.get("TI") or one.get("T1", ""),
                      "authors": [v for t, v in tags if t == "AU"]
                      or [v for t, v in tags if t == "A1"],
                      "year": (one.get("PY") or one.get("Y1") or one.get("DA") or "")[:4],
                      "journal": one.get("JF") or one.get("JO") or one.get("T2", "")})
    return items


def read_items(file):
    """Check items from a JSON list (or - for stdin), a .bib or a .ris file."""
    text = (sys.stdin.read() if file == "-"
            else Path(file).read_text(encoding="utf-8-sig", errors="replace"))
    items = {".bib": bib_items, ".ris": ris_items}.get(Path(file).suffix.lower(), json.loads)(text)
    return items if isinstance(items, list) else [items]


def _one_line(text):
    return " ".join((text or "").split())


def _shorten(text, limit=60):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _published_in(rec):
    """'Nature 596(7873), 583–589'."""
    return "".join([rec["venue"] or rec["publisher"], rec["volume"] and f" {rec['volume']}",
                    rec["issue"] and f"({rec['issue']})",
                    rec["pages"] and ", " + rec["pages"].replace("-", "–")]).strip(" ,")


def label_family(label):
    """The first author in a heading label: 'Jumper et al. (2021)',
    'Flick & Kardorff (2019)', 'Flick und Kardorff', 'Flick u. a.' -> 'Jumper', 'Flick'."""
    return re.split(r"\s+(?:et al\b|&|and\b|und\b|u\. ?a\.)|\s*[(,]", label)[0].strip()


def add(items, found_via="", root=REPO):
    """Check the items, append the new works to thesis/sources.md, print a report:
    a line per added work with its label, full title and key, so it can be named
    as it is, and a line per verdict other than ok and per preprint."""
    path = root / "thesis" / "sources.md"
    text = (path if path.exists() else root / "kit" / "templates" / "sources.md").read_text(
        encoding="utf-8")
    today = datetime.date.today().isoformat()
    results = [check(item) for item in items]
    if results and all(r["verdict"] == "unknown" for r in results):
        print(f"nothing added: the registries could not be reached ({results[0]['reason']})")
        return 1
    added, already, report = 0, 0, []
    for item, result in zip(items, results):
        # The registry's description when the DOI resolved, else what was claimed.
        rec = result["registry"] if result.get("registry", {}).get("status") == "resolved" else None
        families = ([a["family"] for a in rec["authors"]] if rec
                    else claimed_families(item.get("authors")))
        title = (rec and rec["title"]) or _one_line(item.get("title"))
        year = str((rec and rec["year"]) or item.get("year") or "")[:4]
        year = year if year.isdigit() else "n.d."
        if not title:
            report.append(f'"{_shorten(item.get("pdf") or _one_line(item.get("ref")))}": '
                          f'not added — {result["reason"]}')
            continue
        names = families[0] + (" et al." if len(families) > 2 else f" & {families[1]}"
                               if len(families) == 2 else "") if families else "Anonymous"
        shown = f'{names} ({year}) "{_shorten(title)}"'
        entries = read_entries(text)
        same = next((e for e in entries if (rec and e["doi"] == rec["doi"])
                     or (title_key(e["title"]) == title_key(title)
                         and fold(label_family(e["label"])) == fold(label_family(names))
                         # Another DOI or another year: another edition or report.
                         and not (rec and e["doi"]) and (not year.isdigit() or re.findall(
                             r"\((\d{4})", e["label"])[:1] in ([], [year])))), None)
        if same:
            already += 1
            why = _HEADING_SEP.split(same["fields"].get("status", ""), maxsplit=2)[2:]
            report.append(f"{shown}: " + (
                f"dropped before: {why[0] if why else 'no reason given'}"
                if same["status"] == "dropped" else f"already there as [@{same['key']}]"
                if same["key"] else f"already there (line {same['line']}, no Cite as yet)"))
            continue
        title_word = next((w for w in re.findall(r"\w+", title) if len(w) > 3), "")
        key = make_key(families[0] if families else title_word, year, {e["key"] for e in entries})
        verdict, pdf = result["verdict"], item.get("pdf") or ""
        if pdf:
            try:
                pdf = Path(pdf).resolve().relative_to((root / "thesis").resolve()).as_posix()
            except ValueError:
                pass
        short = f": {result['short']}" if verdict != "ok" and result.get("short") else ""
        published = _published_in(rec) if rec else item.get("journal") or ""
        preprint = bool(rec) and rec["type"] in PREPRINTS
        if preprint:
            published = f"{published} (preprint)".strip()
        fields = [
            ("Cite as", f"[@{key}]"),
            ("Status", f"dropped · {today} · retracted" if verdict == "retracted" else "unchecked"),
            ("DOI", rec["doi"] if rec else ""),
            ("Registry check", f"{verdict}{short} · {today}"),
            ("Published in", published),
            ("Found via", found_via),
            ("Free full text", rec and details(rec["doi"], rec)["free_fulltext_url"]),
            ("PDF", pdf),
            # Kept for a mismatch too: which of the two is right is still open.
            ("Reference as given",
             "" if rec and verdict != "mismatch" else _one_line(item.get("ref"))),
        ]
        text = (text.rstrip("\n") + f"\n\n### {names} ({year}) · {title}\n"
                + "".join(f"- {k}: {v}\n" for k, v in fields if v)
                + "- In my own words:\n- Notes:\n")
        added += 1
        report.append(f"added ({'dropped' if verdict == 'retracted' else 'unchecked'}): "
                      f"{names} ({year}) · {title} [@{key}]" + (f" · {pdf}" if pdf else ""))
        if verdict != "ok":
            report.append(f"{shown}: {verdict} — {result['reason']}")
        if preprint:
            report.append(f"{shown}: preprint, not peer-reviewed; a journal version may exist")
    if added:
        temp = path.with_name(".sources.md.tmp")      # written whole, then swapped in
        with open(temp, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
        os.replace(temp, path)
    print(f"added {added} · already there {already}", *report, sep="\n")
    return 0


# ---- Command line -----------------------------------------------------------

def page_range(text):
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", text.strip())
    first, last = (int(match.group(1)), int(match.group(2) or match.group(1))) if match else (0, 0)
    if first < 1 or last < first:
        raise argparse.ArgumentTypeError("give pages like 3-5 or 7")
    return first, last


def main(argv=None):
    # Windows terminals and pipes default to a code page that cannot print "Müller".
    for stream, encoding in ((sys.stdin, "utf-8-sig"), (sys.stdout, "utf-8"),
                             (sys.stderr, "utf-8")):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding=encoding, errors="replace")
    parser = argparse.ArgumentParser(prog="sources.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    cmd = sub.add_parser("find", help="Search for citable works on a topic.")
    cmd.add_argument("topic")
    cmd.add_argument("--n", type=int, default=12, help="Maximum results (default 12)")
    cmd.add_argument("--no-preprints", action="store_true",
                     help="Leave out preprints (SSRN, arXiv, Research Square, ...)")
    sub.add_parser("check", help="Compare claimed works with the registries.").add_argument(
        "file", help="JSON file, or - for stdin")
    cmd = sub.add_parser("add", help="Check works and add them to thesis/sources.md.")
    cmd.add_argument("file", help="JSON list of works, a .bib or .ris export, or - for stdin")
    cmd.add_argument("--found-via", default="", help="The tool or person the student named, if any")
    sub.add_parser("details", help="Registry record, abstract and free full text.").add_argument(
        "dois", nargs="+")
    cmd = sub.add_parser("pdf", help="Print a PDF's text, or the paragraphs that match.")
    cmd.add_argument("file")
    cmd.add_argument("--pages", type=page_range, help="Pages to print or search, e.g. 3-5")
    cmd.add_argument("--find", help="Search terms, e.g. \"heat island|albedo\" (a regex)")
    args = parser.parse_args(argv)

    if args.cmd == "find":
        works, ranked_by = search(args.topic, n=args.n, preprints=not args.no_preprints)
        # One compact line per work: every line of an exposé's searches lands in the AI's context.
        for w in works:
            w["authors"] = (", ".join(a["family"] for a in w["authors"][:3])
                            + (" et al." if len(w["authors"]) > 3 else ""))
        keys = ("doi", "title", "authors", "year", "venue", "type", "cited_by_count")
        lines = [json.dumps({k: w.get(k) for k in keys}, ensure_ascii=False) for w in works]
        print('{"ranked_by": %s, "works": [\n%s\n]}' % (json.dumps(ranked_by), ",\n".join(lines)))
        if not ranked_by:
            print("# no search service could be reached: this is a failed search, "
                  "not an empty topic", file=sys.stderr)
        return 0 if ranked_by else 1

    if args.cmd == "check":
        results = [check(i) for i in read_items(args.file)]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        verdicts = [r["verdict"] for r in results]
        print("# " + " ".join(f"{v}={verdicts.count(v)}" for v in sorted(set(verdicts))),
              file=sys.stderr)
        return 1 if "unknown" in verdicts else 0

    if args.cmd == "add":
        if not (REPO / "thesis").is_dir():
            print("no thesis/ folder yet: set up the kit first (kit/workflows/setup.md)")
            return 1
        return add(read_items(args.file), args.found_via)

    if args.cmd == "details":
        results = [details(d) for d in args.dois]
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] != "resolved" for r in results) else 0

    if args.cmd == "pdf":
        try:
            pattern = re.compile(args.find, re.I) if args.find else None
        except re.error as err:
            print(f"--find is not a valid search pattern: {err}")
            return 2
        first, last = args.pages or ((1, None) if pattern else (1, 2))
        try:
            count, pages = read_pdf(args.file, first, last)
        except PdfError as err:
            print(err)
            return err.code
        if not pattern:
            print(f"pages: {count}")
            for number, text in enumerate(pages, first):
                print(f"--- PDF page {number} ---\n{text.rstrip()}")
            return 0
        hits = []
        for number, text in enumerate(pages, first):
            # Paragraphs: blank-line blocks, or lines when there are none (PDFKit).
            blocks = re.split(r"\n\s*\n", text)
            for block in (blocks if len(blocks) > 1 else text.splitlines()):
                block = " ".join(block.split())
                # PDF text often splits words at a fi or fl ligature ('signifi cance').
                joined = re.sub(r"(fi|fl) (?=[^\W\d_])", r"\1",
                                unicodedata.normalize("NFKC", block))
                if block and (pattern.search(block) or pattern.search(joined)):
                    hits.append((number, block))
        for number, block in hits[:20]:
            print(f"PDF page {number}: {block}")
        print(f"{len(hits)} {'match' if len(hits) == 1 else 'matches'}"
              + (", showing 20" if len(hits) > 20 else ""))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
