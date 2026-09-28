# Export to Word

Makes a new Word file from the chapters written in the kit, or from single chapters or drafts, with citations and a reference list in the profile's citation style.

## Steps

1. Run `python3 kit/scripts/thesis.py export` for every chapter still written in the kit, or name the files the student asked for: `python3 kit/scripts/thesis.py export thesis/drafts/2.1-definitions.md` ("export 2.1 to Word").
2. If it can't reach doi.org, tell the student nothing was exported and to try again when they are online.
3. If it asks for records, complete them as it says (never from memory; the student can fill gaps), check any DOI it questions with the student, then run it again. Fix problems it reports in `thesis/references.json` the same way.
4. **Report** in plain words: the new file's path; the style and any notes on it; the `[CHECK]` markers (they stay visible) and AI-draft sections (they show as Word comments); citations left out of the reference list and why; and the references typed from the sources list, which the student checks against the book or page.
5. Tell the student how to go on in Word. When `thesis/word/` has no Word file yet: open the new file, save it into `thesis/word/` (*File → Save As*), write in that file from then on, and say "sync my Word file" whenever the kit should see their latest text. When they already write in a Word file there: copy the new text into it. In Word they add the title page, the table of contents (*References → Table of Contents*) and page numbers. A university template set as `Word template:` in profile.md controls heading styles, fonts and margins.

Numeric styles (IEEE, Vancouver) are numbered correctly only while every chapter is still written in the kit and exported together.

## Done when

A new `.docx` exists in `thesis/export/`, no file was overwritten, and the student knows everything the report listed.
