#!/usr/bin/env python3
"""Reference lists for thesis-kit, straight from the DOI registries.

No API key, standard library only. doi.org renders any Crossref or DataCite
DOI in any Citation Style Language (CSL) style ("DOI content negotiation").

    bibliography.py text --style apa [--locale en-US] DOI [DOI ...]
    bibliography.py csl-json DOI [DOI ...] -o references.json
    bibliography.py style apa -o DIR

text      prints one formatted reference per DOI, plain text (no italics).
          Author-year styles come out sorted; numeric styles (ieee) are
          numbered in the order the DOIs are given, which should be the order
          of first citation in the text.
csl-json  writes the records as CSL-JSON, for pandoc --citeproc, which
          renders them with proper italics inside a Word export.
style     downloads the CSL style file pandoc needs and prints its path.

Style names: apa, harvard, chicago, mla, ieee, din (DIN 1505-2), or any style
id from https://www.zotero.org/styles. A DOI that cannot be fetched is named
on stderr and the exit code is 1; those entries have to be written by hand.
"""
import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "thesis-kit/1.0 (+https://github.com/CTRLMANu/thesis-kit)"

STYLES = {
    "apa": "apa",
    "harvard": "harvard-cite-them-right",
    "chicago": "chicago-author-date",
    "mla": "modern-language-association",
    "ieee": "ieee",
    "din": "din-1505-2",
}
NUMERIC = {"ieee"}

# The registries' CSL renderer prints an empty editor list as "Edited by ,"
# (Harvard), ", edited by ," (MLA) or "In: (Hrsg.)" (DIN) when a journal
# article has no editors. Remove exactly those artifacts.
_ARTIFACTS = [
    (re.compile(r"\. Edited by ,\s*"), ", "),
    (re.compile(r", edited by ,\s*"), ", "),
    (re.compile(r"In: \(Hrsg\.\)\s*"), "In: "),
]


def style_id(name):
    return STYLES.get(name.lower(), name)


def _doi_url(doi):
    d = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.lower().startswith(prefix):
            d = d[len(prefix):]
    return "https://doi.org/" + urllib.parse.quote(d, safe="/()<>;:.-_")


def _fetch(url, accept, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        body = r.read().decode("utf-8", "replace")
    if "html" in ctype:
        # doi.org answers an unknown DOI with an HTML error page.
        raise ValueError("DOI not found at doi.org")
    return body


def reference_text(doi, style, locale):
    accept = f"text/x-bibliography; style={style_id(style)}; locale={locale}"
    text = _fetch(_doi_url(doi), accept).strip()
    if text.startswith("{") and '"style-not-found"' in text:
        raise ValueError(f"style {style_id(style)!r} is not available at doi.org")
    # DataCite DOIs come back with HTML markup; keep italics as markdown.
    text = re.sub(r"</?(i|em)>", "*", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"^\[\d+\]\s*", "", text)        # numbering is ours
    for pattern, repl in _ARTIFACTS:
        text = pattern.sub(repl, text)
    return re.sub(r"\s+", " ", text)


# The registries' CSL-JSON carries registry bookkeeping (license, funder,
# reference lists, ...) and some variables as lists; pandoc's citeproc rejects
# a list where CSL wants a string. Keep the standard variables, flattened.
_CSL_STRINGS = ["type", "title", "container-title", "container-title-short",
                "collection-title", "publisher", "publisher-place", "page", "volume",
                "issue", "number", "edition", "DOI", "URL", "ISBN", "ISSN",
                "language", "genre", "event", "version", "archive"]
_CSL_NAMES = ["author", "editor", "translator"]
_CSL_DATES = ["issued", "accessed"]
# Crossref answers with its own type names; CSL styles only know CSL types
# (an unknown type renders a journal article like a book chapter).
_CROSSREF_TO_CSL = {
    "journal-article": "article-journal", "proceedings-article": "paper-conference",
    "book-chapter": "chapter", "book-section": "chapter", "book-part": "chapter",
    "book": "book", "monograph": "book", "edited-book": "book", "reference-book": "book",
    "report": "report", "report-component": "report", "posted-content": "article",
    "dissertation": "thesis", "dataset": "dataset", "reference-entry": "entry",
    "standard": "standard",
}


def _clean_csl(raw, doi):
    rec = {"id": raw.get("DOI", doi).lower()}
    for key in _CSL_STRINGS:
        value = raw.get(key)
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, (str, int, float)) and str(value).strip():
            rec[key] = str(value).strip()
    if rec.get("type") in _CROSSREF_TO_CSL:
        rec["type"] = _CROSSREF_TO_CSL[rec["type"]]
    for key in _CSL_NAMES:
        people = []
        for p in raw.get(key) or []:
            person = {k: p[k] for k in ("family", "given", "literal", "suffix",
                                        "non-dropping-particle", "dropping-particle")
                      if isinstance(p.get(k), str) and p[k].strip()}
            if person:
                people.append(person)
        if people:
            rec[key] = people
    for key in _CSL_DATES:
        parts = (raw.get(key) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            rec[key] = {"date-parts": [[int(x) for x in parts[0] if x is not None]]}
    return rec


def csl_record(doi):
    raw = json.loads(_fetch(_doi_url(doi), "application/vnd.citationstyles.csl+json"))
    return _clean_csl(raw, doi)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bibliography.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    p_text = sub.add_parser("text", help="Formatted plain-text reference list.")
    p_text.add_argument("dois", nargs="+")
    p_text.add_argument("--style", default="apa")
    p_text.add_argument("--locale", default="en-US",
                        help="Language of words like 'and', 'et al.', 'pp.' (e.g. de-DE)")
    p_json = sub.add_parser("csl-json", help="CSL-JSON records for pandoc --citeproc.")
    p_json.add_argument("dois", nargs="+")
    p_json.add_argument("-o", "--output", required=True)
    p_style = sub.add_parser("style", help="Download a CSL style file for pandoc.")
    p_style.add_argument("name")
    p_style.add_argument("-o", "--outdir", required=True)
    args = parser.parse_args(argv)

    failed = []
    if args.cmd == "text":
        entries = []
        for doi in args.dois:
            try:
                entries.append(reference_text(doi, args.style, args.locale))
            except Exception as e:
                failed.append((doi, str(e)))
        if args.style.lower() in NUMERIC:
            lines = [f"[{i}] {e}" for i, e in enumerate(entries, 1)]
        else:
            lines = sorted(entries, key=str.casefold)
        print("\n\n".join(lines))
    elif args.cmd == "csl-json":
        records = []
        for doi in args.dois:
            try:
                records.append(csl_record(doi))
            except Exception as e:
                failed.append((doi, str(e)))
        Path(args.output).write_text(json.dumps(records, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
        print(f"wrote {len(records)} records to {args.output}")
    elif args.cmd == "style":
        sid = style_id(args.name)
        out = Path(args.outdir).expanduser() / f"{sid}.csl"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            xml = _fetch(f"https://www.zotero.org/styles/{urllib.parse.quote(sid)}", "*/*")
        except (urllib.error.HTTPError, ValueError) as e:
            print(f"# style {sid!r} could not be downloaded: {e}", file=sys.stderr)
            return 1
        out.write_text(xml, encoding="utf-8")
        print(out)
        return 0
    else:
        parser.print_help()
        return 2

    for doi, err in failed:
        print(f"# could not format {doi}: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
