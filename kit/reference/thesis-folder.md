# The thesis folder

Everything the student owns lives in `thesis/`. The kit never ships it, so kit updates can never collide with it. Setup creates `profile.md`, `question.md`, `papers/` and `word/`; every other file and folder is created by the tool that first needs it, from `kit/templates/` where a template exists. This file is the single definition of what goes where and in which format.

## Layout

| Path | Holds |
|---|---|
| `profile.md` | Facts about the thesis and the kit settings. Read it before every job. |
| `question.md` | The research question, in the student's own words. `sharpen-question.md` adds sub-questions and scope only when the student uses it. |
| `memo.md` | The exposé (map of the field) and themes from reading. |
| `outline.md` | The numbered outline. Its section numbers are how everyone names a section ("draft 2.1"). |
| `sources.md` | Every paper, with its status. |
| `ai-log.md` | The AI log, while `AI log: on`. |
| `chapters/` | One markdown file per chapter: `01-introduction.md`, `02-literature-review.md`, … |
| `drafts/` | Your drafts for chapters whose master copy is in Word: `2.1-short-name.md`. |
| `papers/` | The student's PDFs. |
| `word/` | The student's Word master file, and `template.docx` if the university provides one. |
| `export/` | Word files made by "export to Word". Never overwritten. |
| `feedback/` | One to-do list per round of supervisor feedback: `2026-10-05.md`. |

## profile.md

One `- Field: value` line per fact; see `kit/templates/profile.md` for the fields. `skipped` and `don't know yet` are valid values. Kit settings:

- `AI log: on` or `off`.
- `Online backup: no`, or `yes · <private repository URL>`.
- `Word template: none`, or `thesis/word/template.docx`.

## sources.md

One entry per work, in this shape:

```markdown
### Jumper et al. (2021) · Highly accurate protein structure prediction with AlphaFold
- Status: unchecked
- DOI: 10.1038/s41586-021-03819-2
- Registry check: ok · 2026-10-01
- Published in: Nature 596(7873), 583–589
- Found via: Consensus
- Free full text: https://www.nature.com/articles/s41586-021-03819-2.pdf
- PDF: papers/jumper-2021.pdf
- In my own words:
- Notes:
```

- **Heading:** the in-text label (first author, `et al.` for three or more, year) and the title. Use `n.d.` for no year.
- **Status** is exactly one of:
  - `unchecked`: not yet confirmed by the student. The default for everything you add.
  - `checked · <date>`: the student confirmed they opened it and wrote the `In my own words` line. Only `mark-checked.md` sets this, and only on the student's explicit confirmation.
  - `dropped · <date> · <reason>`: opened and rejected, or retracted. Kept so it is not re-added.
- **Registry check** is the verdict from `python3 kit/scripts/sources.py check`, plus the date: `ok`, `ok · note: correction notice`, `mismatch: <what differs>`, `retracted`, `not found`, `no DOI (confirm by hand)`, `unknown (registries unreachable, re-check)`.
- **Found via:** where the student or you found it (exposé, Consensus, supervisor, Zotero export, …).
- **In my own words:** the student's own one-line summary of what the work found. Empty until checked. Never write it for them.
- **Notes:** dated bullets that name their origin, for example `- 2026-10-03 · Gemini Notebook · p. 7: uses a panel of 400 firms`.

Keep entries in the order they were added.

## outline.md

Chapters are `## 2 Literature review`, sections `### 2.1 Definitions`, subsections `#### 2.1.1 …`. Under each heading: a `Purpose:` line (what this part has to show) and, once known, a `Sources:` line naming the entries it will draw on.

## Chapter files

- File name: two-digit chapter number plus a short name, `chapters/02-literature-review.md`. Headings copy the outline: `# 2 Literature review`, `## 2.1 Definitions`.
- The first line says where the master copy lives:
  - `<!-- master: kit -->`: the chapter is written here.
  - `<!-- master: word · thesis/word/<file>.docx · synced <date> -->`: the chapter lives in Word, and this file is a read-only mirror refreshed by `sync-word.md`. New text for it goes into `drafts/`.
- **Citations** are written in the final, readable style from `profile.md`, for example `(Jumper et al., 2021)` in APA. Each one must match a `checked` entry in `sources.md`.
- **`[CHECK: …]`** marks a claim that still needs a checked source, or a detail to verify. It stays visible until the student resolves it.
- **AI draft marker:** a section you drafted starts with `<!-- AI draft <date> · rewrite in your own words, then delete this line -->`. A section without the marker is the student's text.

## ai-log.md

A table: `| Date | What the AI did | Where | Tools the student used |`. One row per job, written in plain words ("drafted first version of 2.1 from 5 checked papers"). The last column holds outside tools the student mentioned for that work (Consensus, Gemini Notebook, …).

## feedback/

`feedback/<date>.md` holds one round of comments as a to-do list:

```markdown
# Feedback · 2026-10-05 · Prof. Weber (comments in thesis.docx)

## 2.1 Definitions
- [ ] "Define resilience before using it." → add a definition with a source · content
```

The student ticks items. You tick one only when the student says it is done.
