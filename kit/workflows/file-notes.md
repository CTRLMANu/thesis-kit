# File notes

Files notes about sources next to the right entries, whether they come from a tool or from the student's own reading.

Typical input: answers from Gemini Notebook or Elicit, highlights, the student's reading notes, a summary from another AI tool, notes typed from a book.

## Steps

1. Split the input into individual notes. Keep page numbers, quotes and the tool's own source references.
2. Match each note to entries in `thesis/sources.md` by author, year, title or the tool's citation. A note that spans several works (a theme, a disagreement, a comparison) goes to `thesis/memo.md` under "Themes from my reading", naming the works it concerns.
3. Append each matched note under the entry's `Notes:` as `- <date> · <origin> · <page, if any>: <note>`. The origin is the tool's name, or `my reading` for the student's own notes. Quotes stay verbatim, in quotation marks.
4. For a note about a work that is not in `sources.md`, ask whether to add it; on yes, run `kit/workflows/add-sources.md`.
5. Report how many notes went where, and any you could not match.

Notes never change a source's status. A note from an AI tool records what that tool reported, not the student's own reading.

## Done when

Every note is filed under an entry or in `memo.md`, or is listed in your reply as unmatched.
