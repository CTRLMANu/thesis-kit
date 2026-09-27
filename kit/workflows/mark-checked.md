# Mark a source as checked, or drop it

Records that the student has read a source. This is the only way a source becomes `checked`, and only the student's own confirmation triggers it.

## Mark as checked

1. Find the entry in `thesis/sources.md` by author and year, or title. Several candidates: ask which. Not in the file yet: add it first with `kit/workflows/add-sources.md`.
2. The student has to have said, in this conversation, that they opened and read it. "Looks relevant" or "sounds good" is not reading; when unsure, ask "Did you open and read it?".
3. Get their one-line summary of what it found, in their own words; ask for it if they gave none. If their line copies the abstract, say so and ask for their own sentence.
4. Look at the `Registry check:` line:
   - `ok` or `no DOI`: go on.
   - `mismatch`, `not found` or `unknown`: say what is unresolved and ask them to confirm the details from the paper in front of them (title, authors, year, DOI). Correct the entry, and run the check again when they give a DOI.
   - `retracted`: explain that it can't be cited; it stays `dropped`.
5. Write `Status: checked · <date>`, and their line under `In my own words:`, unchanged apart from typos. Add `PDF:` if they saved one into `thesis/papers/`.

## Drop

When the student says a source is irrelevant, unreadable or not what they expected: `Status: dropped · <date> · <their reason in a few words>`. It stays in the file.

## Several at once

The student may confirm several in one message ("read Müller, Chen and Ortiz: …"). Handle each separately. Any without its own summary line stays `unchecked` until they give one.

## Done when

Every source the student named is `checked` with their own line, `dropped` with a reason, or still `unchecked` with your reply saying exactly what you need from them.
