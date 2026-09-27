# Export to Word

Makes a new Word file from the chapters, with a formatted reference list. It always creates a new file and never overwrites one.

## Steps

1. **Choose the chapters**: all files in `thesis/chapters/` in order, or the ones the student named. When a chapter's first line says `master: word`, warn that it already lives in their Word file: the export makes a separate copy, and their Word file stays the master.
2. **Get pandoc** if needed (`kit/reference/tools.md`).
3. **Count markers** in the chosen chapters: `[CHECK: …]` markers and AI draft markers. Tell the student the numbers and ask whether to export anyway. `[CHECK]` markers stay visible in the Word file; the AI draft marker lines are hidden comments and don't appear.
4. **References**: match every in-text citation in the chosen chapters to an entry in `sources.md`. Citations with no match, or whose entry isn't `checked`, are left out of the reference list and listed for the student.
   - Checked works with a DOI: `python3 kit/scripts/bibliography.py csl-json <doi> <doi> … -o <tmp>/references.json`.
   - Checked works without a DOI: add a CSL-JSON record for each to `references.json` by hand (`id`, `type`, `title`, `author`, `issued`, and `publisher`, `publisher-place`, `container-title`, `page` or `URL` as they apply), and tell the student to double-check those entries.
   - The style file: `python3 kit/scripts/bibliography.py style <citation style from profile.md> -o ~/.thesis-kit/styles` prints its path.
5. **Assemble** one markdown file in a temporary folder: a YAML header with `title` (the working title), `author` (the name, if given) and `nocite: '@*'`; the chapters in order; then a references heading in the thesis language (`# References`, `# Literaturverzeichnis`, …) followed by an empty `::: {#refs}` / `:::` block.
6. **Convert**:

   ```sh
   pandoc <tmp>/thesis.md --citeproc --bibliography=<tmp>/references.json --csl=<style file> -o thesis/export/thesis-<YYYY-MM-DD>.docx
   ```

   Add `--reference-doc=<template>` when `Word template:` in profile.md names a file. If a file with today's name exists, add `-2`, `-3`, … to the name.
7. **Report**: the new file's path; what the template controls (heading styles, fonts, margins) and what the student adds by hand in Word (title page, table of contents under *References → Table of Contents*, page numbers); and the citations that had no checked source.

## Done when

A new `.docx` exists in `thesis/export/` and no existing file was overwritten; every entry in its reference list belongs to a `checked` source; and the student knows about any remaining `[CHECK]` markers and unmatched citations.
