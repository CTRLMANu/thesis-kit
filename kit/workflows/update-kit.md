# Update the kit

Pulls the latest version of the kit from GitHub. The student's `thesis/` folder is never touched, because the kit never ships files there.

## Steps

1. Look for changes to kit files: `git status --porcelain --untracked-files=no -- . ":(exclude)thesis"`. Any output lists kit files the student or a tool changed. Show them and ask whether to discard the changes with `git checkout -- <file>`. If they want to keep them, stop, and suggest proposing the change at https://github.com/CTRLMANu/thesis-kit/issues so everyone gets it.
2. Files that are in no saved version are never deleted. If the student's own files (a `.docx`, a PDF) sit outside `thesis/` (`git ls-files --others --exclude-standard -- . ":(exclude)thesis"`), offer to move them into `thesis/word/` or `thesis/papers/`.
3. `git fetch origin`, then `git log --oneline HEAD..origin/main` to see what's new. If nothing is new, say the kit is up to date and stop.
4. `git merge --no-edit origin/main`, which needs the student's approval to run outside the sandbox. If the merge fails for any reason, run `git merge --abort`, tell the student nothing was changed, and suggest reporting it at https://github.com/CTRLMANu/thesis-kit/issues with the message.
5. If `Online backup: yes` in profile.md: `git push --quiet backup HEAD:main`.
6. Summarise what's new in plain words, from the new commits' messages and the changed files in `kit/workflows/` and `README.md` ("new: the AI now also …"). If `kit/templates/` changed, explain that templates only apply to new setups, and offer to bring a specific improvement into the student's own files.

## Done when

No merge is in progress, `git merge-base --is-ancestor origin/main HEAD` succeeds, and nothing in `thesis/` was changed by the update.
