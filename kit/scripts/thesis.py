#!/usr/bin/env python3
"""Save versions of the thesis, export it to Word, and read the Word file back.
Part of thesis-kit; standard library only. Export and sync need pandoc (see
kit/reference/tools.md). Exit code 1 means nothing was saved, exported or synced.

save "MESSAGE" [--tools "ChatGPT, Consensus"]  |  save --own-edits
    Adds a row to thesis/ai-log.md (unless the log is off or the edits are the
    student's own), saves a version of thesis/ (a git commit of thesis/ only),
    lists problems in the lines this save changed, and pushes to the online
    backup when there is one. The first line it prints is exactly one of
    "saved: <message>", "nothing new to save" or "NOT SAVED: <reason>".
export [FILE ...]
    Makes a new Word file in thesis/export/ from the chapters written in the kit
    (or the files named), with citations and the reference list in the
    profile's citation style. Never overwrites a file.
sync [DOCX] [--move CHAPTER ...]
    Mirrors the chapters of the student's Word file into thesis/chapters/ and
    writes its comments and tracked changes to thesis/feedback/word-comments.md.
    Chapters still written in the kit are only overwritten with --move. The
    Word file itself is never written.
"""
import argparse
import collections
import datetime
import difflib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import (KEY, SSL_CONTEXT, TITLE_END, USER_AGENT, NotFound, fetch_json, fold,  # noqa: E402
                     label_family, make_key, read_entries, title_key)

ROOT = Path(__file__).resolve().parents[2]
NO_VALUE = {"", "skipped", "don't know yet", "don’t know yet"}
# "AI log: no", "aus", "Nein": the log is off. Anything else, even no value, keeps it on.
LOG_OFF = re.compile(r"(off|no|nein|aus|false)\b", re.I)
FRONT = "00-front-matter.md"


def today():
    return datetime.date.today().isoformat()


def read(path):
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def write(path, text):
    Path(path).write_bytes(text.encode("utf-8"))     # \n line ends on every system


def rel(root, path):
    """A path as shown to the student: relative to the workspace, with /."""
    try:
        return Path(path).resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def first_line(text):
    return next((line.strip() for line in (text or "").splitlines() if line.strip()), "")


def print_list(title, items):
    if items:
        print("\n".join([title] + ["  " + item for item in items]))


def run(cmd, stdin=None, cwd=None, env=None):
    return subprocess.run(cmd, input=stdin or "", cwd=cwd, env=env, capture_output=True,
                          encoding="utf-8", errors="replace")


def git(root, *args, env=None, stdin=None):
    return run(["git", *args], stdin, cwd=str(root), env=env)


def citeproc(pandoc, csl, meta, body, *args):
    """pandoc --citeproc on a markdown body with `meta` as its metadata."""
    return run([pandoc, "-f", "markdown", "--citeproc", f"--csl={csl}", *args],
               f"---\n{json.dumps(meta, ensure_ascii=False)}\n---\n\n{body}\n")


def find_pandoc(root):
    """pandoc on PATH, in the workspace's .tools/, or where the Windows installer puts it."""
    local = os.environ.get("LOCALAPPDATA")
    return next((c for c in (shutil.which("pandoc"), shutil.which(str(root / ".tools/pandoc/bin/pandoc")),
                             local and os.path.join(local, "Pandoc", "pandoc.exe"),
                             r"C:\Program Files\Pandoc\pandoc.exe") if c and os.path.isfile(c)), None)


def find_file(root, name):
    """A file named on the command line: from here, the workspace, or thesis/;
    None after saying there is no such file."""
    path = next((p.resolve() for p in (Path(name), root / name, root / "thesis" / name) if p.is_file()), None)
    if path is None:
        print(f"no such file: {name}")
    return path


def profile(root):
    """thesis/profile.md as {lower-case field: value}; "" when it holds no real value."""
    path, fields = root / "thesis" / "profile.md", {}
    for match in re.finditer(r"^\s*- ([^:\n]+):(.*)$", read(path) if path.exists() else "", re.M):
        value = match.group(2).strip()
        fields.setdefault(match.group(1).strip().lower(), "" if value.lower() in NO_VALUE else value)
    return fields


def source_entries(root):
    """The entries of thesis/sources.md by cite key."""
    path = root / "thesis" / "sources.md"
    return {e["key"]: e for e in read_entries(read(path)) if e["key"]} if path.exists() else {}


# ------------------------------------------------- chapters, citations, lint

MASTER = re.compile(r"\s*<!--\s*master:")
MASTER_WORD = re.compile(r"\s*<!--\s*master:\s*word\b")
HEADING = re.compile(r"#{1,6}\s")
AI_MARKER = re.compile(r"^\s*<!--\s*AI draft (\d{4}-\d{2}-\d{2}).*?-->\s*$")
CHECK = re.compile(r"\\?\[CHECK:")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
CITATION = re.compile(r"(?<![\w@\\])@(" + KEY + r")(?!\w)")
OTHER_AT = re.compile(r"(?<![\w@\\])@(?=\w)(?!" + KEY + r"(?!\w))")
# Code, math and <autolinks>: they hold no citations, and pandoc takes a
# backslash in them literally.
VERBATIM = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,}).*?\n[ \t]{0,3}\1[`~]*[ \t]*$"
                      r"|(?<!`)(`+)(?!`)[^\n]+?(?<!`)\2(?!`)"
                      r"|<[A-Za-z][A-Za-z0-9+.-]+:[^\s<>]*>"
                      r"|\$\$.*?\$\$|\$(?=\S)[^$\n]*?(?<=\S)\$(?!\d)", re.S | re.M)
# Hand-typed citations: (Müller, 2021), (see Müller et al., 2021a; Berg & Lund,
# 2019, p. 7), Müller (2021), and numbers like [12] or [3, 5–7].
_NAME = (r"(?!(?:January|February|March|April|May|June|July|August|September|October"
         r"|November|December|Januar|Jänner|Februar|März|Mai|Juni|Juli|Oktober|Dezember)\b)"
         r"[A-ZÀ-ÖØ-Þ][^\W\d_]+(?:[-'’][^\W\d_]+)*")
_AUTHOR = _NAME + r"(?:\s+(?:et\s+al\.?|u\.\s*a\.)|\s+(?:&|and|und)\s+" + _NAME + r")?"
_YEAR = r"(?:1[5-9]\d\d|20\d\d)[a-z]?(?!\w|\s*[-–]\s*\d)"  # a year range is no citation: Germany (2020–2022)
_RANGE = r"\d+(?:\s*[-–]\s*\d+)?"
HAND_TYPED = re.compile(r"\([^()]*?" + _AUTHOR + r",?\s+" + _YEAR + r"[^()]*\)"
                        r"|" + _AUTHOR + r"\s+\(" + _YEAR + r"[^()]*\)"
                        r"|\[" + _RANGE + r"(?:\s*,\s*" + _RANGE + r")*\](?![(\[:])")
# Brackets that are not hand-typed citations: [@key, p. 7] and [CHECK: …].
NOT_TYPED = re.compile(r"\\?\[CHECK:[^\]]*\]|\[[^\[\]]*@[^\[\]]*\]")
# "Die Pandemie (2020)", "the GDPR (2018)": a noun after an article is no author.
ARTICLE_BEFORE = re.compile(r"\b(?:der|die|das|dem|den|des|ein|eine|einer|eines|einem|einen"
                            r"|im|am|vom|zum|zur|beim|the|a|an|this|that)\s+$", re.I)
# [@Muller2021], [@muller-2021], [@müller2021]: meant as a citation, but no key.
CITE_BRACKET = re.compile(r"(?<!\\)\[(?!CHECK:)[^\[\]]*@[^\[\]]*\](?!\()")
NOT_KEY = re.compile(r"(?<![\w@\\])@(?!" + KEY + r"(?!\w))(\w[^\s;,\]]*)")


def _blank(match):
    """Blank out a match but keep its line breaks, so line numbers stay right."""
    return re.sub(r"[^\n]", " ", match.group())


def _line(text, match):
    return text.count("\n", 0, match.start()) + 1


def written_in_kit(path):
    """True unless the file's first line says its master copy is in Word."""
    return not MASTER_WORD.match(read(path).split("\n", 1)[0])


def text_problems(name, text, entries, lines=None, chapter=False):
    """(citation problems, hand-typed citations) in a chapter or draft as "<name>:<line>: <problem>",
    only on `lines` when given. A chapter's first heading must be level 1 (# 2 Title):
    export makes it the chapter heading in Word, and sync splits the Word file there."""
    text = VERBATIM.sub(_blank, HTML_COMMENT.sub(_blank, text))
    first = re.search(r"^(#{1,6})[ \t]", text, re.M) if chapter else None
    problems = [(_line(text, first), "a chapter's first heading takes one # (# 2 Literature review), "
                 "or Word won't show it as a chapter")] if first and len(first.group(1)) > 1 else []
    for match in CITATION.finditer(text):
        entry = entries.get(match.group(1))
        state = "not in sources.md" if entry is None else entry["status"] or "not checked"
        if state != "checked":
            problems.append((_line(text, match), f"cites [@{match.group(1)}], which is {state}"))
    plain = NOT_TYPED.sub(_blank, text)
    typed = [(_line(plain, m), f"looks like a citation typed by hand: {' '.join(m.group().split())}; "
              "cite with the source's key instead")
             for m in HAND_TYPED.finditer(plain)
             if m.group()[0] in "([" or not ARTICLE_BEFORE.search(plain[max(0, m.start() - 12):m.start()])]
    typed += [(_line(text, b), f"@{m.group(1)} is not a Cite as key (keys are lower-case letters "
               "and a year, like @muller2021); use the key from sources.md")
              for b in CITE_BRACKET.finditer(text) for m in NOT_KEY.finditer(b.group())]
    return tuple([f"{name}:{n}: {problem}" for n, problem in found if lines is None or n in lines]
                 for found in (problems, typed))


def sources_problems(name, text):
    """Structure problems in sources.md."""
    problems, seen = [], {}
    entries = read_entries(text)
    taken = {e["key"] for e in entries if e["key"]}
    for e in entries:
        where, fields = f"{name}:{e['line']}: {e['label'] or e['heading']}", e["fields"]
        if not e["key"]:
            year = re.search(r"\d{4}", e["label"])
            key = make_key(label_family(e["label"]), year and year.group(), taken)
            taken.add(key)
            problems.append(f'{where}: no Cite as key; add the line "- Cite as: [@{key}]"')
        for what, value in ((f"Cite as [@{e['key']}] is also used", ("key", e["key"])),
                            (f"DOI {e['doi']} is also", ("doi", e["doi"]))):
            if value[1] and seen.setdefault(value, e["line"]) != e["line"]:   # seen on another line
                problems.append(f"{where}: {what} on line {seen[value]}")
        checked, registry = e["status"] == "checked", fields.get("registry check", "")
        problems += [f"{where}: {problem}" for bad, problem in (
            (not e["status"], "Status must be unchecked, checked · date, or dropped · date · reason"),
            (checked and not re.search(r"\d{4}-\d{2}-\d{2}", fields.get("status", "")),
             "checked without a date (checked · YYYY-MM-DD)"),
            (not registry, "no Registry check line"),
            (checked and not fields.get("in my own words"), "checked, but In my own words is empty"),
            (checked and registry.lower().startswith("retracted"),
             "checked, but the registry lists it as retracted")) if bad]
    return problems


def lint(root, files, lines=None):
    """(problems, possible hand-typed citations: a guess, so kept apart) in the
    given files, each as "<file>:<line>: <problem>": sources.md gets a structure
    check, chapters written in the kit and drafts a citation check (chapters also
    a heading check), only on the line numbers in `lines` ({file: numbers}) when
    given. Other files are ignored."""
    chapters, drafts, sources = ((root / "thesis" / n).resolve() for n in ("chapters", "drafts", "sources.md"))
    entries = source_entries(root)
    problems, typed = [], []
    for path in (Path(f).resolve() for f in files if Path(f).is_file()):
        name = rel(root, path)
        chapter = path.suffix == ".md" and path.parent == chapters and written_in_kit(path)
        if path == sources:
            problems += sources_problems(name, read(path))
        elif chapter or (path.suffix == ".md" and drafts in path.parents):
            cites, hand = text_problems(name, read(path), entries,
                                        None if lines is None else lines.get(name, ()),
                                        chapter and path.name != FRONT)
            problems += cites
            typed += hand
    return problems, typed


# ---------------------------------------------------------------------- save

def stage(root, env=None):
    """Stage thesis/ (PDFs in papers/ stay untracked); returns the staged paths."""
    git(root, "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", "thesis/papers", env=env)
    git(root, "add", "-A", "--", "thesis", env=env)
    out = git(root, "diff", "--cached", "--name-only", "-z", "--", "thesis", env=env).stdout
    return [p for p in out.split("\0") if p]


def added_lines(root, path, env):
    """The line numbers the staged change adds or changes in one file."""
    out = git(root, "diff", "--cached", "-U0", "--histogram", "--no-color", "--no-ext-diff",
              "--", path, env=env).stdout
    return {n for m in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", out, re.M)
            for n in range(int(m.group(1)), int(m.group(1)) + int(m.group(2) or 1))}


def add_log_row(root, message, where, tools):
    """Add the AI-log row; False when ai-log.md already has a row its last
    saved version (or the template) lacks, i.e. one was written by hand."""
    path, template = root / "thesis" / "ai-log.md", root / "kit" / "templates" / "ai-log.md"
    text = read(path if path.exists() else template)
    saved = git(root, "show", "HEAD:thesis/ai-log.md")
    old = {line.strip() for line in (saved.stdout if saved.returncode == 0 else read(template)).splitlines()}
    if path.exists() and any(line.strip().startswith("|") and line.strip() not in old
                             for line in text.splitlines()):
        return False
    where = where[:3] + [f"+{len(where) - 3} more"] if len(where) > 3 else where
    cells = [today(), message, ", ".join(where) or "chat", tools or "–"]
    write(path, text.rstrip("\n") + "\n| "
          + " | ".join(" ".join(c.replace("|", "/").split()) for c in cells) + " |\n")
    return True


def save(root, message, tools="", own_edits=False):
    try:
        top = git(root, "rev-parse", "--show-toplevel")
    except FileNotFoundError:
        print("NOT SAVED: git is not installed (see kit/reference/tools.md)")
        return 1
    blocked = ("saved versions are not set up (see kit/workflows/setup.md step 5)"
               if top.returncode or not Path(top.stdout.strip()).samefile(root)
               else "a kit update is half done; finish or undo it first (kit/workflows/update-kit.md)"
               if git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0
               else ("an undo is half done (a file still has conflicts); finish or cancel it first "
                     "(kit/reference/versions.md)") if git(root, "ls-files", "-u", "--", "thesis").stdout.strip()
               else "")
    if blocked:
        print("NOT SAVED: " + blocked)
        return 1
    fields = profile(root)
    origin = git(root, "remote", "get-url", "--push", "origin")
    notes = (["warning: the public kit (origin) can still receive uploads; "
              "setup sets its push URL to DISABLED"]
             if origin.returncode == 0 and origin.stdout.strip() != "DISABLED" else [])
    identity = []
    for setting, fallback in (("user.name", fields.get("name") or "Thesis student"),
                              ("user.email", "student@thesis-kit.local")):
        if not git(root, "config", setting).stdout.strip():
            identity += ["-c", f"{setting}={fallback}"]

    # `git commit -- thesis` would put back PDFs just untracked from papers/,
    # so the version is built in a separate index: the last version plus thesis/.
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
        if git(root, "rev-parse", "-q", "--verify", "HEAD").returncode == 0:
            git(root, "read-tree", "HEAD", env=env)
        changed = stage(root, env)
        if not own_edits and not LOG_OFF.match(fields.get("ai log", "")):
            if add_log_row(root, message, [p[len("thesis/"):] for p in changed if p != "thesis/ai-log.md"],
                           tools):
                changed = stage(root, env)
            else:
                notes.append("the AI log already has a new row, so save added none")
        if not changed:
            print("\n".join(["nothing new to save"] + notes))
            return 0
        # Only the lines this save wrote: the rest was listed when it was written.
        problems, typed = lint(root, [root / p for p in changed],
                               {rel(root, root / p): added_lines(root, p, env)
                                for p in changed if p.endswith(".md")})
        result = git(root, *identity, "commit", "-q", "-F", "-", env=env, stdin=message + "\n")
    if result.returncode != 0:
        print("NOT SAVED: " + first_line(result.stderr or result.stdout))
        return 1
    stage(root)                     # the normal index now matches the saved version
    print("\n".join(["saved: " + message] + notes))
    if own_edits:
        print_list("In the student's own edits (tell them; change nothing):", problems + typed)
    else:
        print_list("Problems in this change (fix them, then save again):", problems)
        print_list("Maybe citations typed by hand (cite the real ones with their source's key; "
                   "leave the rest):", typed)
    if fields.get("online backup", "").lower().startswith("yes"):
        pushed = git(root, "push", "--quiet", "backup", "HEAD:main",
                     env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if pushed.returncode != 0:
            ahead = git(root, "rev-list", "--count", "backup/main..HEAD")
            count = ahead.stdout.strip() if ahead.returncode == 0 else "all"
            # a rejected push starts with "To <url>"; git gives the reason on the "!" line
            reason = next((" ".join(line.split()) for line in pushed.stderr.splitlines()
                           if line.lstrip().startswith("!")), first_line(pushed.stderr))
            versions = "1 saved version is" if count == "1" else f"{count} saved versions are"
            print(f"online backup failed: {versions} only on this computer ({reason})")
    return 0


# -------------------------------------------------------------------- export

STYLES = [  # (pattern in the profile's citation style, CSL style id); "note" finds footnote, Fußnote
    (r"\bapa", "apa"), (r"harvard", "harvard-cite-them-right"), (r"\bmla", "modern-language-association"),
    (r"\bieee", "ieee"), (r"vancouver", "vancouver"), (r"chicago.*note", "chicago-note-bibliography"),
    (r"chicago", "chicago-author-date"), (r"\bdin\b|iso\s*690", "iso690-author-date-de")]
LANGUAGES = [  # (words in the profile's thesis language, lang, references heading)
    (("engl",), "en-US", "References"), (("germ", "deut"), "de-DE", "Literaturverzeichnis"),
    (("fren", "fran"), "fr-FR", "Bibliographie"), (("span", "espa"), "es-ES", "Bibliografía"),
    (("ital",), "it-IT", "Bibliografia"), (("dutch", "neder", "niederl"), "nl-NL", "Literatuurlijst"),
    (("portu",), "pt-PT", "Referências")]
# doi.org's CSL-JSON carries registry bookkeeping (license, funder, reference
# lists, ...) and some variables as lists; citeproc wants strings. Keep the
# standard variables, flattened.
CSL_STRINGS = ("type title container-title container-title-short collection-title publisher publisher-place "
               "page volume issue number edition DOI URL ISBN ISSN language genre event version archive").split()
CSL_NAME_PARTS = "family given literal suffix non-dropping-particle dropping-particle".split()
# Crossref answers with its own type names; CSL styles only know CSL types
# (an unknown type renders a journal article like a book chapter). Types
# both know, like book or report, stay as they are.
CROSSREF_TO_CSL = {
    "journal-article": "article-journal", "proceedings-article": "paper-conference", "book-chapter": "chapter",
    "book-section": "chapter", "book-part": "chapter", "monograph": "book", "edited-book": "book",
    "reference-book": "book", "report-component": "report", "posted-content": "article",
    "dissertation": "thesis", "reference-entry": "entry"}
PUBLISHER = re.compile(r"press|verlag|publish|books|routledge|springer|wiley|palgrave", re.I)


def csl_style(value):
    """(CSL style id, note) for the profile's citation style."""
    value = value.strip()
    if re.match(r"^[a-z0-9]+(-[a-z0-9]+)+$", value):      # already a style id
        return value, ""
    for pattern, style in STYLES:
        if re.search(pattern, value, re.I):
            return style, ("Chicago has two variants; say 'Chicago with footnotes' to switch"
                           if style == "chicago-author-date" else "")
    return "apa", (f"citation style '{value}' is not one the kit knows; used APA" if value
                   else "no citation style in profile.md; used APA")


def language(fields):
    """(lang, references heading) for the profile's thesis language."""
    value = fold(fields.get("thesis language", ""))
    return next(((code, heading) for words, code, heading in LANGUAGES
                 if any(w in value for w in words)), ("en-US", "References"))


def style_file(root, style):
    """The CSL file for a style id, downloaded from zotero.org the first time."""
    path = root / ".tools" / "styles" / f"{style}.csl"
    if not path.exists():
        request = urllib.request.Request("https://www.zotero.org/styles/" + urllib.parse.quote(style),
                                         headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
            xml = response.read().decode("utf-8", "replace")
        if "<style" not in xml:
            raise ValueError("not a citation style")
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, xml)
    return path


def _string(value, kinds=(str, int, float)):
    """A CSL variable as one string: a list's first item, whitespace collapsed; "" when none."""
    if isinstance(value, list):
        value = value[0] if value else None
    return " ".join(str(value).split()) if isinstance(value, kinds) else ""


def clean_csl(raw, key):
    """A doi.org CSL-JSON record reduced to what citeproc needs, with id = key."""
    rec = {"id": key, **{f: v for f in CSL_STRINGS for v in [_string(raw.get(f))] if v}}
    rec["type"] = CROSSREF_TO_CSL.get(rec.get("type"), rec.get("type") or "article")
    if "title" in rec:
        rec["title"] = TITLE_END.sub("", rec["title"])
        # Crossref keeps many subtitles apart; styles cite the full title.
        sub = TITLE_END.sub("", _string(raw.get("subtitle"), str))
        if sub and fold(sub) not in fold(rec["title"]):
            rec["title"] += (" " if rec["title"].endswith(("?", "!", ":")) else ": ") + sub
    for field in ("author", "editor", "translator"):
        people = [{k: p[k] for k in CSL_NAME_PARTS if isinstance(p.get(k), str) and p[k].strip()}
                  for p in raw.get(field) or []]
        if any(people):
            rec[field] = [p for p in people if p]
    # The print year, not the online-first one, is the year a paper is cited by.
    for field, source in (("issued", raw.get("published-print") or raw.get("issued")),
                          ("accessed", raw.get("accessed"))):
        parts = (source or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            rec[field] = {"date-parts": [[int(x) for x in parts[0] if x is not None]]}
    return rec


def load_records(path):
    """(records by id, problems) from thesis/references.json. The records are the
    well-formed-enough ones even when there are problems: sync compares with them."""
    try:
        data = json.loads(read(path)) if path.exists() else []
    except ValueError as err:
        return {}, [f"thesis/references.json is not valid JSON ({err}); fix it, then export again"]
    if not isinstance(data, list):
        return {}, ["thesis/references.json must be a JSON list of records"]
    problems = []
    for number, rec in enumerate(data, 1):
        if not isinstance(rec, dict):
            problems.append(f"thesis/references.json: record {number} is not a JSON object")
            continue
        authors, issued = rec.get("author", []), rec.get("issued", {"date-parts": [[]]})
        parts = issued.get("date-parts") if isinstance(issued, dict) else None
        wrong = [f'needs "{f}"' for f in ("id", "type", "title")
                 if not isinstance(rec.get(f), str) or not rec[f].strip()]
        if not (isinstance(authors, list) and all(isinstance(a, dict) for a in authors)):
            wrong.append('"author" must look like [{"family": "Müller", "given": "Jana"}]')
        if not (isinstance(parts, list) and parts and all(isinstance(p, list) for p in parts)):
            wrong.append('"issued" must look like {"date-parts": [[2021]]}')
        problems += [f"thesis/references.json: record {rec.get('id') or number}: {w}" for w in wrong]
    return {r["id"]: r for r in data if isinstance(r, dict) and isinstance(r.get("id"), str)}, problems


def skeleton(key, entry):
    """A record to complete by hand for a checked source without a DOI record."""
    published = entry["fields"].get("published in", "")
    book = bool(PUBLISHER.search(published))
    year = re.search(r"\((\d{4})", entry["label"])
    names = re.sub(r"\s*\(.*$", "", entry["label"]).replace(" et al.", "").split(" & ")
    return {"id": key, "type": "book" if book else "article-journal", "title": entry["title"],
            **({"issued": {"date-parts": [[int(year.group(1))]]}} if year else {}),
            "author": [{"family": n.strip(), "given": ""} for n in names if n.strip()],
            **({"publisher" if book else "container-title": published} if published else {})}


def word_text(text, ids):
    """A chapter or draft as pandoc markdown: no master line, other @words
    escaped, and each AI-draft marker turned into a Word comment on the
    nearest heading above it (or the next paragraph when there is none)."""
    lines = text.split("\n")
    out, pending = [], ""
    for line in lines[1:] if MASTER.match(lines[0]) else lines:
        marker = AI_MARKER.match(line)
        if marker:
            n, date = next(ids), marker.group(1)
            comment = (f"[AI draft {date} · rewrite in your own words, then delete this comment]"
                       f'{{.comment-start id="{n}" author="thesis-kit" date="{date}T00:00:00Z"}}'
                       f'[]{{.comment-end id="{n}"}}')
            above = next((i for i in range(len(out) - 1, -1, -1) if HEADING.match(out[i])), None)
            if above is None:
                pending += comment
            else:
                out[above] = _with_comment(out[above], comment)
        else:
            if pending and line.strip():
                line, pending = _with_comment(line, pending) if HEADING.match(line) else pending + line, ""
            out.append(line)
    text = "\n".join(out)
    verbatim = [m.span() for m in VERBATIM.finditer(text)]
    return OTHER_AT.sub(lambda m: "@" if any(a <= m.start() < b for a, b in verbatim) else "\\@", text)


def _with_comment(heading, comment):
    """Append to a heading's text, before any {#id .class} attributes."""
    match = re.match(r"(.*?)(\s+\{[#.-][^{}]*\})?\s*$", heading)
    return match.group(1) + comment + (match.group(2) or "")


def new_path(folder, base, suffix, taken=()):
    """folder/base.suffix, or base-2, base-3, ... when that exists or is taken."""
    paths = (folder / f"{base}{'' if n == 1 else f'-{n}'}{suffix}" for n in itertools.count(1))
    return next(p for p in paths if not p.exists() and p not in taken)


def export(root, names):
    thesis = root / "thesis"
    chapters = [p.resolve() for p in sorted((thesis / "chapters").glob("*.md"))]
    named = [find_file(root, name) for name in names]
    if None in named:
        return 1
    files = [p for p in named or chapters if written_in_kit(p)]
    skipped = [f"skipped {rel(root, p)}: it lives in the Word file (master: word)"
               for p in named if not written_in_kit(p)]
    if not files:
        print("\n".join(skipped + ["nothing to export: no chapter is written in the kit"]))
        return 1
    pandoc = find_pandoc(root)
    if not pandoc:
        print("pandoc is missing: get it as kit/reference/tools.md describes, then export again")
        return 1

    fields = profile(root)
    style, note = csl_style(fields.get("citation style", ""))
    notes = [note] if note else []
    try:
        csl = style_file(root, style)
        if 'citation-format="numeric"' in read(csl):
            if any((thesis / "drafts").resolve() in p.parents for p in files):
                style, csl = "apa", style_file(root, "apa")
                notes.append("shown author-year; number them in your Word file")
            elif set(files) != set(chapters):   # the rest is numbered elsewhere
                notes.append("numbers start at [1] in this file")
    except Exception as err:
        print(f"could not download the citation style {style} from zotero.org ({err})")
        return 1
    lang, heading = language(fields)

    entries = source_entries(root)
    texts = [read(p) for p in files]
    found = [text_problems(rel(root, p), t, entries) for p, t in zip(files, texts)]
    problems, typed = sum((f[0] for f in found), []), sum((f[1] for f in found), [])
    keys = dict.fromkeys(m.group(1) for t in texts for m in CITATION.finditer(HTML_COMMENT.sub("", t)))
    cited = [k for k in keys if k in entries and entries[k]["status"] == "checked"]

    refs_path = thesis / "references.json"
    records, bad = load_records(refs_path)
    if bad:
        print("\n".join(bad))
        return 1
    cached, failed, unrecorded = len(records), [], []
    for key in [k for k in cited if k not in records and entries[k]["doi"]]:
        if failed:              # once doi.org is unreachable, don't wait for it again
            failed.append(key)
            continue
        try:
            raw = fetch_json("https://doi.org/" + urllib.parse.quote(entries[key]["doi"], safe="/()<>;:.-_"),
                             accept="application/vnd.citationstyles.csl+json")
            if not isinstance(raw, dict):
                raise ValueError("not a CSL record")
            records[key] = clean_csl(raw, key)
        except (NotFound, ValueError):  # the DOI has no record (or none in CSL)
            unrecorded.append(key)
        except Exception:
            failed.append(key)
    if len(records) > cached:
        write(refs_path, json.dumps(sorted(records.values(), key=lambda r: r["id"]),
                                    indent=2, ensure_ascii=False) + "\n")
    missing = [k for k in cited if k not in records and not entries[k]["doi"]]
    if failed:
        print(f"could not reach doi.org for {', '.join(failed)}; nothing exported")
    if missing:
        print("These checked sources have no DOI, so their reference list entries are typed in once.")
    if unrecorded:
        print(f"doi.org has no record for the DOI of {', '.join(unrecorded)}: check the DOI in "
              "thesis/sources.md, or type in the record below.")
    if missing or unrecorded:
        print("Complete each record below from the entry's Reference as given line or the first "
              "page of its PDF (not from memory), add it to thesis/references.json, then export again.")
        for key in missing + unrecorded:
            given, pdf = (entries[key]["fields"].get(f, "") for f in ("reference as given", "pdf"))
            print("\n" + json.dumps(skeleton(key, entries[key]), indent=2, ensure_ascii=False)
                  + "\nReference as given: " + (given or "(none in sources.md)"))
            if pdf:
                print(f'PDF: take the rest from its first page: python3 kit/scripts/sources.py pdf '
                      f'"{pdf if pdf.startswith("thesis/") else "thesis/" + pdf}" --pages 1')
    if failed or missing or unrecorded:
        return 1

    meta = {"lang": lang, "references": [records[k] for k in cited]}
    meta.update((k, fields[f]) for k, f in (("title", "working title"), ("author", "name")) if fields.get(f))
    ids = itertools.count(1)
    body = "\n\n".join(word_text(text, ids) for text in texts)
    out = new_path(thesis / "export", f"{files[0].stem if len(files) == 1 else 'thesis'}-{today()}", ".docx")
    args = ["-o", str(out)]
    template = fields.get("word template", "")
    if template and template.lower() != "none":
        if (root / template).is_file():
            args.append(f"--reference-doc={root / template}")
        else:
            notes.append(f"Word template {template} not found; used pandoc's plain look")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = citeproc(pandoc, csl, meta, f"{body}\n\n# {heading}\n\n::: {{#refs}}\n:::", *args)
    if result.returncode != 0:
        print("pandoc could not make the Word file: " + first_line(result.stderr))
        return 1

    print("\n".join([f"exported: {rel(root, out)}"] + skipped + [f"style: {style}"]
                    + [f"  note: {note}" for note in notes]))
    drafts = sum(1 for t in texts for line in t.split("\n") if AI_MARKER.match(line))
    print(f"{sum(len(CHECK.findall(t)) for t in texts)} [CHECK] markers, {drafts} AI-draft sections")
    print_list("Left out of the references (shown in bold with a ? in Word):", problems)
    print_list("Citations typed by hand (printed as written, not linked to a source):", typed)
    # Records doi.org gave carry their DOI; the ones typed in don't.
    manual = [records[k] for k in cited if not entries[k]["doi"] or not records[k].get("DOI")]
    if manual:
        plain = citeproc(pandoc, csl, {"lang": lang, "references": manual, "nocite": "@*"}, "",
                         "-t", "plain", "--wrap=none")
        print("Typed from your sources list; check these against the book or page:")
        print("\n".join("  " + line for line in plain.stdout.splitlines() if line.strip()))
    return 0


# ---------------------------------------------------------------------- sync

def pick_docx(root, name):
    """The Word file to read, or None after saying why there is no single one."""
    if name:
        return find_file(root, name)
    thesis = root / "thesis"
    recorded = {m.group(1) for m in (re.match(r"\s*<!--\s*master:\s*word\s*·\s*(.+?)\s*·",
                                              read(p).split("\n", 1)[0])
                                     for p in (thesis / "chapters").glob("*.md")) if m}
    found = sorted(p for p in (thesis / "word").glob("*.docx")
                   if p.name != "template.docx" and not p.name.startswith("~$"))
    several = "several Word files in thesis/word/ (ask which one the student works in): "
    if len(recorded) == 1 and (root / next(iter(recorded))).is_file():
        path = (root / recorded.pop()).resolve()
        # A Word file saved after the one read last time (File > Save As) may
        # be the one the student works in now, so ask instead of guessing.
        newer = [p.name for p in found if p.stat().st_mtime > path.stat().st_mtime]
        if not newer:
            return path
        print(f"{several}{rel(root, path)}, read last time; newer: {', '.join(newer)}")
    elif len(found) == 1:
        return found[0].resolve()
    elif found:
        print(several + ", ".join(p.name for p in found))
    else:
        exported = ", ".join(sorted(p.name for p in (thesis / "export").glob("*.docx")))
        hint = f"\nto keep working on an exported file, save it into thesis/word/ (in thesis/export/: {exported})"
        print("no Word file in thesis/word/" + (hint if exported else ""))
    return None


def plain_headings(markdown):
    """The text without pandoc anchors and {#id .class} heading attributes."""
    return "\n".join(re.sub(r"\s+\{[#.-][^{}]*\}\s*$", "", line).rstrip() if HEADING.match(line) else line
                     for line in re.sub(r"\[\]\{#[^{}]*\.anchor[^{}]*\}", "", markdown).split("\n"))


def split_chapters(markdown):
    """(text before the first top-level heading, [one text per top-level
    section]), or None when there is no top-level heading."""
    parts = re.split(r"^(?=# )", plain_headings(markdown), flags=re.M)
    return (parts[0].strip(), [p.strip() for p in parts[1:]]) if len(parts) > 1 else None


def heading_parts(line):
    """'# 2 Literature review' -> (2, 'Literature review'); no number -> (None, title)."""
    match = re.match(r"#*\s*(?:(\d+)(?:\.\d+)*\.?\s+)?(.*?)\s*$", line)
    return (match.group(1) and int(match.group(1))), match.group(2)


def match_chapter(number, title, existing, used):
    """The existing chapter file for a Word chapter: the one with the same
    title, else the most similar (ratio ≥ 0.6), one with the same number
    first; None when there is none."""
    key = title_key(title)
    free = {p: title_key(existing[p][1]) for p in existing if p not in used}
    ratio = {p: difflib.SequenceMatcher(None, other, key).ratio() for p, other in free.items()}
    return next((p for p, other in free.items() if other == key), None) or max(
        (p for p in free if ratio[p] >= 0.6), default=None,
        key=lambda p: (number is not None and existing[p][0] == number, ratio[p]))


def selected(path, number, moves):
    """The --move values that name this chapter: all, its file name, or its
    number (the Word heading's, else the file name's)."""
    digits = re.match(r"\d+", path.name)
    number = digits and int(digits.group()) if number is None else number
    return {m for m in moves if m in ("all", path.stem) or Path(m).name == path.name
            or m.isdigit() and int(m) == number}


def _plain(text):   # pandoc escapes punctuation in some places, not others
    return " ".join(re.sub(r"\\(?=[^\w\s])", "", HTML_COMMENT.sub("", text)).split())


def as_exported(root, pandoc, paths):
    """{heading: section} for these kit chapters as sync reads them back from an export
    (citations in the profile's style), so an unchanged export compares as the same text;
    {} while export has not downloaded the style."""
    fields = profile(root)
    csl = root / ".tools" / "styles" / f"{csl_style(fields.get('citation style', ''))[0]}.csl"
    records = load_records(root / "thesis" / "references.json")[0]
    if not paths or not csl.exists():
        return {}
    entries = source_entries(root)
    meta = {"lang": language(fields)[0], "suppress-bibliography": True,
            "references": [r for k, r in records.items() if entries.get(k, {}).get("status") == "checked"]}
    body = "\n\n".join(word_text(HTML_COMMENT.sub("", read(p)), itertools.count(1)) for p in paths)
    result = citeproc(pandoc, csl, meta, body, "-t", "markdown-smart", "--wrap=none",
                      "--reference-location=section")
    parts = None if result.returncode else split_chapters(result.stdout)
    return {section.split("\n", 1)[0]: section for section in parts[1]} if parts else {}


def events(node):
    """Words, comments and tracked changes in a pandoc JSON node, in order.
    Deleted text and the text of comments are not words of the document."""
    if isinstance(node, list):
        for item in node:
            yield from events(item)
    elif isinstance(node, dict) and "t" in node:
        kind, content = node["t"], node.get("c")
        if kind in ("Str", "Space", "SoftBreak", "LineBreak"):
            yield "text", content if kind == "Str" else " "
        elif kind != "Span":
            yield from events(content)
        else:
            (_, classes, attributes), inlines = content
            get = dict(attributes).get
            mark = next((c for c in ("comment-start", "comment-end", "insertion", "deletion")
                         if c in classes), None)
            if mark:
                yield mark, get("id"), get("author", ""), get("date", ""), words(inlines)
            if mark not in ("comment-start", "deletion"):
                yield from events(inlines)


def words(node):
    return " ".join("".join(e[1] for e in events(node) if e[0] == "text").split())


def word_feedback(ast):
    """({section: ['- author (date): comment — on "words"',
    '- author (date): inserted "words" after "…words before"', ...]}, comments per
    author, tracked changes per author, sections with an AI-draft comment)."""
    comments, authors, changes, ai_sections = {}, collections.Counter(), {}, []
    h1 = h2 = ""
    for block in ast.get("blocks", []):
        if block.get("t") == "Header" and block["c"][0] <= 2:
            h1, h2 = (words(block["c"][2]), "") if block["c"][0] == 1 else (h1, words(block["c"][2]))
        section = f"{h1} › {h2}" if h1 and h2 else h1 or h2 or "Before the first heading"
        found = list(events(block))
        for i, (kind, *about) in enumerate(found):
            if kind in ("insertion", "deletion"):
                author, date, text = about[1] or "unknown", about[2][:10], about[3]
                changes.setdefault(author, {"insertion": 0, "deletion": 0})[kind] += 1
                if text:
                    before = "".join(e[1] for e in found[:i] if e[0] == "text").split()
                    near = ("…" if len(before) > 5 else "") + " ".join(before[-5:])
                    text = text[:79] + "…" if len(text) > 80 else text
                    line = (f"- {author}" + (f" ({date})" if date else "")
                            + f': {"inserted" if kind == "insertion" else "deleted"} "{text}"')
                    comments.setdefault(section, []).append(line + (f' after "{near}"' if near else ""))
            elif kind == "comment-start" and about[1] == "thesis-kit":
                ai_sections.append(section)
            elif kind == "comment-start":
                cid, author, date, text = about[0], about[1] or "unknown", about[2][:10], about[3]
                span = itertools.takewhile(lambda e: e[:2] != ("comment-end", cid), found[i + 1:])
                marked = " ".join("".join(e[1] for e in span if e[0] == "text").split())
                marked = marked[:79] + "…" if len(marked) > 80 else marked
                authors[author] += 1
                line = f"- {author}" + (f" ({date})" if date else "") + f": {text}"
                comments.setdefault(section, []).append(line + (f' — on "{marked}"' if marked else ""))
    return comments, authors, changes, list(dict.fromkeys(ai_sections))


def _changes(changes):
    return "; ".join(f"{author}: " + ", ".join(f"{c[k]} {k}{'' if c[k] == 1 else 's'}"
                                               for k in ("insertion", "deletion"))
                     for author, c in changes.items())


def sync(root, name, moves):
    thesis = root / "thesis"
    docx = pick_docx(root, name)
    if docx is None:
        return 1
    pandoc = find_pandoc(root)
    if not pandoc:
        print("pandoc is missing: get it as kit/reference/tools.md describes, then sync again")
        return 1
    text = run([pandoc, str(docx), "-t", "markdown-smart", "--wrap=none", "--reference-location=section",
                "--track-changes=accept"])
    ast = run([pandoc, str(docx), "-t", "json", "--track-changes=all"])
    if text.returncode or ast.returncode:
        print(f"pandoc could not read {rel(root, docx)}: {first_line(text.stderr or ast.stderr)}")
        return 1
    parts = split_chapters(text.stdout)
    if parts is None:
        print("the Word file uses no Heading 1 styles, so chapters can't be told apart")
        return 1
    front, sections = parts

    chapters = thesis / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    existing = {p: heading_parts(plain_headings(head.group())) for p in sorted(chapters.glob("*.md"))
                if p.name != FRONT and (head := re.search(r"^# .*", read(p), re.M))}
    plan = [("Text before the first heading", chapters / FRONT, front, None)] if front else []
    used = set()
    # Numbers already taken by chapter files, so an unnumbered Word section
    # never gets the number of another chapter. The reference list that
    # export adds is 99, after every chapter, and takes no chapter's number.
    numbers = {int(path.name[:2]) for path in chapters.glob("[0-9][0-9]-*.md")} - {99}
    references = {title_key(heading) for _, _, heading in LANGUAGES}
    for position, section in enumerate(sections, 1):
        head = section.split("\n", 1)[0]
        number, title = heading_parts(head)
        is_refs = number is None and title_key(title) in references
        path = match_chapter(number, title, existing, used)
        if path is None:
            if is_refs:
                n = 99
            else:
                n = number if number is not None else position if position not in numbers else max(numbers) + 1
                numbers.add(n)
            slug = re.sub(r"[^a-z0-9]+", "-", fold(title)).strip("-")[:40].strip("-") or "chapter"
            path = new_path(chapters, f"{n:02d}-{slug}", ".md", used)
        used.add(path)
        plan.append((f'"{head.lstrip("#").strip()}"' + (" (the reference list made by the export)"
                                                        if is_refs else ""), path, section, number))

    master = f"<!-- master: word · {rel(root, docx)} · synced {today()} -->"
    report, markers, matched = [], [], set()
    exported = as_exported(root, pandoc, [path for _, path, _, _ in plan
                                          if path.exists() and written_in_kit(path)])
    for label, path, section, number in plan:
        old = read(path) if path.exists() else None
        in_kit = old is not None and not MASTER_WORD.match(old.split("\n", 1)[0])
        name = rel(root, path)
        matched |= (moved := selected(path, number, moves))
        if in_kit and not moved:
            kit_text = exported.get(section.split("\n", 1)[0]) or plain_headings(old)
            report.append(f"{label} → {name}: still written in the kit, not changed "
                          f"(Word text {'same' if _plain(kit_text) == _plain(section) else 'differs'})")
            continue
        if old is not None and not in_kit and old.split("\n", 1)[-1].strip() == section:
            action = "no change"
        else:
            write(path, master + "\n" + section + "\n")
            action = "moved to Word" if in_kit else "updated" if old is not None else "new"
        report.append(f"{label} → {name}: {action}")
        if CHECK.search(section):
            markers.append(f"{name} {len(CHECK.findall(section))}")
    # A mirror of this Word file whose chapter is gone (renamed or deleted)
    # is no mirror any more; its text stays in the saved versions.
    planned = {path for _, path, _, _ in plan}
    for path in sorted(chapters.glob("*.md")):
        if path not in planned and read(path).startswith(f"<!-- master: word · {rel(root, docx)} ·"):
            path.unlink()
            report.append(f"{rel(root, path)}: removed, no longer in the Word file")

    comments, authors, changes, ai_sections = word_feedback(json.loads(ast.stdout))
    body = "\n\n".join([f"## {s}\n\n" + "\n".join(c) for s, c in comments.items()] or ["No comments."])
    body = (body + (f"\n\nTracked changes not yet accepted: {_changes(changes)}." if changes else "")).strip()
    snapshot = thesis / "feedback" / "word-comments.md"
    if not snapshot.exists() or read(snapshot).split("\n", 1)[-1].strip() != body:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        write(snapshot, f"# Comments in {docx.name} · synced {today()}\n\n{body}\n")

    print("\n".join([f"Word file: {rel(root, docx)}"] + report
                    + [f"no chapter matches --move {m}" for m in moves if m not in matched]))
    print("Comments: " + (", ".join(f"{a} {n}" for a, n in authors.items()) or "none")
          + f" (in {rel(root, snapshot)})")
    if changes:
        print(f"Tracked changes not yet accepted: {_changes(changes)}")
    if ai_sections:
        print("AI-draft comments still in Word: " + "; ".join(ai_sections))
    if markers:
        print("[CHECK] markers: " + ", ".join(markers))
    return 0


# --------------------------------------------------------------- command line

def main(argv=None, root=ROOT):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="thesis.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("save", help="Save a version of thesis/.")
    p.add_argument("message", nargs="?", help="What was done, in plain words")
    p.add_argument("--tools", default="", help="Outside tools the student used for it")
    p.add_argument("--own-edits", action="store_true", help="Save the student's own edits (no AI-log row)")
    sub.add_parser("export", help="Make a new Word file from the chapters.").add_argument(
        "files", nargs="*", help="Chapters or drafts (default: all chapters)")
    p = sub.add_parser("sync", help="Mirror the Word file's chapters and comments.")
    p.add_argument("docx", nargs="?", help="The Word file (default: the one in thesis/word/)")
    p.add_argument("--move", nargs="+", default=[], metavar="CHAPTER",
                   help="Chapters now written in Word: the number in the Word heading, file name or all")
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2
    if args.cmd == "save" and not (args.own_edits or (args.message or "").strip()):
        parser.error('save needs a message, e.g. save "drafted 2.1", or --own-edits')

    root = Path(root).resolve()
    if not (root / "thesis").is_dir():
        print(("NOT SAVED: " if args.cmd == "save" else "")
              + "there is no thesis/ folder yet; run setup first (kit/workflows/setup.md)")
        return 1
    if args.cmd == "save":
        message = "your own edits" if args.own_edits else " ".join(args.message.split())
        return save(root, message, args.tools.strip(), args.own_edits)
    if args.cmd == "export":
        return export(root, args.files)
    return sync(root, args.docx, args.move)


if __name__ == "__main__":
    sys.exit(main())
