# Sync the Word file

Brings the student's Word file back into the kit, so you work from their latest text, and collects comments and tracked changes. The Word file is the master copy and is read-only for you.

## Steps

1. **Find the file**: the `.docx` the student names; otherwise the newest `.docx` in `thesis/word/` other than `template.docx` and Word's temporary `~$…` files. If there is none, explain how to put it there: in Word, *File → Save a Copy* into the `thesis/word/` folder; in Google Docs, *File → Download → Microsoft Word (.docx)*, then move the file there.
2. **Get pandoc** if needed (`kit/reference/tools.md`).
3. **Read the file twice**, into a temporary folder outside `thesis/`:
   - `pandoc <file> -t markdown --wrap=none --track-changes=accept -o <tmp>/clean.md` gives the text as it reads with every change accepted;
   - `pandoc <file> -t markdown --wrap=none --track-changes=all -o <tmp>/marked.md` gives the same text with comments (`[comment]{.comment-start author=… date=…}commented words[]{.comment-end}`), insertions (`[…]{.insertion author=…}`) and deletions (`[…]{.deletion author=…}`).
4. **Mirror the chapters**: split `clean.md` at its top-level headings and match each chapter to its file in `thesis/chapters/` by number or name. Text before the first chapter goes to `00-front-matter.md`; unnumbered parts after the last chapter (references, appendix) go to `99-<name>.md`. Overwrite every chapter file whose text changed with the Word text, and make its first line `<!-- master: word · thesis/word/<file>.docx · synced <date> -->`. Create files for new chapters. Chapter files the Word file doesn't contain stay as they are.
5. **Compare** each chapter with its previous saved version: sections added, removed or rewritten, and which sections still carry an AI draft marker or `[CHECK]`.
6. **Collect feedback**: every comment, insertion and deletion in `marked.md`, with its author, date, section and the words it concerns. Save them as a plain list in `thesis/feedback/<date>.md` and offer to turn them into a checklist (`kit/workflows/supervisor-comments.md`).
7. **Citations**: find in-text citations in the Word text that match no `checked` entry in `sources.md`.

## Report

In plain words: which chapters were updated and roughly how; how many comments and tracked changes there were, and from whom; and any citations without a checked source. End with the most useful next step.

## Done when

Every chapter in the Word file is mirrored in `thesis/chapters/` with the Word master line; comments and tracked changes are saved in `thesis/feedback/`; and the Word file itself is unchanged.
