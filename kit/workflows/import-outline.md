# Import an outline or overview

Brings an outline, a structure or an overview of the field into `thesis/outline.md` and `thesis/memo.md`, wherever it comes from.

Typical input: the supervisor's suggested structure, a sketch the student typed, the chapters a university template requires, the output of another research tool (an AI chat, a literature review tool), or a Word or PDF file.

## Steps

1. Read the input. For a `.docx`, get pandoc if needed (`kit/reference/tools.md`) and run `pandoc <file> -t markdown --wrap=none`. For a PDF, read its text.
2. Sort what it contains:
   - **structure** (chapters, sections, their purpose) → the outline;
   - **overview of the field** (groups, debates, gaps, summaries) → `memo.md`, marked with where it came from;
   - **references** → `kit/workflows/add-sources.md`, where they arrive `unchecked` like any other source;
   - **ready-made thesis prose** (whole paragraphs or chapters written by a tool) stays out. Say so, and offer `kit/workflows/draft-section.md`, which drafts from the student's checked sources.
3. If `thesis/outline.md` already has content, show both briefly side by side and ask: replace, merge, or keep theirs. When the student is unsure, merge and keep their section names.
4. Write the outline to `thesis/outline.md` (created from `kit/templates/outline.md` the first time) in the format of `kit/reference/thesis-folder.md`: numbered headings, each with a `Purpose:` line taken from the input, or `Purpose: open`.

## Done when

`thesis/outline.md` reflects the student's choice (replace, merge or keep); every reference from the input is in `sources.md` or named in your reply; and no prose from the input landed in `thesis/chapters/`.
