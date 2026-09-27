# Set up the online backup

Connects the thesis to a **private** GitHub repository, so every saved version is also stored online. This is optional, and the student decides.

## 1. Explain and confirm

In plain words: it needs a free GitHub account (sign-up at https://github.com/signup takes a few minutes); the repository is private, so only they can see it; from then on, each saved version is also uploaded. Continue only on a clear yes. If they have no account yet, give them the link and wait until they do.

## 2. Get the GitHub tool and sign in

1. Get `gh` if needed (`kit/reference/tools.md`). Below, `gh` means its full path if it lives in `~/.thesis-kit/tools/`.
2. Run `gh auth status`. If not signed in, run `gh auth login --hostname github.com --git-protocol https --web`. It prints a one-time code: show the code to the student, have them open https://github.com/login/device, enter it and approve. If the command waits for a keypress you can't give, ask the student to open Cursor's terminal (*Terminal → New Terminal*), paste the same command, press Enter and follow it.
3. `gh auth setup-git`, so git can upload with that sign-in.

## 3. Create the repository and upload

1. Name it `thesis-<short topic>-backup`, lowercase with hyphens, unless the student prefers another name.
2. `gh repo create <name> --private --source . --remote backup --push`.
3. Check: `gh repo view <name> --json visibility -q .visibility` must print `PRIVATE`. If it prints anything else, immediately run `gh repo edit <name> --visibility private --accept-visibility-change-consequences`, check again, and tell the student.

## 4. Record it

Set `Online backup: yes · <repository URL>` in `thesis/profile.md` and save a version, which is now uploaded too. Tell the student where they can see it online.

## Done when

The `backup` remote exists, the repository's visibility is `PRIVATE`, `git ls-remote backup main` shows the same commit as `git rev-parse HEAD`, and profile.md records the backup.
