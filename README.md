# thesis-kit

A Cursor workspace for writing a thesis from sources you checked yourself.

You open this folder in [Cursor](https://cursor.com), an editor with an AI assistant built in, and the assistant becomes your research and writing partner. The kit gives it a set of tools for every part of the work, from finding papers to handing in, and one rule it follows throughout: **your text only cites papers you have opened and confirmed yourself.**

- **A toolbox, not a path.** Every tool works on its own. Use what helps, whenever it helps, in any order.
- **Papers you can trust.** Every paper's DOI and details are checked against the registries (Crossref, DataCite, OpenAlex), flagging wrong DOIs, retracted studies and references no registry knows. A paper only counts once *you* confirm you read it.
- **Writing that stays yours.** The AI drafts one section at a time from your checked papers, marks what it can't back up with `[CHECK]`, and you rewrite it in your own words.
- **Word in, Word out.** Export to Word when you're ready, keep working there, and sync your latest version and your supervisor's comments back in.
- **An honest record.** An optional log of what the AI did turns into your AI declaration at the end.

No coding. You talk to the AI in plain language, and it does the technical parts.

## Get started (about 15 minutes)

1. **Install Cursor** from [cursor.com](https://cursor.com) and sign in. The free plan is enough to start.
2. **Make an empty folder** for your thesis, for example a folder called `my-thesis` in your home folder (on a Mac: Finder → *Go* → *Home*).
   Don't put it inside iCloud Drive, Dropbox or OneDrive, or in Desktop or Documents if those sync to the cloud. Cloud syncing can quietly break the kit's saved versions.
3. **Open the folder in Cursor:** *File → Open Folder…*
4. **Open the AI chat** (the panel on the right; if you don't see it, press `Cmd+L` on a Mac or `Ctrl+L` on Windows). If there is a mode menu, choose **Agent**. Then paste this sentence:

   > Set up thesis-kit in this folder: run `git clone https://github.com/squaloo-studio/thesis-kit.git .` outside Cursor's sandbox (if the folder isn't empty, or my computer asks to install developer tools or git, sort it out and walk me through it), then read AGENTS.md and start the setup.

   Cursor asks you to allow this first command, which downloads the kit: click allow.

5. **Answer a few questions** about your thesis: your research question or topic, field, university, language, citation style, deadline. "Don't know yet" is a fine answer.

On a Mac, the first time, a window may offer to install "command line developer tools": click **Install** and wait a few minutes. When setup is done, the AI shows you the tools below.

## When Cursor asks you to allow a command

The kit works by running small commands on your computer: saving a version of your files, checking papers against the registries, making a Word file. Cursor runs them in a protected space, a sandbox, that can only change this folder and reach a few websites. The kit brings a list of the free paper databases it may reach, so these commands go through by themselves.

A few commands need more: downloading the kit at the start, changing git's settings during setup, updating the kit, setting up the online backup, installing a tool. For those, Cursor shows you the command and waits for you to allow it, and the AI says in one line what it does.

If your Cursor asks before every command instead (set under **Cursor Settings → Agents → Approvals & Execution**), add the kit's own tools to the allowlist: `python3 kit/scripts/` (on Windows: `py -3 kit/scripts/`). A **Run Everything** mode never asks, but it lets the AI run anything on your computer, so the sandbox or the allowlist is safer.

## The tools

Say it in your own words; the phrases are just examples. Ask "what can you do?" in the chat to see this list there.

**Finding papers**
- **"make my exposé"**: a map of your field from the scholarly databases: research groups, debates, gaps, a first outline, and the papers the field builds on.
- **"find sources for 2.1"** or **"look for more sources"**: new leads for one section or the whole thesis, from the databases and from what the papers you've read cite and are cited by.
- **"add these sources"**, plus a pasted list, DOIs, a Zotero export, or PDFs you saved in `thesis/papers/`: each paper looked up in the registries and added to `sources.md`.

**Reading and checking**
- **"I read Müller 2021: it found …"**: that paper becomes *checked*, so it can be cited.
- **"file these notes"**, plus answers from Gemini Notebook or your own notes: notes stored next to the right paper.
- **"check this sentence: …"**: whether your checked papers really support it.

**Shaping and writing**
- **"help me sharpen my question"**: an interview that turns a topic into a precise research question, if you want one.
- **"use this outline"**, plus your supervisor's structure or your own: imported into `outline.md`.
- **"draft 2.1"**: one section drafted from your checked papers, for you to rewrite in your own words.

**Word and your supervisor**
- **"export to Word"**: a new Word file with a formatted reference list. "Export 2.1 to Word" does the same for a single draft.
- **"sync my Word file"**: your latest Word text, comments and tracked changes brought back. Save the file into `thesis/word/` first.
- **"make a to-do list from these comments"**: supervisor feedback as a list you work through.

**Handing in**
- **"write my AI declaration"**: a draft declaration from the AI log.

**Looking after your work**
- **"undo that"** or **"show me 2.1 from last Tuesday"**: an earlier saved version.
- **"set up an online backup"**: a private copy of your work on GitHub, if you want one.
- **"turn the AI log off"** (or on).
- **"update my kit"**: the latest version of the kit, with your files untouched.

## Tools that work well alongside

These are free to start, and every one is optional. The kit doesn't connect to them: use them on their own and bring the results in by pasting them or exporting a file (Zotero: .bib or .ris), saying "add these sources" or "file these notes". That works with any tool.

| Tool | Use it to |
|---|---|
| [Consensus](https://consensus.app) | ask your question in plain words and see what studies say |
| [Semantic Scholar](https://www.semanticscholar.org) | search papers, with short summaries |
| [ResearchRabbit](https://www.researchrabbit.ai) | find papers connected to the ones you like |
| [Zotero](https://www.zotero.org) | keep your papers and PDFs in one library |
| [Gemini Notebook](https://notebooklm.google.com) (formerly NotebookLM) | ask questions answered only from your own PDFs |

If you already use [Elicit](https://elicit.com), it works well for comparing many studies in a table.

## How the kit keeps your thesis honest

- Papers start as **unchecked** leads. Only you can make one **checked**, by confirming you read it and writing one line about it in your own words.
- Drafts cite only checked papers, and every save checks that each citation in your text belongs to one.
- The AI never rewrites your text without asking, and it only reads your Word files; it never edits them.

Your department decides what AI use is allowed. If you tell the kit your university's rules during setup, it reminds you when a request might conflict. The AI log (on by default, easy to turn off) records what the AI did, so your final declaration is accurate.

## A note on AI models

Free plans work, within their usage limits. For the serious writing months, a paid plan with stronger AI models gives noticeably better results and more usage.

## Your files

Your thesis lives in the `thesis/` folder on your computer. After every job the kit saves a version, so "undo" always works. PDFs you save in `thesis/papers/` stay on this computer only: they are not part of saved versions or the online backup. If you like, the kit can also back your work up in a private GitHub repository (a free account and about five minutes; say "set up an online backup"). Keeping everything local is fine too; just back up your computer as you would anyway.

## Other AI tools

The instructions live in `AGENTS.md`, which many AI coding tools read, so Codex, Claude Code and others will probably work too (some need to be told to read it first). Feedback is welcome.

## Manual install

If the one-sentence setup doesn't work for you: install git, clone this repository (`git clone https://github.com/squaloo-studio/thesis-kit.git my-thesis`, or use *Clone repo* on Cursor's start screen), open the folder in Cursor, and say "start" in the chat.

## Contributing

Ideas, bugs and improvements are welcome as [issues](https://github.com/squaloo-studio/thesis-kit/issues) and pull requests. When you open this repository to work on the kit itself, tell the AI so, and it skips the student setup. How the kit works:

- `AGENTS.md`: the rules and the list of jobs, loaded in every chat
- `kit/workflows/`: one instruction file per job
- `kit/reference/`: the thesis folder's formats, saving versions, installing tools
- `kit/templates/`: the starting files for a student's `thesis/`
- `kit/scripts/`: `sources.py` (search, citation chasing, registry checks, adding sources, PDF text) and `thesis.py` (saving versions, Word export and sync), Python standard library only, no API key needed
- `tests/`: automated tests for both scripts, no internet needed. Run them with `python3 -m unittest discover -s tests`
- `.cursor/sandbox.json`: the paper databases Cursor's sandbox may reach

## License

MIT License, see [`LICENSE`](LICENSE).
