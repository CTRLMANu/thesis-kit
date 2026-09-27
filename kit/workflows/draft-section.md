# Draft a section

Writes a first version of **one** outline section from the student's checked sources, for the student to rewrite in their own words.

## 1. Pin down the section

1. Find the section in `thesis/outline.md` by number or name. Without an outline, offer to make one first (`make-expose.md` or `import-outline.md`); if the student insists, draft from their description of the section.
2. Find its chapter file, `thesis/chapters/NN-name.md`, and read the first line:
   - no file yet, or `master: kit`: the draft goes into the chapter file;
   - `master: word`: the draft goes into `thesis/drafts/<section>-<short-name>.md`, for the student to paste into Word.
3. If the section already has text **without** an AI draft marker, that text is the student's. Ask before touching it, and offer to put the new draft into `thesis/drafts/` instead.

## 2. Check the ground

1. Read `University rules on AI` in profile.md. If they forbid or limit AI-written text, say so in one sentence and offer feedback on the student's own draft instead. Do what the student decides.
2. Collect the `checked` sources that fit this section: the outline's `Sources:` line, plus any other checked entries whose `In my own words` line or notes fit. Read those lines, the notes, and their PDFs in `thesis/papers/` when present.
3. If fewer than two checked sources fit, say so, name the `unchecked` ones that would help, and ask whether to wait or to draft now with `[CHECK: …]` gaps.

## 3. Write

Write only this section, in the thesis language, in the register of an academic thesis at the student's degree level:

- Every claim about the literature cites a `checked` source in the readable form of the profile's citation style, for example `(Jumper et al., 2021)`, and says only what that source's own-words line, notes or PDF support.
- A claim the section needs but no checked source supports gets `[CHECK: what is missing]` in its place.
- Length: in proportion to the section's weight in the outline and the required length in profile.md; when unclear, 300–600 words.
- The section starts with `<!-- AI draft <date> · rewrite in your own words, then delete this line -->`. A new chapter file starts with `<!-- master: kit -->` and the chapter heading.

Then stop: one section per request.

## 4. Hand over

Tell the student where the draft is, which sources it used, and how many `[CHECK]` markers remain and why. Remind them in one sentence that the next step is theirs: rewrite it in their own words and delete the marker line when done.

## Done when

Exactly one section was written; every citation in it matches a `checked` entry in `sources.md`; every unsupported claim carries `[CHECK: …]`; the AI draft marker is its first line; and no other section changed.
