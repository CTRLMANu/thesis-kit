# Make the exposé

Builds a first map of the field from free scholarly databases: a working memo on who works on the question, what they report, where they disagree and what is missing; a first outline; and a list of `unchecked` leads. It contains no thesis text.

## 1. Prepare

1. Read `thesis/question.md` and work from the question or topic exactly as the student has it. If there is none, ask what the exposé should be about.
2. If `thesis/memo.md` or `thesis/outline.md` already has content, say so and agree whether to add to it or replace it.
3. Tell the student this takes a few minutes and several AI requests, then start.

## 2. Search

1. Plan 5–8 queries that together cover the question: its main concepts, their common synonyms, and the method or setting. Make one aim at overview work (`<topic> review`), so foundational papers don't get buried under recent ones. Search in English, plus 1–2 queries in the thesis language when it isn't English.
2. Run each: `python3 kit/scripts/sources.py find "<query>" --n 15`. Label preprints (type `preprint` or `posted-content`) as preprints wherever they appear; rerun a query with `--no-preprints` when they crowd out published work.
   - **Exit code 1**: no database answered. Wait a minute and run it once more; if it fails again, stop and tell the student. Never fill the gap from memory.
   - **`ranked_by` is `crossref`**: OpenAlex was unavailable and the results are weaker. Say so in the memo's Sources overview. If it happens on every query, offer the free OpenAlex key (`kit/reference/tools.md`).
3. Merge the results, removing duplicates by DOI. Keep the 20–40 most relevant by title, venue and `cited_by_count`. With fewer than 3 in total, stop: tell the student the question may need other words or a broader angle, and propose new queries.

## 3. Read the abstracts

1. For the kept works, run `python3 kit/scripts/sources.py details <doi> <doi> …`, about 10 DOIs per call.
2. Leave out retracted works and DOIs that didn't resolve. For every other work, note its question, method and main finding, and whether you had its `abstract` or only its `title`. Describe method and findings only from an abstract.

## 4. Write it down

Write from the abstracts only. Create each file from `kit/templates/` if it doesn't exist yet.

1. `thesis/memo.md`, with these sections:
   - **Summary**: at most 5 lines.
   - **Sources overview**: a small table: number of works, year range, most common venues, how many had abstracts.
   - **Research groups and positions**: clusters of work that ask the question the same way or argue the same thing, with their leading authors and what each group claims.
   - **What the abstracts report.**
   - **Disagreements**: where findings or framings conflict, and what the dispute seems to turn on (method, sample, definition).
   - **Gaps**: methods not tried, settings not studied, recent developments not yet covered. State trends as counts ("7 of the 31 works are from 2024 or later").
   - **Central works**: the 5–10 most-cited works in the set, with their citation counts.

   Every finding says it comes from an abstract.
2. `thesis/sources.md`: list every work the memo names as `{"ref": "<doi>"}` items in a temporary JSON file outside `thesis/`, then run `python3 kit/scripts/sources.py add <file> --found-via "exposé"`.
3. `thesis/outline.md`: a chapter structure that suits the degree and the kind of question (for an empirical thesis: introduction, literature review, method, results, discussion, conclusion), in the format of `kit/reference/thesis-folder.md`, with a `Sources:` line of the keys `add` printed for the works that fit each part: `Sources: [@orben2019], [@keles2020]`.

## 5. Hand over

In three or four sentences: what the map shows, where it is (`memo.md`, `outline.md`, `sources.md`), and that everything in it is a lead from abstracts.

## Done when

Every work named in `memo.md` is in `sources.md`, added by `sources.py add`; every finding in the memo says it comes from an abstract; `outline.md` holds only headings, purpose lines and sources lines; and nothing in `thesis/chapters/` was created or changed.
