# Mark a source as checked, or drop it

Records that the student has read a source: the only way a source becomes `checked`.

## Mark as checked

1. Find the entry in `thesis/sources.md` by author and year, or title. Several candidates: ask which. Not in the file yet: add it first with `kit/workflows/add-sources.md`.
2. The student has to have said, in this conversation, that they opened and read it. "Looks relevant" or "sounds good" is not reading; when unsure, ask "Did you open and read it?".
3. Get their one-line summary of what it found, in their own words; ask for it if they gave none. If their line copies the abstract, say so and ask for their own sentence.
4. Look at the `Registry check:` line:
   - `ok` or `no-doi`: go on.
   - `mismatch`, `not-found` or `unknown`: say what is unresolved and ask them to confirm title, authors, year, journal and DOI from the paper in front of them. Write it as one item in a temporary JSON file, as in `kit/workflows/add-sources.md` step 1, with `ref` = the reference as they give it (with the DOI if the paper shows one), and run `python3 kit/scripts/sources.py check <file>`. Correct the entry's heading, `DOI` and `Published in` from the registry record it returns (else from what the student confirmed), and write the new verdict and today's date into `Registry check:`. The `Cite as` key stays.
   - `retracted`: explain that it can't be cited; it stays `dropped`.
5. Write `Status: checked · YYYY-MM-DD` with today's date, and their line under `In my own words:`, unchanged apart from typos. Add `PDF: papers/<file>` if they saved one into `thesis/papers/`.

## Drop

When the student says a source is irrelevant, unreadable or not what they expected: `Status: dropped · YYYY-MM-DD · <their reason in a few words>`. It stays in the file.

## Several at once

Handle each source the student confirms separately ("read Müller, Chen and Ortiz: …"). Any without its own summary line stays `unchecked` until they give one.

## Save

Right after marking or dropping, before any other job the same message asks for ("I read Twenge: … now write 2.2"): `python3 kit/scripts/thesis.py save "marked <Author Year> as read"` (or `"dropped <Author Year>"`), so the next job can be undone on its own.

## Done when

Every source the student named is `checked` with their own line, `dropped` with a reason, or still `unchecked` with your reply saying exactly what you need from them; the change is saved as its own version.
