# Check a sentence

Tests whether the student's checked sources actually support a claim.

## Steps

1. Split the text into single claims. One sentence can carry several ("X rose sharply (Müller, 2021) and is now the main driver").
2. For each claim, look for support in the `checked` sources: their `In my own words` lines, notes, and PDFs in `thesis/papers/` (search them with `python3 kit/scripts/sources.py pdf <file> --find "<term>|<term>"`). Unchecked sources may be named as leads, never as support.
3. Give each claim one verdict:
   - **supported**: name the source; when you found it in a PDF, quote the passage with the page number printed on it (the script's `PDF page K` is its place in the file; look with `--pages K`);
   - **partly supported**: say which part is and which isn't (often a number, a causal word, or a generalisation);
   - **not supported by your checked sources**: say what kind of source would support it, and whether an unchecked one might;
   - **contradicted**: show the conflicting source.
4. When a cited source does not say what the sentence claims, say so plainly. This is the most important thing this check can find.
5. Offer a rewording that stays within the evidence. Change thesis files only when the student asks.

## Done when

Every claim in the text has a verdict, with its evidence named or the reason no evidence was found.
