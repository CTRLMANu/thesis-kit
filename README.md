# thesis-kit

A Cursor workspace for writing a thesis from sources you checked yourself.

You open this folder in [Cursor](https://cursor.com), an editor with an AI assistant built in, and the assistant becomes your research and writing partner. It walks you from a vague topic to a handed-in thesis, and it follows one rule throughout: **your text only cites papers you have opened and confirmed yourself.**

- **A path to follow.** A checklist takes you from topic to hand-in, with the next step always spelled out. Ask "what now?" at any time.
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

5. **Answer a few questions** about your thesis: topic, field, university, language, citation style, deadline. "Don't know yet" is a fine answer.

Cursor will ask you to allow the commands the AI runs. The AI tells you what each one does. On a Mac, the first time, a window may offer to install "command line developer tools": click **Install** and wait a few minutes.

When setup is done, open `thesis/START-HERE.md`. That's your map.

## Things you can ask

| Say something like | What happens |
|---|---|
| "what now?" | where you stand, and the one next step |
| "help me sharpen my question" | an interview that turns your topic into one clear research question |
| "make my exposé" | a map of your field from the scholarly databases: research groups, debates, gaps, a first outline, papers worth opening |
| "add these sources" + a pasted list, DOIs, a Zotero export or PDFs | papers checked against the registries and added to `sources.md` |
| "I read Müller 2021: it found …" | that paper becomes *checked*, so it can be cited |
| "file these notes" + answers from Gemini Notebook or your own notes | notes stored next to the right paper |
| "use this outline" + your supervisor's structure | imported into `outline.md` |
| "draft 2.1" | one section drafted from your checked papers, for you to rewrite |
| "check this sentence: …" | whether your sources really support it |
| "export to Word" / "sync my Word file" | a new Word file / your latest Word text and comments brought back |
| "make a checklist from these comments" | supervisor feedback as a to-do list |
| "write my AI declaration" | a draft declaration from the AI log |
| "undo that" / "show me 2.1 from last Tuesday" | an earlier saved version |
| "update my kit" | the latest version of the kit, with your files untouched |

## Research tools

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
