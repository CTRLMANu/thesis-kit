# The thesis folder

Everything the student owns lives in `thesis/`. The kit never ships it, so kit updates never touch it. Setup creates `profile.md`, `question.md`, `papers/` and `word/`; every other file is created by the job that first needs it, from `kit/templates/` where a template exists.

## Layout

| Path | Holds |
|---|---|
| `profile.md` | Facts about the thesis and the kit settings. |
| `question.md` | The research question, in the student's own words. |
| `memo.md` | The exposé (map of the field) and themes from reading. |
| `outline.md` | The numbered outline. Its section numbers name the sections ("draft 2.1"). |
| `sources.md` | Every source, with its status and cite key. |
| `references.json` | The Word export's CSL-JSON records, one per cited checked work, with the cite key as `id`. `thesis.py export` fills it and asks for the records it cannot fetch. |
| `ai-log.md` | The AI log: a table (Date, What the AI did, Where, Outside tools) with one row per job, added by `thesis.py save` while `AI log: on`. |
| `chapters/` | One markdown file per chapter (below). |
| `drafts/` | Drafts for chapters whose master copy is in Word: `2.1-short-name.md`. |
| `papers/` | The student's PDFs. They stay on this computer, outside saved versions and the online backup. |
| `word/` | The student's Word master file, and `template.docx` if the university provides one. |
| `export/` | Word files made by "export to Word". Never overwritten. |
| `feedback/` | The Word file's comments and the supervisor to-do lists (below). |

## profile.md

One `- Field: value` line per fact; the fields are in `kit/templates/profile.md`. An empty value, `skipped` and `don't know yet` all mean there is no value. Kit settings: `AI log: on` or `off`; `Online backup: no` or `yes · <private repository URL>`; `Word template: none` or `thesis/word/template.docx`.

## sources.md

`python3 kit/scripts/sources.py add` writes one entry per work, in this shape:

```markdown
### Jumper et al. (2021) · Highly accurate protein structure prediction with AlphaFold
- Cite as: [@jumper2021]
- Status: unchecked
- DOI: 10.1038/s41586-021-03819-2
- Registry check: ok · 2026-10-01
- Published in: Nature 596(7873), 583–589
- Found via: search for 2.1
- Free full text: https://www.nature.com/articles/s41586-021-03819-2.pdf
- PDF: papers/jumper-2021.pdf
- In my own words:
- Notes:
```

- **Heading:** the in-text label (first author's family name; `A & B` for two authors, `A et al.` for three or more; the year, or `n.d.`), then the title.
- **Cite as:** the key thesis text cites the work with. Never changed once written.
- **Status:** `unchecked`, `checked · YYYY-MM-DD` or `dropped · YYYY-MM-DD · <reason>`; only `mark-checked.md` changes it. Dropped entries stay, so they are not added again.
- **Registry check:** the verdict as `sources.py` prints it (`ok`, `mismatch`, `retracted`, `not-found`, `no-doi`, `unknown`; `add-sources.md` explains each), an optional `: short reason`, and the date.
- Lines without a value are left out, such as **Found via** when the student named none. **Published in** ends in `(preprint)` for preprints. **Reference as given** keeps the reference as it came in, for works without a registry record and for a `mismatch`.
- **In my own words:** the student's own one-line summary of what the work found. Empty until checked. Never write it for them.
- **Notes:** dated bullets that name their origin, as `file-notes.md` describes.

## outline.md

Chapters are `## 2 Literature review`, sections `### 2.1 Definitions`, subsections `#### 2.1.1 …`. Under each heading: a `Purpose:` line (what this part has to show) and, once known, a `Sources:` line with the cite keys it will draw on: `Sources: [@orben2019], [@keles2020]`. Keep the labels `Purpose:` and `Sources:` in English, whatever the thesis language, and the keys on that one line; `sources.py coverage` reads them.

## Chapter files

- File name: two-digit chapter number plus a short name, `chapters/02-literature-review.md`. Headings take the outline's numbers and titles, one level higher: `# 2 Literature review`, `## 2.1 Definitions`.
- The first line says where the master copy lives:
  - `<!-- master: kit -->`: the chapter is written here. A file without a master line counts as this.
  - `<!-- master: word · thesis/word/<file>.docx · synced <date> -->`: the chapter lives in Word, and this file is a read-only mirror that `thesis.py sync` rewrites. New text for it goes into `drafts/`.
- **Citations** in chapters written here and in `drafts/` use the entry's `Cite as` key: `[@jumper2021]`, with a page `[@jumper2021, p. 7]`, several `[@jumper2021; @chen2019]`, narrative `@jumper2021`, without the author's name `[-@jumper2021]`. In mirrors, citations are plain text, as in Word.
- **`[CHECK: …]`** marks a claim that still needs a checked source, or a detail to verify, until the student resolves it.
- **AI draft marker:** the `<!-- AI draft … -->` line that `draft-section.md` puts first under a section's heading. A section without it is the student's text. The Word export turns it into a Word comment by `thesis-kit`.

## feedback/

- `word-comments.md`: the Word file's current comments and tracked changes (who, which words) by section. `thesis.py sync` rewrites it every time.
- `<date>.md`: one round of feedback as a to-do list, written by `supervisor-comments.md` and never overwritten:

```markdown
# Feedback · 2026-10-05 · Prof. Weber (comments in thesis.docx)

## 2.1 Definitions
- [ ] "Define resilience before using it." → add a definition with a source · content
```
