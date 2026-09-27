# Setup

Sets the kit up for a student in one short conversation: their profile, their research question in their own words, and a few settings. Runs on the first chat, when `thesis/profile.md` does not exist yet.

## 1. Welcome

In two or three plain sentences: the kit is a set of tools for researching and writing their thesis from papers they checked themselves, to use whenever they like; first come a few quick questions; "skip" or "don't know yet" is always a fine answer.

## 2. Ask about the thesis

In one message, as a short numbered list they can answer in any order:

1. Your name (optional, for the title page)
2. Your research question or topic, in your own words
3. Field or subject
4. Degree: Bachelor's, Master's, PhD, other
5. University and department
6. Thesis language
7. Required length, if you know it
8. Deadline

Follow up only on answers you cannot use (a deadline without a year, for example).

## 3. Ask about the settings

In a second message:

1. Citation style (APA, Harvard, Chicago, MLA, IEEE, DIN, …). "Don't know" is fine; it can be set any time later.
2. Does your university have rules on using AI in a thesis? Paste a link or the text if you have it; "skip" is fine.
3. The AI log, in two sentences: the kit keeps a short record of what the AI does (found sources, drafted 2.1, …), so it can draft the AI declaration many universities ask for. It is on unless they'd rather turn it off, now or later.
4. The online backup, once: their work is saved on this computer with an undo history, like any folder. It can also be backed up online in a private GitHub repository, which needs a free GitHub account and about five minutes of extra setup. Skipping it is completely fine, and they can ask for it any time.

## 4. Create the thesis folder

1. Copy `kit/templates/profile.md` to `thesis/profile.md` and fill it with their answers. Write `skipped` or `don't know yet` where they gave none.
2. If they gave a question or topic, write `thesis/question.md`: the heading `# My research question`, then their words exactly as they wrote them.
3. Create the folders `thesis/papers/`, for their PDFs, and `thesis/word/`, for their Word files.

Every other file in `thesis/` is created by the tool that first needs it.

## 5. Prepare saving

1. If `git rev-parse --is-inside-work-tree` fails, the kit was downloaded without git: run `git init`, and tell the student that saved versions work but kit updates need the install from the README.
2. If `git config user.name` prints nothing, run `git config user.name "<their name, or Thesis student>"`. If `git config user.email` prints nothing, run `git config user.email "student@thesis-kit.local"`.
3. `git remote set-url --push origin DISABLED`, which stops anything from ever being uploaded to the public kit.
4. Save the first version, `set up my thesis`, as described in `kit/reference/versions.md`.
5. If they chose the online backup, run `kit/workflows/setup-backup.md` now.

## 6. Hand over

In a few lines: their thesis folder is set up, PDFs go into `thesis/papers/` and Word files into `thesis/word/`. Then give an overview of the tools from the README section "The tools": grouped by purpose, one line each, with the words to say. The student picks from there.

## Done when

Every field in `thesis/profile.md` holds an answer, `skipped` or `don't know yet`; `thesis/question.md` holds their words unchanged, if they gave any; the first version is saved; and `git remote get-url --push origin` prints `DISABLED` (when an `origin` exists).
