# Setup

Creates the student's `thesis/` folder and profile through a short, friendly conversation. Runs on the first chat, when `thesis/profile.md` does not exist yet.

## 1. Welcome

In three or four plain sentences: this kit helps them research and write their thesis from papers they checked themselves; you'll ask a few quick questions and then set up their files; "skip" or "don't know yet" is always a fine answer.

## 2. Ask about the thesis

Ask these in one message, as a short numbered list the student can answer in any order:

1. Your name (optional, for the title page)
2. Your topic, even if it's still vague
3. Field or subject
4. Degree: Bachelor's, Master's, PhD, other
5. University and department
6. Thesis language
7. Required length, if you know it
8. Deadline

Follow up only on answers you cannot use (a deadline without a year, for example).

## 3. Ask how they work

In a second message:

1. Citation style (APA, Harvard, Chicago, MLA, IEEE, DIN, …). "Don't know" is fine: suggest they ask their supervisor.
2. Which research tools do you already use? (Consensus, Semantic Scholar, ResearchRabbit, Zotero, Gemini Notebook, Google Scholar, your library's search, something else, none yet)
3. Does your university have rules on using AI in a thesis? Paste a link or the text if you have it; "skip" is fine.

## 4. Explain the AI log

Two sentences: the kit keeps a short log of what the AI does (found sources, drafted 2.1, …), so at the end it can draft the AI declaration many universities ask for. It's on unless they'd rather turn it off, now or any time later. Record their choice.

## 5. Offer the online backup, once

Say plainly: their work is saved on this computer with an undo history, like any folder. Optionally it can also be backed up online, in a private GitHub repository; that needs a free GitHub account and about five minutes of extra setup. Skipping is completely fine, and they can ask for it later ("set up an online backup").

Record yes or no. On yes, run `kit/workflows/setup-backup.md` after step 7.

## 6. Create the thesis folder

1. Copy every file in `kit/templates/` into `thesis/`.
2. Fill `thesis/profile.md` with their answers. Write `skipped` or `don't know yet` where they gave none.
3. Put their topic, in their words, under "Topic, in my words" in `thesis/question.md`.
4. Tailor `thesis/START-HERE.md` to the tools they named: in steps 4–6, mention the tools they already use first; tools they don't use stay as optional suggestions; a tool they named that is not in the table gets its own row.
5. Create the folders `thesis/chapters/`, `thesis/drafts/`, `thesis/papers/`, `thesis/word/`, `thesis/export/` and `thesis/feedback/`, each with an empty `.gitkeep` file so it is saved.

## 7. Prepare saving

1. If `git rev-parse --is-inside-work-tree` fails, the kit was downloaded without git: run `git init`, and tell the student that saved versions work but kit updates need the install from the README.
2. If `git config user.name` prints nothing, run `git config user.name "<their name, or Thesis student>"`. If `git config user.email` prints nothing, run `git config user.email "student@thesis-kit.local"`.
3. `git remote set-url --push origin DISABLED`, which stops anything from ever being uploaded to the public kit.
4. Save the first version, `set up my thesis`, as described in `kit/reference/versions.md`.

## 8. Hand over

In a few lines: their thesis folder and checklist are ready, `thesis/START-HERE.md` is their map, and "what now?" works any time. Suggest step 2: *"help me sharpen my question"*.

## Done when

Every field in `thesis/profile.md` holds an answer, `skipped` or `don't know yet`; step 1 is ticked in `thesis/START-HERE.md`; the first version is saved; and `git remote get-url --push origin` prints `DISABLED` (when an `origin` exists).
