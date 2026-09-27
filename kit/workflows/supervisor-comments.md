# Supervisor comments → to-do list

Turns feedback into a to-do list for the student. You make the list; the thesis text stays as it is until the student picks an item to work on.

Typical input: pasted comments or an email, notes from a meeting, the feedback file saved by `kit/workflows/sync-word.md`, or comments copied from a PDF.

## Steps

1. Split the feedback into single points. A comment that asks for two things becomes two items.
2. For each point, note: where it applies (a section number from the outline, or `general`), what the supervisor asks (a short quote or a close paraphrase), and one line on what doing it would involve. Tag it `content`, `structure`, `sources`, `style` or `formal`.
3. A point you cannot place or understand becomes an item `ask supervisor: …`, with the question to ask.
4. Write `thesis/feedback/<date>.md` in the format of `kit/reference/thesis-folder.md`, grouped by section in outline order, with `general` first. If `sync-word.md` already saved that day's comments there, turn that file into the list.
5. Tell the student where the list is, how many items it has and how they split by tag.

When the student picks an item, work on that item only (drafting goes through `kit/workflows/draft-section.md`), and tick it once they say it's done.

## Done when

Every point in the feedback is exactly one item in the list, and no thesis text has changed.
