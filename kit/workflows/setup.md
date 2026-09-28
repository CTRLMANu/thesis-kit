# Setup

Sets the kit up in one short conversation: the student's profile, their research question in their own words, and a few settings.

## 1. Welcome

In two or three sentences: the kit is a set of tools for researching and writing their thesis from papers they checked themselves, to use whenever they like; first come a few quick questions; "skip" or "don't know yet" is always a fine answer.

## 2. Ask about the thesis

In one message, as a short numbered list they can answer in any order:

1. Your name (optional, for the title page)
2. Your research question or topic, in your own words
3. Field or subject
4. Degree: Bachelor's, Master's, PhD, other
5. University and department
6. Thesis language
7. Required length, if you know it
8. Deadline (with the year)

Leave out what they already told you, and repeat those answers in one line so they can correct them, for example: "Master's in business, on how remote work affects job satisfaction, due in April (which year?)".

## 3. Ask about the settings

In a second message:

1. Citation style (APA, Harvard, Chicago, MLA, IEEE, DIN, …). "Don't know" is fine; it can be set later.
2. Does your university have rules on using AI in a thesis? Paste a link or the text if you have it; "skip" is fine.
3. The AI log, in two sentences: the kit keeps a short record of what the AI does (found sources, drafted 2.1, …), so it can draft the AI declaration many universities ask for. It is on unless they turn it off, now or later (you write `AI log: on` or `off`).
4. The online backup, once: their work is saved on this computer with an undo history; it can also go to a private GitHub repository (a free GitHub account, about five minutes). Skipping it is fine; they can ask for it any time ("set up an online backup").

Follow up only on answers you cannot use, for example a deadline without a year, or "Chicago" (with footnotes or author-date?).

## 4. Create the thesis folder

1. Copy `kit/templates/profile.md` to `thesis/profile.md` and fill it with their answers. Write `skipped` or `don't know yet` for questions they left open; leave Working title and Supervisor empty unless they mentioned them.
2. If they gave a question or topic, write `thesis/question.md`: the heading `# My research question`, then their words exactly as they wrote them.
3. Create the folders `thesis/papers/` and `thesis/word/`.

## 5. Prepare saving

Steps 1–3 change git's settings, so they need the student's approval outside Cursor's sandbox.

1. If `git rev-parse --show-toplevel` fails or prints a folder other than this one, the kit was downloaded without git: run `git init`, and tell the student that saved versions work but kit updates need the install from the README.
2. If `git config user.name` prints nothing, run `git config user.name "<their name, or Thesis student>"`. If `git config user.email` prints nothing, run `git config user.email "student@thesis-kit.local"`.
3. When an `origin` exists: `git remote set-url --push origin DISABLED`, so nothing is ever uploaded to the public kit.
4. `python3 kit/scripts/thesis.py save "set up my thesis"`.
5. If they chose the online backup, run `kit/workflows/setup-backup.md` now.

## 6. Hand over

In a few lines: their thesis folder is set up; PDFs go into `thesis/papers/` (they stay on this computer, outside saved versions) and Word files into `thesis/word/`. Then list every tool from the README section "The tools", in its groups, one line per tool with the words to say. Keep every line, including "set up an online backup" and "turn the AI log off", whatever they chose.

## Done when

Every field setup asked about holds an answer, `skipped` or `don't know yet` in `thesis/profile.md`; `thesis/question.md` holds their words unchanged, if they gave any; the first version is saved; and `git remote get-url --push origin` prints `DISABLED` (when an `origin` exists).
