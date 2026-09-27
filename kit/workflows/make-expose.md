# Make the exposé

Builds a first map of the field from free scholarly databases: who works on the question, what they report, where they disagree, what is missing, and a first outline. The result is a working memo, an outline and a list of leads, all `unchecked`. It contains no thesis text.

The method follows OpenDraft's research stages (search, read abstracts, map gaps, outline), carried out by you with `kit/scripts/sources.py`.

## 1. Prepare

1. Read `thesis/profile.md` and `thesis/question.md`. Without a research question, suggest sharpening it first, because the map gets much better with one. Carry on if the student prefers.
2. If `thesis/memo.md` or `thesis/outline.md` already has content, say so and agree whether to add to it or replace it.
3. Tell the student this takes a few minutes and several AI requests, then start.

## 2. Search

1. Plan 5–8 search queries that together cover the question: its main concepts, their common synonyms, and the method or setting. Make one of them aim at overview work (`<topic> review`), because the databases rank recent papers high and foundational ones can get buried. The databases are mostly English, so search in English, plus 1–2 queries in the thesis language when it isn't English.
2. Run each: `python3 kit/scripts/sources.py find "<query>" --n 15 --json`. Results include preprints (SSRN, arXiv, Research Square, type `posted-content`). Label them as preprints wherever they appear, and rerun a query with `--no-preprints` when they crowd out published work.
   - **Exit code 1** means no database answered. Wait a minute and run it once more. If it fails again, stop and tell the student the databases could not be reached. Leave the gap empty rather than filling it from memory.
3. Merge the results and remove duplicates by DOI. Keep the 20–40 most relevant by title and venue. With fewer than 3 in total, stop: tell the student the question may need other words or a broader angle, and propose new queries.

## 3. Read the abstracts

1. For the kept works, run `python3 kit/scripts/sources.py details <doi> <doi> …`, about 10 DOIs per call. It returns the abstract when a registry has one, a free full-text link when one exists, and retraction notices.
2. Leave out retracted works. For every other work, note its question, method and main finding, and how you know: `abstract` or `title only`. Describe method and findings only for works whose abstract you have.

## 4. Map the field

From the abstracts only:

- **Research groups and positions**: clusters of work that ask the question the same way or argue the same thing. Name leading authors and what each group claims.
- **Disagreements**: where findings or framings conflict, and what the dispute seems to turn on (method, sample, definition).
- **Gaps**: methods not tried, settings not studied, recent developments not yet covered. State trends as counts ("7 of the 31 works are from 2024 or later"), not impressions.
- **Outline**: a chapter structure that suits the degree and the kind of question (for an empirical thesis, for example: introduction, literature review, method, results, discussion, conclusion). Headings with a `Purpose:` line each, and a `Sources:` line naming the works that fit.

## 5. Write it down

1. `thesis/memo.md`: fill Summary (at most 5 lines); Sources overview (a small table: number of works, year range, most common venues, how many had abstracts); Research groups and positions; What the abstracts report; Disagreements; Gaps; Next steps (the 5–10 works to open first, and why). Every finding says it comes from an abstract.
2. `thesis/outline.md`: the outline, in the format of `kit/reference/thesis-folder.md`.
3. `thesis/sources.md`: every work the memo mentions, as `unchecked`, with `Registry check: ok · <date>` (`details` resolved them), `Found via: exposé` and the free full-text link when there is one. Works already in the file are not added again.

## 6. Hand over

In three or four sentences, tell the student what the map shows, that everything in it is a lead taken from abstracts, and which papers to open first. Suggest the next step: open those papers, then *"I read …: it found …"*.

## Done when

Every work named in `memo.md` is in `sources.md` as `unchecked` with a DOI that `details` resolved; every finding in the memo says it comes from an abstract; `outline.md` holds only headings, purpose lines and sources lines; and nothing in `thesis/chapters/` was created or changed.
