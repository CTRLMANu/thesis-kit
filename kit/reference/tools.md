# Getting a missing tool

Before installing anything, tell the student in one plain sentence what you are installing and why ("I'm installing a free converter so I can read your Word file"). Nothing here needs an administrator password.

Downloaded tools go into `.tools/` in the workspace, which git ignores and Cursor's sandbox may write to. Check for an existing copy first, and run the commands below from the workspace folder. On Windows, commands run in PowerShell, and `winget` comes with Windows 10 and 11.

## git

- **macOS:** the first git command opens Apple's dialog to install the "command line developer tools". Tell the student to click **Install** (not "Get Xcode") and wait until it finishes, which takes 5–15 minutes. Then run the command again.
- **Windows:** `winget install --id Git.Git -e --source winget`, then ask the student to restart Cursor.

## Python 3 (runs `kit/scripts/`)

- **macOS:** installed together with git's developer tools. `python3 --version` should show 3.9 or newer.
- **Windows:** `winget install --id Python.Python.3.12 -e --source winget`.

## pandoc (Word import and export)

Check first: `pandoc --version`, then `.tools/pandoc/bin/pandoc --version`. The kit's scripts find either copy by themselves.

**macOS:**

```sh
T=.tools; mkdir -p "$T"
V=$(curl -s https://api.github.com/repos/jgm/pandoc/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
ARCH=$( [ "$(uname -m)" = arm64 ] && echo arm64 || echo x86_64 )
curl -sL -o "$T/pandoc.zip" "https://github.com/jgm/pandoc/releases/download/$V/pandoc-$V-$ARCH-macOS.zip"
unzip -q -o "$T/pandoc.zip" -d "$T" && rm "$T/pandoc.zip" && rm -rf "$T/pandoc" && mv "$T/pandoc-$V-$ARCH" "$T/pandoc"
"$T/pandoc/bin/pandoc" --version
```

In your own pandoc commands, call it as `.tools/pandoc/bin/pandoc`.

**Windows:** `winget install --id JohnMacFarlane.Pandoc -e --source winget`, then restart the terminal and call `pandoc`.

## GitHub CLI (only for the online backup)

Check first: `gh --version`, then `.tools/gh/bin/gh --version`.

**macOS:**

```sh
T=.tools; mkdir -p "$T"
V=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"][1:])')
ARCH=$( [ "$(uname -m)" = arm64 ] && echo arm64 || echo amd64 )
curl -sL -o "$T/gh.zip" "https://github.com/cli/cli/releases/download/v$V/gh_${V}_macOS_$ARCH.zip"
unzip -q -o "$T/gh.zip" -d "$T" && rm "$T/gh.zip" && rm -rf "$T/gh" && mv "$T/gh_${V}_macOS_$ARCH" "$T/gh"
"$T/gh/bin/gh" --version
```

**Windows:** `winget install --id GitHub.cli -e --source winget`.

## PDF text (Windows, Linux)

On macOS, `sources.py pdf` reads PDFs with the system's own PDF support. Elsewhere it needs pypdf:

```sh
python3 -m pip install --target .tools/python pypdf
```

On Windows: `py -3 -m pip install --target .tools/python pypdf`.

## OpenAlex key (optional)

If `find` keeps answering with `ranked_by: crossref`, or a message says OpenAlex is rate-limited, a free key helps: the student creates a free account at https://openalex.org and copies their API key; save it as one line in `.tools/openalex-key`.
