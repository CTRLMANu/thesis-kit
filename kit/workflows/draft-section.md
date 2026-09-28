# Draft a section

Drafts **one** outline section from the student's checked sources, for them to rewrite in their own words.

## 1. Pin down the section

1. Find the section in `thesis/outline.md` by number or name. If it or the outline is missing, ask what it should cover and which chapter it belongs to.
2. Find its chapter file, `thesis/chapters/NN-name.md`, and read the first line:
   - no file yet, `master: kit`, or no master line: the draft goes into the chapter file;
   - `master: word`: the draft goes into `thesis/drafts/<section>-<short-name>.md`, for pasting into Word.
3. Text already in the section **without** an AI draft marker is the student's: ask before touching it, and offer to put the draft into `thesis/drafts/` instead.

## 2. Check the ground

1. If the university's AI rules in profile.md limit AI-written text, say so (rule 9) and offer feedback on the student's own draft instead.
2. Collect the `checked` sources that fit this section: the outline's `Sources:` line, plus other checked entries whose `In my own words` line or notes fit. Read those lines and notes. From their PDFs in `thesis/papers/`, read only the passages you need: `python3 kit/scripts/sources.py pdf <file> --find "<term>|<term>"`, then `--pages A-B` around the hits. A citation uses the number printed on the page (look with `--pages K`), or no page when none is printed; the script's `PDF page K` is its place in the file.
3. If fewer than two checked sources fit, say so, name the `unchecked` ones that would help, and ask whether to wait, find more sources first (`find-sources.md`), or draft now with `[CHECK: …]` gaps.

## 3. Write

Write only this section, in the thesis language and the register of an academic thesis at the student's degree level:

- Every claim about the literature cites a `checked` source with its `Cite as` key (`[@jumper2021]`, `[@jumper2021, p. 7]`, narrative `@jumper2021`) and says only what that source's own-words line, notes or PDF support.
- A claim the section needs but no checked source supports gets `[CHECK: what is missing]` in its place.
- Length follows the evidence: only what the checked sources carry, roughly one paragraph per point they support; never stretch. When the outline's weight or the required length in profile.md asks for more, write what they carry and mark the gaps with `[CHECK: …]`.
- The first line under the section's heading is `<!-- AI draft YYYY-MM-DD · rewrite in your own words, then delete this line -->`. A new chapter file starts with `<!-- master: kit -->`, then the chapter heading one level higher than in the outline: `# 2 Literature review`, sections `## 2.2 …`. Add only this section's heading and text, nothing for other sections.

Reread it sentence by sentence against those lines, notes and PDF passages; a claim without support there becomes `[CHECK: …]` or is cut. Then stop.

## 4. Hand over

Tell the student:
- where the draft is;
- which sources it used;
- how many `[CHECK]` markers it has and what each is missing (or that it has none), and, if it is shorter than asked, that the sources carry no more;
- that citations are keys like `[@jumper2021]`, which the Word export turns into their citation style;
- that it stays marked as an AI draft until they rewrite it in their own words and delete the marker line.

For a draft in `thesis/drafts/`, offer a Word version to paste: `python3 kit/scripts/thesis.py export thesis/drafts/<file>`.

## Done when

Exactly one section was written; every literature claim in it carries the key of a `checked` source that supports it, or is a `[CHECK: …]`; the AI draft marker is the first line under its heading; no other section changed; and `thesis.py save` reports no problems in this change.
