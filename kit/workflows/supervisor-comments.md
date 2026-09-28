# Supervisor comments → to-do list

Turns feedback into a to-do list for the student. You make the list; the thesis text stays as it is until the student picks an item to work on.

Typical input: pasted comments or an email, notes from a meeting, the Word file's comments in `thesis/feedback/word-comments.md` (collected by `kit/workflows/sync-word.md`), or comments copied from a PDF.

## Steps

1. Split the feedback into single points. A comment that asks for two things becomes two items. Leave out points already in an earlier to-do list (`thesis/feedback/<date>.md`).
2. For each point, note: where it applies (a section number from the outline, or `general`), what the supervisor asks (a short quote or a close paraphrase), and one line on what doing it would involve. Tag it `content`, `structure`, `sources`, `style` or `formal`.
3. A point you cannot place or understand becomes an item `ask supervisor: …`, with the question to ask.
4. Write a new file `thesis/feedback/<date>.md` (`<date>-2.md` if that name is taken) in the format of `kit/reference/thesis-folder.md`, grouped by section in outline order, with `general` first.
5. Tell the student where the list is, how many items it has, and how many per tag.

When the student picks an item, work on that item only (drafting goes through `kit/workflows/draft-section.md`), and tick it once they say it's done.

## Done when

Every point in the feedback is exactly one item in the new list or already in an earlier to-do list, and no thesis text has changed.
