# Saved versions

A **version** is a git commit of `thesis/` only. To the student, call it "a saved version", never a commit. Versions are what make "undo" and "show me last Tuesday's 2.1" possible.

Everything below is run by you. Never use `git reset --hard`, `git push --force`, `git rebase` or anything else that rewrites or deletes history.

## Save a version

1. `git add -A -- thesis`
2. `git diff --cached --quiet -- thesis`: exit code 0 means nothing changed, so stop here.
3. `git commit --quiet -m "<what changed, in plain words>"`

- Stage only `thesis/`. Kit files never go into a version.
- The message names the job and the place: `drafted 2.1 Definitions`, `added 6 sources from Consensus`, `synced Word file (chapters 1–3)`.
- **Unsaved student edits first:** before a job starts, if `git status --porcelain -- thesis` shows changes, save them as a version called `your own edits` so the student's writing and yours stay apart in the history.
- If `Online backup: yes` in profile.md, push after saving: `git push --quiet backup HEAD:main`. If the push fails (offline, expired sign-in), tell the student once in one sentence and carry on. The version is safe locally.

## Undo the last change

1. Find the latest version that touched the thesis: `git log -1 --format='%h %ad %s' --date=format:'%d %b %H:%M' -- thesis`.
2. Tell the student what it was ("the last saved version is 'drafted 2.1 Definitions' from 14:02; undo it?") and wait for yes.
3. `git revert --no-edit <hash>`. This adds a new version that reverses the old one, so the undo can itself be undone.
4. If the revert stops with a conflict: `git revert --abort`, explain that later changes touched the same text, and offer to restore the affected files one by one (below).

## See or restore an older version

- List a file's history: `git log --format='%h %ad %s' --date=format:'%a %d %b %H:%M' -- <file>`. Show it to the student as dates and descriptions.
- Show an old version: `git show <hash>:<file>`. For a single section, show just that section.
- Restore, after the student agrees: `git checkout <hash> -- <file>`, then save a version `restored <file> from <date>`. Restore single sections by editing the current file instead, so nothing else is lost.
