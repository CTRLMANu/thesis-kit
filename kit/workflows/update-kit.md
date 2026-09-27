# Update the kit

Pulls the latest version of the kit from GitHub. The student's `thesis/` folder is never touched, because the kit never ships files there.

## Steps

1. Save a version of `thesis/` if it has unsaved changes (`kit/reference/versions.md`).
2. Look for local changes to kit files: `git status --porcelain -- . ":(exclude)thesis"`. Any output means the student or a tool changed kit files. Show which ones and ask whether to discard them: `git checkout -- <file>` for changed files, deleting the file for new ones. Never touch anything inside `thesis/`. If they want to keep their changes, stop, and suggest proposing the change at https://github.com/CTRLMANu/thesis-kit/issues so it can be added for everyone.
3. `git fetch origin`, then `git log --oneline HEAD..origin/main` to see what's new. If nothing is new, say the kit is up to date and stop.
4. `git merge --no-edit origin/main`. A conflict should never happen; if it does, run `git merge --abort`, tell the student nothing was changed, and suggest reporting it at https://github.com/CTRLMANu/thesis-kit/issues with the message.
5. If `Online backup: yes` in profile.md: `git push --quiet backup HEAD:main`.
6. Summarise what's new in plain words, from the new commits' messages and the changed files in `kit/workflows/` and `README.md` ("new: the AI now also …"). If `kit/templates/` changed, explain that templates only apply to new setups, and offer to bring a specific improvement into the student's own files.

## Done when

No merge is in progress, `git merge-base --is-ancestor origin/main HEAD` succeeds, and nothing in `thesis/` was changed by the update.
