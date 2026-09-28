# Add sources

Adds works from anywhere to `thesis/sources.md` as `unchecked`, each looked up in the registries. The script writes the entries; you hand it the works exactly as the student gave them.

Any input works: a pasted reference list, DOIs, links, titles, a BibTeX or RIS export, a table from Consensus or Elicit, text from a screenshot, or PDFs in `thesis/papers/` ("add the PDFs I just saved").

## Steps

1. **List the works** as JSON in a temporary file outside `thesis/`:
   - pasted text: one item per work, `{"ref": "<the reference exactly as the student gave it>", "title": "…", "authors": ["Müller, J."], "year": 2021, "journal": "…"}`. A bare DOI or link counts as the reference. Take title, authors, year and journal only from the reference, and leave out what it doesn't say. An organisation as author goes in whole: `{"name": "World Health Organization"}`.
   - PDFs in `thesis/papers/`: `{"pdf": "thesis/papers/<file>"}`. The script reads the DOI from the PDF.
   - a `.bib` or `.ris` export: no list; use the file itself in step 2.
2. **Add** them: `python3 kit/scripts/sources.py add <file>`, plus `--found-via "<tool or person>"` only when the student named one. If it prints `nothing added`, no registry answered: tell the student and try again later.
3. **Report** in plain words: how many were added, how many were already there (for one dropped before, say why), and every work whose verdict is not `ok`, with its reason:
   - `not-found`: the DOI doesn't exist, or the journal is indexed but has no such article. A tool may have invented the work. Ask whether the student has the paper itself (a PDF or the publisher's page).
   - `mismatch`: the DOI and the description disagree. Show both and ask which is right.
   - `retracted`: added as dropped, so it is never cited.
   - `preprint`: not peer-reviewed; a journal version may exist.
   - `no-doi`: normal for books, reports, laws, web pages and some small journals. The student confirms it by hand when checking it.
   - `unknown`: the registries couldn't be reached; it is checked again when the student marks it as read.
   - `not added`: no registry record and no title. For a PDF, read its first page with `python3 kit/scripts/sources.py pdf <file>` and add it again with the title, authors and year printed there; otherwise ask the student for the title.

   Name each work as its `added` line does, never by a title of your own; `ok` only means the registries know it as described: the entry is `unchecked`, and becomes `checked` when the student says they read it and what it found, in their own words ("I read Müller 2021: it found …").

   A "closest record" in a reason is a different work, unless the student says it is the one they meant. Then correct that entry as `kit/workflows/mark-checked.md` step 4 does, with the record's DOI as `ref`.

## Done when

Every work in the input was added or named as a duplicate, and every verdict other than `ok` was explained to the student.
