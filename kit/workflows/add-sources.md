# Add sources

Takes papers from anywhere and adds them to `thesis/sources.md` as `unchecked`, each with a registry check.

Any input works: a pasted reference list, DOIs, links, titles, a BibTeX or RIS export (Zotero, Mendeley, EndNote), a table from Consensus or Elicit, text from a screenshot, or PDFs in `thesis/papers/` ("add the PDFs I just saved").

## Steps

1. **Extract** each work: DOI (from the text, a link, or a PDF's first page), title, authors, year. For a PDF, read its first page and keep the file name for the `PDF:` line.
2. **Check** them in one run. Write the list as JSON, `[{"doi": "…", "title": "…", "authors": ["Müller, J."], "year": 2021}, …]`, leaving out fields you don't have, to a temporary file outside `thesis/`. Then run `python3 kit/scripts/sources.py check <file>`. Exit code 1 means the registries could not be reached: retry once; if it fails again, add the works with `Registry check: unknown (registries unreachable, re-check)`.
3. **Skip duplicates**: a work already in `sources.md` (same DOI, or same title and first author) is not added again. If it was `dropped`, tell the student instead of adding it back.
4. **Add** each new work to `thesis/sources.md` (created from `kit/templates/sources.md` the first time) in the entry format of `kit/reference/thesis-folder.md`:
   - heading and `Published in:` from the registry record when the check found one, otherwise from the input;
   - `Status: unchecked`;
   - `Registry check:` the verdict and today's date;
   - `Found via:` the tool or person the student named;
   - `PDF:` when there is one;
   - `Free full text:` the link from `python3 kit/scripts/sources.py details <doi> …`, when it returns one.
5. **Report** in plain words: how many were added, how many were already there, and every work whose verdict is not `ok`, with its reason:
   - `not-found`: the DOI does not exist. The paper may have been invented by a tool, or the DOI mistyped. Ask where it came from.
   - `mismatch`: the DOI and the description disagree. Show both and ask which is right.
   - `retracted`: added as `dropped · <date> · retracted`, so it is never cited.
   - `no-doi`: normal for books, reports, laws and web pages. The student confirms it by hand when checking it.

## Done when

Every work in the input is either in `sources.md` with a registry check line or named in your report as a duplicate, and every verdict other than `ok` has been explained to the student.
