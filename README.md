# thesis-kit

A Cursor workspace for writing a thesis from sources you checked yourself.

You open this folder in [Cursor](https://cursor.com), an editor with an AI assistant built in, and the assistant becomes your research and writing partner. The kit gives it a set of tools for every part of the work, from finding papers to handing in, and one rule it follows throughout: **your text only cites papers you have opened and confirmed yourself.**

- **A toolbox, not a path.** Every tool works on its own. Use what helps, whenever it helps, in any order.
- **Papers you can trust.** Every paper is checked against the official registries (Crossref, DataCite), which catches invented references, wrong DOIs and retracted studies. A paper only counts once *you* confirm you read it.
- **Writing that stays yours.** The AI drafts one section at a time from your checked papers, marks what it can't back up with `[CHECK]`, and you rewrite it in your own words.
- **Word in, Word out.** Export to Word when you're ready, keep working there, and sync your latest version and your supervisor's comments back in.
- **An honest record.** An optional log of what the AI did turns into your AI declaration at the end.

No coding. You talk to the AI in plain language, and it does the technical parts.

## Get started (about 15 minutes)

1. **Install Cursor** from [cursor.com](https://cursor.com) and sign in. The free plan is enough to start.
2. **Make an empty folder** for your thesis, for example a folder called `thesis` in your home folder (on a Mac: Finder → *Go* → *Home*).
   Don't put it inside iCloud Drive, Dropbox or OneDrive, or in Desktop or Documents if those sync to the cloud. Cloud syncing can quietly break the kit's saved versions.
3. **Open the folder in Cursor:** *File → Open Folder…*
4. **Open the AI chat** (the panel on the right; if you don't see it, press `Cmd+L` on a Mac or `Ctrl+L` on Windows). If there is a mode menu, choose **Agent**. Then paste this sentence:

   > Set up thesis-kit in this folder: run `git clone https://github.com/CTRLMANu/thesis-kit.git .` (if the folder isn't empty, or my computer asks to install developer tools or git, sort it out and walk me through it), then read AGENTS.md and start the setup.

5. **Answer a few questions** about your thesis: your research question or topic, field, university, language, citation style, deadline. "Don't know yet" is a fine answer.

Cursor will ask you to allow some of the commands the AI runs; see [below](#when-cursor-asks-you-to-allow-a-command). On a Mac, the first time, a window may offer to install "command line developer tools": click **Install** and wait a few minutes.

When setup is done, the AI shows you the tools below. Use whichever you need.

## When Cursor asks you to allow a command

The kit does its work by running small commands on your computer: saving a version of your files, checking papers against the registries, making a Word file. Cursor checks every command the AI wants to run. Harmless ones go through by themselves; for the others it shows you the command and waits for you to allow it. The AI says in one line what each one does. The kit's commands only touch your thesis folder and the free paper databases.

To be asked less often, open **Cursor Settings → Agents → Approvals & Execution** and add these two entries to the allowlist:

- `git`: saving versions of your work. The kit can't upload anything to the public kit; that is blocked during setup.
- `python3 kit/scripts/`: the kit's own tools for checking papers and making reference lists.

Commands on the allowlist run without asking; everything else is still checked. There is also a **Run Everything** mode that never asks. It's convenient, but it lets the AI run anything on your computer, so the allowlist is the safer choice.

## The tools

Use any of them, whenever you like, in any order. Say it in your own words; the phrases are just examples. Ask "what can you do?" in the chat to see this list there.

**Finding papers**
- **"make my exposé"**: a map of your field from the scholarly databases: research groups, debates, gaps, a first outline, and the papers the field builds on.
- **"add these sources"**, plus a pasted list, DOIs, a Zotero export, or PDFs you saved in `thesis/papers/`: each paper checked against the registries and added to `sources.md`.

**Reading and checking**
- **"I read Müller 2021: it found …"**: that paper becomes *checked*, so it can be cited.
- **"file these notes"**, plus answers from Gemini Notebook or your own notes: notes stored next to the right paper.
- **"check this sentence: …"**: whether your checked papers really support it.

**Shaping and writing**
- **"help me sharpen my question"**: an interview that turns a topic into a precise research question, if you want one.
- **"use this outline"**, plus your supervisor's structure or your own: imported into `outline.md`.
- **"draft 2.1"**: one section drafted from your checked papers, for you to rewrite in your own words.

**Word and your supervisor**
- **"export to Word"**: a new Word file with a formatted reference list.
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

These are free to start, and every one is optional. The kit accepts papers and notes from any tool, including ones not listed here.

| Tool | Use it to |
|---|---|
| [Consensus](https://consensus.app) | ask your question in plain words and see what studies say |
| [Semantic Scholar](https://www.semanticscholar.org) | search papers, with short summaries |
| [ResearchRabbit](https://www.researchrabbit.ai) | find papers connected to the ones you like |
| [Zotero](https://www.zotero.org) | keep your papers and PDFs in one library |
| [Gemini Notebook](https://notebooklm.google.com) (formerly NotebookLM) | ask questions answered only from your own PDFs |

If you already use [Elicit](https://elicit.com), it works well for comparing many studies in a table.

## How the kit keeps your thesis honest

- Every paper that comes in is checked against Crossref and DataCite: does the DOI exist, do the title, authors and year match, has it been retracted?
- Papers start as **unchecked** leads. Only you can make one **checked**, by confirming you read it and writing one line about it in your own words.
- Drafts cite only checked papers. Anything they can't support is marked `[CHECK: …]`.
- The AI drafts one section at a time and never rewrites your text without asking.
- The AI only reads your Word files; it never edits them.

Your department decides what AI use is allowed. If you tell the kit your university's rules during setup, it reminds you when a request might conflict. The AI log (on by default, easy to turn off) records what the AI did, so your final declaration is accurate.

## A note on AI models

Everything works on free plans. For the serious writing months, a paid plan with stronger AI models gives noticeably better results and more usage.

## Your files

Your thesis lives in the `thesis/` folder on your computer. After every job the kit saves a version, so "undo" always works. If you like, the kit can also back your work up online in a private GitHub repository; that needs a free GitHub account and about five minutes of setup (say "set up an online backup"). Keeping everything local is completely fine; just back up your computer as you would anyway.

## Updating

Say "update my kit". You get the latest instructions and tools, and your `thesis/` folder is never touched.

## Other AI tools

The instructions live in `AGENTS.md`, a format many AI coding tools read, so tools such as Codex or Claude Code will probably work too (some need to be told to read `AGENTS.md` first). Feedback is welcome.

## Manual install

If the one-sentence setup doesn't work for you: install git, clone this repository (`git clone https://github.com/CTRLMANu/thesis-kit.git thesis`, or use *Clone repo* on Cursor's start screen), open the folder in Cursor, and say "start" in the chat.

## Contributing

Ideas, bugs and improvements are welcome as [issues](https://github.com/CTRLMANu/thesis-kit/issues) and pull requests. When you open this repository to work on the kit itself, tell the AI so, and it skips the student setup. How the kit works:

- `AGENTS.md`: the rules and the list of jobs, loaded in every chat
- `kit/workflows/`: one instruction file per job
- `kit/reference/`: the thesis folder's formats, saving versions, installing tools
- `kit/templates/`: the files setup copies into a student's `thesis/`
- `kit/scripts/`: `sources.py` (search, registry checks, abstracts) and `bibliography.py` (reference lists), Python standard library only, no API keys
- `tests/`: automated tests for `sources.py`, no internet needed. Run them with `python3 -m unittest discover -s tests`

## License

MIT License, see [`LICENSE`](LICENSE).
