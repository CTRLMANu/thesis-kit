# Saved versions

A **version** is a git commit of `thesis/` only. To the student, call it "a saved version", never a commit. Versions are what make "undo" and "show me last Tuesday's 2.1" possible. Never use `git reset --hard`, `git push --force`, `git rebase` or anything else that rewrites or deletes history.

## Save a version

`python3 kit/scripts/thesis.py save "<what changed, in plain words>"` saves `thesis/` and nothing else. The description names the job and the place: `drafted 2.1 Definitions`, `added 6 sources from Consensus`, `synced Word file (chapters 1–3)`. `--own-edits` saves the student's unsaved changes as `your own edits`, without a log row, so their writing and yours stay apart in the history.

## Undo the last change

1. Find the latest version that is neither the student's own edits nor only a log row: `git log -1 --format='%h %ad %s' --date=format:'%d %b %H:%M' --invert-grep --grep='^your own edits$' -- thesis ':(exclude)thesis/ai-log.md'`.
2. Tell the student what it was ("the last saved version is 'drafted 2.1 Definitions' from 14:02; undo it?") and wait for yes.
3. `git revert --no-commit <hash>`, then `git checkout HEAD -- thesis/ai-log.md` if that file exists, so the AI log keeps every row. Then `python3 kit/scripts/thesis.py save "undid: <its description>"`. The undo is a new version, so it can itself be undone.
4. If the revert reports a conflict in a file other than `thesis/ai-log.md`: `git revert --abort`, explain that later changes touched the same text, and offer to restore the affected files one by one (below).

## See or restore an older version

- List a file's history: `git log --format='%h %ad %s' --date=format:'%a %d %b %H:%M' -- <file>`. Show it to the student as dates and descriptions.
- Show an old version: `git show <hash>:<file>`. For a single section, show just that section.
- Restore, after the student agrees: `git checkout <hash> -- <file>`, then save a version `restored <file> from <date>`. Restore single sections by editing the current file instead, so nothing else is lost.
