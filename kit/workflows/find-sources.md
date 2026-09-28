# Find more sources

Finds new `unchecked` leads for one outline section or the whole thesis, from database searches and from what the student's checked sources cite and are cited by.

## Steps

1. **Scope:** the section the student names, or, for the whole thesis, the sections with few sources.
   - Where a `Sources:` line in `thesis/outline.md` names works instead of cite keys (outlines from an older exposé; `coverage` says `has no cite keys`), first replace each name with its entry's `Cite as` key from `sources.md`; leave names with no entry as they are.
   - Whole thesis: run `python3 kit/scripts/sources.py coverage`. It counts only the keys on `Sources:` lines, so also count the other checked entries in `sources.md` that fit a section. Show the student the sections with few sources (roughly under 5 in all, or none checked), leaving out parts that need no literature, such as results, and work on those or the ones they pick, at most 5 per run.
   - No outline yet (`coverage` exits 1): the research question in `thesis/question.md` takes the place of a section and its Purpose (no question either: ask what to search for); use `--found-via "search for the thesis"` and skip step 5.
2. **Search**, per section:
   - 2–4 queries from its heading, its `Purpose:` line and the research question in `thesis/question.md`, in English, plus 1 in the thesis language when it isn't English: `python3 kit/scripts/sources.py find "<query>" --n 15`. A work marked `in_sources` is in `sources.md` already: don't add it again, but when it fits, put the key it shows on the section's line in step 5.
   - Citation chasing from the checked sources that fit it, the keys on its `Sources:` line plus other checked entries that fit (as `draft-section.md` step 2.2 collects them): `python3 kit/scripts/sources.py related orben2019 keles2020`. Whole thesis: instead run `related` once, without keys (all checked sources), and sort its leads to the sections they fit.
   - Exit code 1 (no database answered, or nothing to chase yet): carry on with what worked. `ranked_by: crossref` means OpenAlex was unavailable; if that or `related`'s rate-limit message keeps coming, offer the free OpenAlex key (`kit/reference/tools.md`). Never fill a gap from memory.
3. **Pick** only the new works whose title shows they serve the section's Purpose: at most 10, and fewer is fine. Judge by title and venue first, then `links` (ties to the student's sources) and `cited_by_count`; a high `cited_by_count` alone doesn't make a work fit. Leave out works that another section's Purpose fits better, guidance or policy reports unless the Purpose asks for them, and generic methods or statistics papers unless it is a method section.
4. **Add** them, per section: a JSON list of `{"ref": "<doi>"}` items in a temporary file outside `thesis/`, then `python3 kit/scripts/sources.py add <file> --found-via "search for <section number>"`. Whole thesis: leads that fit the thesis but no single section, at most 10, get `--found-via "search for the thesis"` and no `Sources:` line.
5. **Outline:** append to the section's `Sources:` line in `thesis/outline.md` (`Sources: [@orben2019], [@keles2020]`) the keys from the `added` lines, the fitting `in_sources` keys, and the fitting checked entries from step 2 that aren't on it yet; create the line under the `Purpose:` line if missing. Apart from this and step 1's keys, change nothing in the outline.
6. **Report**, per section: how many leads were added and the few most relevant, named exactly as their `added` lines do; that they are `unchecked`, so a draft cites none of them yet; any verdict other than `ok`, explained as `add-sources.md` does; and whether a search failed or OpenAlex was unavailable.

## Done when

Every section in scope was searched; the new works went in through `sources.py add`; with an outline, their keys are on the right `Sources:` lines; and the student has the report.
