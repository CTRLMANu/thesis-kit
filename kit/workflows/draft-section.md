# Draft a section

Writes a first version of **one** outline section from the student's checked sources, for the student to rewrite in their own words.

## 1. Pin down the section

1. Find the section in `thesis/outline.md` by number or name. When there is no outline, or the section isn't in it, ask what the section should cover and which chapter it belongs to.
2. Find its chapter file, `thesis/chapters/NN-name.md`, and read the first line:
   - no file yet, `master: kit`, or no master line: the draft goes into the chapter file;
   - `master: word`: the draft goes into `thesis/drafts/<section>-<short-name>.md`, for the student to paste into Word.
3. If the section already has text **without** an AI draft marker, that text is the student's. Ask before touching it, and offer to put the new draft into `thesis/drafts/` instead.

## 2. Check the ground

1. If the university's AI rules in profile.md limit AI-written text, say so (rule 9) and offer feedback on the student's own draft instead.
2. Collect the `checked` sources that fit this section: the outline's `Sources:` line, plus any other checked entries whose `In my own words` line or notes fit. Read those lines and the notes. From their PDFs in `thesis/papers/`, read only the passages you need: `python3 kit/scripts/sources.py pdf <file> --find "<term>|<term>"`, then `--pages A-B` around the hits. The script's `PDF page K` is the page's place in the file; a citation uses the number printed on the page itself (look with `--pages K`), or no page when none is printed.
3. If fewer than two checked sources fit, say so, name the `unchecked` ones that would help, and ask whether to wait or to draft now with `[CHECK: …]` gaps.

## 3. Write

Write only this section, in the thesis language, in the register of an academic thesis at the student's degree level:

- Every claim about the literature cites a `checked` source with its `Cite as` key (`[@jumper2021]`, `[@jumper2021, p. 7]`, narrative `@jumper2021`) and says only what that source's own-words line, notes or PDF support.
- A claim the section needs but no checked source supports gets `[CHECK: what is missing]` in its place.
- Length: in proportion to the section's weight in the outline and the required length in profile.md; when unclear, 300–600 words.
- The first line under the section's heading is `<!-- AI draft YYYY-MM-DD · rewrite in your own words, then delete this line -->`. A new chapter file starts with `<!-- master: kit -->`, then the chapter heading one level higher than in the outline: `# 2 Literature review`, sections `## 2.2 …`. Add only this section's heading and text: no headings or placeholder text for other sections.

Reread the section sentence by sentence against those own-words lines, notes and PDF passages. A claim they do not support becomes `[CHECK: …]` or is cut. Then stop.

## 4. Hand over

Tell the student:
- where the draft is;
- which sources it used;
- how many `[CHECK]` markers it has and what each one is missing, or that it has none;
- that citations are keys like `[@jumper2021]`, which the Word export turns into their citation style;
- that it stays marked as an AI draft until they have rewritten it in their own words and deleted the marker line.

For a draft in `thesis/drafts/`, offer a Word version to paste: `python3 kit/scripts/thesis.py export thesis/drafts/<file>`.

## Done when

Exactly one section was written; every claim about the literature in it carries the key of a `checked` source that supports it, or is a `[CHECK: …]`; the AI draft marker is the first line under its heading; no other section changed; and `thesis.py save` reports no problems in this change.
