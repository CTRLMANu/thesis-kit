# Sync the Word file

Brings the student's Word file back into the kit, so you work from their latest text, and collects its comments and tracked changes. The Word file is the master copy of the chapters it holds; the script only reads it.

## Steps

1. Run `python3 kit/scripts/thesis.py sync`, or `python3 kit/scripts/thesis.py sync thesis/word/<file>.docx` for the file the student named.
   - No Word file in `thesis/word/`: tell the student to save their file there and write in that copy from then on: in Word, *File → Save As* (*Save a Copy* for files in OneDrive) into `thesis/word/`; from Google Docs, *File → Download → Microsoft Word (.docx)* into `thesis/word/` before every sync, replacing the old file under the same name.
   - Several Word files: ask which one they work in, and run it again with that file.
   - No Heading 1 styles: ask the student to give each chapter title the style *Heading 1* in Word, save, and sync again.
2. Read the new mirrors in `thesis/chapters/` for citations that match no `checked` entry in `sources.md`. In Word, citations are plain text; report them and change nothing.
3. **Report** in plain words everything the script printed (chapters updated, created, removed or still written in the kit; comments and tracked changes, by person; AI-draft comments; `[CHECK]` markers) and the citations from step 2. The text of removed chapters stays in the saved versions; the comments and tracked changes are in `thesis/feedback/word-comments.md`.
4. If the report lists chapters "still written in the kit" whose text differs from the Word file, end the report by asking once, naming them: "Do you write chapter N in Word from now on?" Everything else is already brought in; the answer only decides whether the kit's text of those chapters is replaced by the Word text. If the report lists tracked changes not yet accepted, say that a yes takes the chapter's text as if they were accepted (in Word they stay open to accept or reject). For each yes, run it again with `--move N` (or `--move all`), check that chapter's citations as in step 2, and say which chapters now follow Word; the kit's text stays in the saved versions.

## Done when

Every chapter in the Word file is mirrored in `thesis/chapters/` or reported as still written in the kit, the student was asked about every such chapter that differs, and the Word file is unchanged.
