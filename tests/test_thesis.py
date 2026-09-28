"""Tests for kit/scripts/thesis.py.

No network: doi.org and zotero.org are faked. Every test works in its own
temporary workspace, with its own git repository where one is needed; the
global and system git settings are ignored. Export and sync need pandoc (on
PATH or in .tools/pandoc/bin/) and are skipped without it. Run from the
repository root:

    python3 -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "kit" / "scripts" / "thesis.py"
_spec = importlib.util.spec_from_file_location("thesis", SCRIPT)
thesis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(thesis)

PANDOC = shutil.which("pandoc") or shutil.which(str(REPO / ".tools" / "pandoc" / "bin" / "pandoc"))
needs_pandoc = unittest.skipUnless(PANDOC, "pandoc not found")
TODAY = thesis.today()

PROFILE = """# My thesis profile

## The thesis

- Name: Jana Müller
- Working title: Cooling cities
- Thesis language: English
- Citation style: APA 7
- Deadline: skipped

## Kit settings

- AI log: on
- Online backup: no
- Word template: none
"""

SOURCES = """# My sources

### Jumper et al. (2021) · Highly accurate protein structure prediction with AlphaFold
- Cite as: [@jumper2021]
- Status: checked · 2026-09-20
- DOI: 10.1038/s41586-021-03819-2
- Registry check: ok · 2026-09-01
- Published in: Nature 596(7873), 583–589
- Found via: Consensus
- In my own words: AlphaFold predicts protein structures accurately.
- Notes:

### Berg (n.d.) · Stadtklima
- Cite as: [@bergnd]
- Status: checked · 2026-09-21
- Registry check: no-doi: no registry record · 2026-09-01
- Published in: Springer Verlag
- Reference as given: Berg, K. (o. J.). Stadtklima. Springer Verlag.
- In my own words: A textbook on urban climate.
- Notes:

### Lund (2020) · Heat islands
- Cite as: [@lund2020]
- Status: unchecked
- DOI: 10.1000/heat
- Registry check: ok · 2026-09-01
- In my own words:
- Notes:

### Olsen (2019) · Green roofs
- Cite as: [@olsen2019]
- Status: dropped · 2026-09-22 · off topic
- Registry check: ok · 2026-09-01
- In my own words:
- Notes:
"""

# What doi.org answers for the AlphaFold DOI, trimmed: registry bookkeeping,
# lists where CSL wants strings, a closing period and footnote star, and the
# online-first date.
JUMPER_CSL = {
    "type": "journal-article", "title": ["Highly accurate protein structure prediction\n with AlphaFold.*"],
    "container-title": ["Nature"], "volume": "596", "page": "583-589",
    "author": [{"family": "Jumper", "given": "John", "sequence": "first", "affiliation": []}],
    "issued": {"date-parts": [[2021, 7, 15]]}, "published-print": {"date-parts": [[2021, 8, 26]]},
    "DOI": "10.1038/s41586-021-03819-2", "license": [{"URL": "https://example.org"}],
    "reference": [{"key": "ref1"}],
}


def csl_style(citation_format):
    """A tiny CSL style; the kit only reads its citation-format."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info><title>Test</title><id>test</id><category citation-format="{citation_format}"/>
    <updated>2020-01-01T00:00:00+00:00</updated></info>
  <citation><layout prefix="(" suffix=")" delimiter="; ">
    <names variable="author"><name form="short"/></names>
    <date variable="issued" prefix=", "><date-part name="year"/></date></layout></citation>
  <bibliography><layout><names variable="author"><name/></names>
    <date variable="issued" prefix=" (" suffix=")."><date-part name="year"/></date>
    <text variable="title" prefix=" "/></layout></bibliography>
</style>
"""


class Workspace(unittest.TestCase):
    """A temporary workspace with kit/templates/ and thesis/profile.md."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        env = patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        env.start()
        self.addCleanup(env.stop)
        self.write("kit/templates/ai-log.md",
                   "# AI log\n\n| Date | What the AI did | Where | Outside tools |\n|---|---|---|---|\n")
        self.write(".gitignore", ".tools/\nthesis/papers/\n")
        self.write("thesis/profile.md", PROFILE)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = thesis.main(list(argv), root=self.root)
        return code, out.getvalue()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, encoding="utf-8",
                              check=True).stdout

    def init_repo(self):
        """A repository whose first version holds the kit and the profile.
        It has no user name or e-mail configured."""
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=Kit", "-c", "user.email=kit@example.org", "commit", "-q", "-m", "kit")


class NoThesisFolder(Workspace):

    def test_every_command_refuses_without_thesis_folder(self):
        shutil.rmtree(self.root / "thesis")
        for argv in (["save", "x"], ["export"], ["sync"]):
            code, out = self.main(*argv)
            self.assertEqual(code, 1)
            self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertTrue(self.main("save", "x")[1].startswith("NOT SAVED: "))


# --------------------------------------------------------------------------
# save
# --------------------------------------------------------------------------

class Save(Workspace):

    def setUp(self):
        super().setUp()
        self.init_repo()

    def last_version(self):
        return self.git("log", "-1", "--format=%s|%an|%ae").strip().split("|")

    def saved_files(self):
        return self.git("show", "--name-only", "--format=", "HEAD").split()

    def test_saves_only_thesis_even_with_a_staged_kit_file(self):
        self.write("kit/templates/extra.md", "kit change\n")
        self.git("add", "kit/templates/extra.md")
        self.write("thesis/chapters/01-intro.md", "<!-- master: kit -->\n# 1 Intro\n")
        code, out = self.main("save", "drafted 1 Intro")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "saved: drafted 1 Intro")
        self.assertEqual(sorted(self.saved_files()), ["thesis/ai-log.md", "thesis/chapters/01-intro.md"])
        self.assertEqual(self.git("diff", "--cached", "--name-only").split(), ["kit/templates/extra.md"])
        self.assertEqual(self.git("status", "--porcelain", "--", "thesis"), "")

    def test_nothing_new_to_save(self):
        code, out = self.main("save", "--own-edits")
        self.assertEqual((code, out), (0, "nothing new to save\n"))

    def test_own_edits_have_their_own_message_and_no_log_row(self):
        self.write("thesis/question.md", "# My research question\n\nWhy?\n")
        code, out = self.main("save", "--own-edits")
        self.assertEqual(out.splitlines()[0], "saved: your own edits")
        self.assertEqual(self.last_version()[0], "your own edits")
        self.assertFalse((self.root / "thesis/ai-log.md").exists())

    def test_log_row_names_where_and_outside_tools(self):
        for name in ("sources.md", "memo.md", "outline.md", "chapters/01-intro.md"):
            self.write("thesis/" + name, "text\n")
        self.main("save", "added 6 sources | from Consensus", "--tools", "ChatGPT | Consensus")
        row = self.read("thesis/ai-log.md").splitlines()[-1]
        self.assertEqual(row, f"| {TODAY} | added 6 sources / from Consensus | "
                              "chapters/01-intro.md, memo.md, outline.md, +1 more | ChatGPT / Consensus |")
        code, out = self.main("save", "checked a sentence in 2.1")
        self.assertEqual(out.splitlines()[0], "saved: checked a sentence in 2.1")
        self.assertEqual(self.read("thesis/ai-log.md").splitlines()[-1],
                         f"| {TODAY} | checked a sentence in 2.1 | chat | – |")
        self.assertEqual(self.saved_files(), ["thesis/ai-log.md"])

    def test_no_log_row_when_the_log_is_off(self):
        self.write("thesis/profile.md", PROFILE.replace("AI log: on", "AI log: off"))
        self.main("save", "changed a setting")
        self.assertFalse((self.root / "thesis/ai-log.md").exists())

    def test_the_log_is_off_for_no_in_other_words_and_on_for_anything_else(self):
        for value, logged in (("no", False), ("Nein", False), ("aus", False), ("FALSE", False),
                              ("No, thanks", False), ("yes", True), ("On", True), ("skipped", True),
                              ("", True), ("nothing said", True)):
            with self.subTest(value=value):
                self.write("thesis/profile.md", PROFILE.replace("AI log: on", "AI log: " + value))
                self.write("thesis/memo.md", value + "\n")
                self.main("save", f"log '{value}'")
                log = self.root / "thesis/ai-log.md"
                self.assertEqual(log.exists() and f"| log '{value}' |" in log.read_text(encoding="utf-8"),
                                 logged)

    def test_identity_comes_from_the_profile_without_writing_git_config(self):
        self.write("thesis/memo.md", "memo\n")
        self.main("save", "wrote the memo")
        self.assertEqual(self.last_version()[1:], ["Jana Müller", "student@thesis-kit.local"])
        self.assertNotIn("user", self.read(".git/config"))

    def test_pdfs_in_papers_stop_being_saved(self):
        self.write("thesis/papers/a.pdf", "%PDF-1.4")
        self.git("add", "-f", "thesis/papers/a.pdf")
        self.git("-c", "user.name=Old", "-c", "user.email=o@example.org", "commit", "-q", "-m", "old setup")
        self.main("save", "--own-edits")
        self.assertEqual(self.git("ls-files", "thesis/papers"), "")
        self.assertEqual(self.git("ls-tree", "-r", "--name-only", "HEAD", "thesis/papers"), "")
        self.assertTrue((self.root / "thesis/papers/a.pdf").exists())

    def test_failed_backup_push_is_reported(self):
        self.write("thesis/profile.md", PROFILE.replace("Online backup: no",
                                                        "Online backup: yes · https://example.org/x"))
        self.git("remote", "add", "backup", str(self.root / "no-such-repository"))
        code, out = self.main("save", "set up the online backup")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "saved: set up the online backup")
        self.assertIn("online backup failed: all saved versions are only on this computer (", out)

    def test_rejected_backup_push_gives_the_reason(self):
        self.write("thesis/profile.md", PROFILE.replace("Online backup: no",
                                                        "Online backup: yes · https://example.org/x"))
        self.git("init", "-q", "--bare", "backup.git")
        self.git("remote", "add", "backup", str(self.root / "backup.git"))
        self.write("thesis/memo.md", "memo\n")
        self.assertNotIn("online backup failed", self.main("save", "wrote the memo")[1])
        # the backup got a version from another computer
        self.git("clone", "-q", "-b", "main", "backup.git", "other")
        (self.root / "other/thesis/memo.md").write_text("other memo\n", encoding="utf-8")
        for args in (["-c", "user.name=O", "-c", "user.email=o@example.org", "commit", "-qam", "x"],
                     ["push", "-q", "origin", "main"]):
            subprocess.run(["git", *args], cwd=self.root / "other", check=True, capture_output=True)
        self.write("thesis/memo.md", "memo 2\n")
        out = self.main("save", "rewrote the memo")[1]
        self.assertIn("online backup failed: 1 saved version is only on this computer "
                      "(! [rejected] HEAD -> main", out)

    def test_warns_when_origin_can_receive_uploads(self):
        self.git("remote", "add", "origin", "https://github.com/CTRLMANu/thesis-kit.git")
        self.write("thesis/memo.md", "memo\n")
        out = self.main("save", "wrote the memo")[1]
        self.assertEqual(out.splitlines()[0], "saved: wrote the memo")
        self.assertIn("warning: the public kit (origin)", out)
        self.git("remote", "set-url", "--push", "origin", "DISABLED")
        self.write("thesis/memo.md", "memo 2\n")
        self.assertNotIn("warning", self.main("save", "rewrote the memo")[1])

    def test_problems_in_the_change_are_listed(self):
        self.write("thesis/sources.md", SOURCES)
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nHeat [@lund2020].\n")
        out = self.main("save", "drafted 1")[1]
        self.assertIn("Problems in this change (fix them, then save again):\n"
                      "  thesis/chapters/01-intro.md:3: cites [@lund2020], which is unchecked\n", out)
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nHeat (Lund, 2020).\n")
        out = self.main("save", "--own-edits")[1]
        self.assertIn("In the student's own edits (tell them; change nothing):\n"
                      "  thesis/chapters/01-intro.md:3: looks like a citation typed by hand", out)
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nHeat (Lund, 2020).\n\nGermany (2020).\n")
        out = self.main("save", "drafted more")[1]
        self.assertNotIn("Problems", out)
        self.assertIn("Maybe citations typed by hand (cite the real ones with their source's key; "
                      "leave the rest):\n  thesis/chapters/01-intro.md:5: looks like a citation typed "
                      "by hand: Germany (2020)", out)

    def test_problems_saved_before_are_not_blamed_on_the_change(self):
        self.write("thesis/sources.md", SOURCES)
        student = "# 2 Theory\n\n## 2.1 Basics\n\nHeat (Lund, 2020) and [@lund2020].\n"
        self.write("thesis/chapters/02-theory.md", student)
        self.assertIn("In the student's own edits", self.main("save", "--own-edits")[1])
        self.write("thesis/chapters/02-theory.md", student + "\n## 2.2 Models\n\nModels [CHECK: x].\n")
        self.assertNotIn("thesis/chapters", self.main("save", "drafted 2.2")[1])
        self.write("thesis/chapters/02-theory.md",
                   "# 2 Theory\n\n## 2.0 Aim\n\nAim [@lund2020].\n\n" + student[len("# 2 Theory\n\n"):])
        out = self.main("save", "drafted 2.0")[1]
        self.assertIn("Problems in this change (fix them, then save again):\n"
                      "  thesis/chapters/02-theory.md:5: cites [@lund2020], which is unchecked\n", out)
        self.assertEqual(out.count("thesis/chapters"), 1)

    def test_a_half_done_undo_is_not_saved(self):
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nFirst text.\n")
        self.main("save", "--own-edits")
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nAI text.\n")
        self.main("save", "drafted 1")
        drafted = self.git("rev-parse", "HEAD").strip()
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nStudent text.\n")
        self.main("save", "--own-edits")
        head = self.git("rev-parse", "HEAD")
        undo = subprocess.run(["git", "revert", "--no-commit", drafted], cwd=self.root, capture_output=True)
        self.assertNotEqual(undo.returncode, 0)         # the chapter conflicts
        for argv in (["save", "undid: drafted 1"], ["save", "--own-edits"]):
            code, out = self.main(*argv)
            self.assertEqual(code, 1)
            self.assertTrue(out.startswith("NOT SAVED: an undo is half done"), out)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)

    def test_a_log_row_added_by_hand_is_not_doubled(self):
        self.write("thesis/ai-log.md", self.read("kit/templates/ai-log.md")
                   + "| 2026-09-27 | drafted 2.2 from three sources | chapters/02-lit.md | – |\n")
        self.write("thesis/chapters/02-lit.md", "# 2 Literature\n\n## 2.2 Cities\n\nText.\n")
        code, out = self.main("save", "drafted 2.2")
        self.assertEqual(out.splitlines()[:2], ["saved: drafted 2.2",
                                                "the AI log already has a new row, so save added none"])
        rows = [line for line in self.read("thesis/ai-log.md").splitlines() if line.startswith("| 2026")]
        self.assertEqual(len(rows), 1)
        self.write("thesis/chapters/02-lit.md", "# 2 Literature\n\n## 2.2 Cities\n\nMore text.\n")
        self.main("save", "revised 2.2")
        self.assertTrue(self.read("thesis/ai-log.md").endswith(
            f"| {TODAY} | revised 2.2 | chapters/02-lit.md | – |\n"))

    def test_not_a_git_repository(self):
        shutil.rmtree(self.root / ".git")
        code, out = self.main("save", "drafted 1")
        self.assertEqual(code, 1)
        self.assertEqual(out, "NOT SAVED: saved versions are not set up "
                              "(see kit/workflows/setup.md step 5)\n")


# --------------------------------------------------------------------------
# lint
# --------------------------------------------------------------------------

class Lint(Workspace):

    def lint(self, name, text):
        return sum(thesis.lint(self.root, [self.write(name, text)]), [])

    def test_citations_must_be_checked_sources(self):
        self.write("thesis/sources.md", SOURCES)
        problems = self.lint("thesis/chapters/01-intro.md", (
            "<!-- master: kit -->\n# 1 Intro\n\n"
            "As shown [@jumper2021, p. 7; @lund2020] and by @nobody2020, not @olsen2019.\n"
            "Mail jana@uni.de, follow @elonmusk, or see [-@jumper2021].\n"
            "<!-- [@ghost2020] is only in a comment -->\n"))
        self.assertEqual(problems, [
            "thesis/chapters/01-intro.md:4: cites [@lund2020], which is unchecked",
            "thesis/chapters/01-intro.md:4: cites [@nobody2020], which is not in sources.md",
            "thesis/chapters/01-intro.md:4: cites [@olsen2019], which is dropped",
        ])

    def test_only_kit_chapters_and_drafts_are_checked(self):
        text = "# 1 Intro\n\nHeat [@nobody2020].\n"
        self.assertEqual(len(self.lint("thesis/drafts/1.1-heat.md", text)), 1)
        self.assertEqual(self.lint("thesis/chapters/02-word.md",
                                   "<!-- master: word · thesis/word/t.docx · synced 2026-09-01 -->\n"
                                   + text), [])
        self.assertEqual(self.lint("thesis/memo.md", text), [])

    def test_hand_typed_citations(self):
        problems = self.lint("thesis/drafts/2.1-heat.md", (
            "Cities heat up (Müller, 2021). Others (see Berg et al., 2019a; Lund & Olsen,\n"
            "2018, p. 7) agree. Müller (2021) says so [12] and [3, 5–7].\n"
            "A survey (June 2021), Germany (2020–2022), [CHECK: is Müller (2021) right?] and [@a2020, p. 7] are fine.\n"
            "So are [a link](https://example.org) and footnotes[^1].\n"))
        problems = [p for p in problems if "typed by hand" in p]
        found = [p.split(": looks like a citation typed by hand: ")[1].split("; cite")[0]
                 for p in problems]
        self.assertEqual(found, ["(Müller, 2021)", "(see Berg et al., 2019a; Lund & Olsen, 2018, p. 7)",
                                 "Müller (2021)", "[12]", "[3, 5–7]"])
        self.assertTrue(problems[1].startswith("thesis/drafts/2.1-heat.md:1: "))
        self.assertTrue(problems[2].startswith("thesis/drafts/2.1-heat.md:2: "))

    def test_prose_code_and_math_are_no_hand_typed_citations(self):
        self.assertEqual(self.lint("thesis/drafts/2.1-heat.md", (
            "Die Pandemie (2020) und das Grundgesetz (1949); im Mai (2022), Jänner (2021).\n"
            "Die Zahlen (Stand: Mai 2023) liegen in $x \\in [0, 1]$, `data[1]` und <https://x.org/[2]>.\n"
            "```python\nfirst = values[0]  # Müller (2021) @lund2020\n```\n")), [])

    def test_citation_keys_typed_wrong(self):
        self.write("thesis/sources.md", SOURCES)
        problems = self.lint("thesis/drafts/2.1-heat.md", (
            "As [@Jumper2021] and [@jumper-2021] and [see @müller2021; @jumper2021, p. 7].\n"
            "Fine: [jana@uni.de], [CHECK: ask @supervisor], \\[@x], [@jumper2021] and [@me](https://x.org).\n"))
        self.assertEqual([p.split(": ", 1)[1].split(" is not")[0] for p in problems],
                         ["@Jumper2021", "@jumper-2021", "@müller2021"])
        self.assertTrue(problems[0].startswith("thesis/drafts/2.1-heat.md:1: @Jumper2021 is not a Cite as "
                                               "key (keys are lower-case letters and a year"))

    def test_a_chapter_starts_with_a_level_1_heading(self):
        self.assertEqual(self.lint("thesis/chapters/02-review.md",
                                   "<!-- master: kit -->\n## 2 Review\n\n### 2.1 Heat\n\nText.\n"),
                         ["thesis/chapters/02-review.md:2: a chapter's first heading takes one # "
                          "(# 2 Literature review), or Word won't show it as a chapter"])
        self.assertEqual(self.lint("thesis/chapters/02-review.md",
                                   "```\n## code\n```\n# 2 Review\n\n## 2.1 Heat\n"), [])
        self.assertEqual(self.lint("thesis/drafts/2.1-heat.md", "## 2.1 Heat\n\nText.\n"), [])
        self.assertEqual(self.lint("thesis/chapters/00-front-matter.md", "## Abstract\n"), [])
        path = self.write("thesis/chapters/03-method.md", "## 3 Method\n\nText.\n")
        self.assertEqual(thesis.lint(self.root, [path], {"thesis/chapters/03-method.md": {3}}), ([], []))

    def test_a_missing_key_is_made_from_the_first_author(self):
        self.assertEqual(self.lint("thesis/sources.md", (
            "# My sources\n\n### Flick und Kardorff (2019) · Qualitative Forschung\n"
            "- Status: unchecked\n- Registry check: no-doi · 2026-09-01\n")),
            ['thesis/sources.md:3: Flick und Kardorff (2019): no Cite as key; '
             'add the line "- Cite as: [@flick2019]"'])

    def test_sources_structure(self):
        problems = self.lint("thesis/sources.md", """# My sources

### Keine (2020) · No key
- Status: checked
- In my own words:

### Dup (2020) · First
- Cite as: [@dup2020]
- Status: maybe
- DOI: 10.1/x
- Registry check: ok · 2026-09-01

### Dup (2020) · Second
- Cite as: [@dup2020]
- Status: checked · 2026-09-02
- DOI: 10.1/X
- Registry check: retracted · 2026-09-01
- In my own words: something
""")
        self.assertEqual(problems, [
            "thesis/sources.md:3: Keine (2020): no Cite as key; add the line \"- Cite as: [@keine2020]\"",
            "thesis/sources.md:3: Keine (2020): checked without a date (checked · YYYY-MM-DD)",
            "thesis/sources.md:3: Keine (2020): no Registry check line",
            "thesis/sources.md:3: Keine (2020): checked, but In my own words is empty",
            "thesis/sources.md:7: Dup (2020): Status must be unchecked, checked · date, "
            "or dropped · date · reason",
            "thesis/sources.md:13: Dup (2020): Cite as [@dup2020] is also used on line 7",
            "thesis/sources.md:13: Dup (2020): DOI 10.1/x is also on line 7",
            "thesis/sources.md:13: Dup (2020): checked, but the registry lists it as retracted",
        ])
        self.assertEqual(self.lint("thesis/sources.md", SOURCES), [])


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

class Styles(Workspace):

    def test_citation_style_names(self):
        cases = {
            "APA 7": ("apa", ""), "Harvard": ("harvard-cite-them-right", ""),
            "MLA": ("modern-language-association", ""), "IEEE": ("ieee", ""),
            "Vancouver": ("vancouver", ""), "Chicago with footnotes": ("chicago-note-bibliography", ""),
            "Chicago (Fußnoten)": ("chicago-note-bibliography", ""),
            "DIN 1505": ("iso690-author-date-de", ""), "ISO 690": ("iso690-author-date-de", ""),
            "iso690-numeric-de": ("iso690-numeric-de", ""),
        }
        for value, expected in cases.items():
            self.assertEqual(thesis.csl_style(value), expected, value)
        self.assertEqual(thesis.csl_style("Chicago")[0], "chicago-author-date")
        self.assertIn("Chicago with footnotes", thesis.csl_style("Chicago")[1])
        self.assertEqual(thesis.csl_style("Hausstil"),
                         ("apa", "citation style 'Hausstil' is not one the kit knows; used APA"))
        self.assertEqual(thesis.csl_style(""), ("apa", "no citation style in profile.md; used APA"))

    def test_style_is_downloaded_once(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = csl_style("author-date").encode()
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            path = thesis.style_file(self.root, "apa")
            self.assertEqual(thesis.style_file(self.root, "apa"), path)
        self.assertEqual(path, self.root / ".tools" / "styles" / "apa.csl")
        self.assertEqual(urlopen.call_count, 1)
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://www.zotero.org/styles/apa")
        self.assertIs(urlopen.call_args[1]["context"], thesis.SSL_CONTEXT)
        self.assertIn('citation-format="author-date"', path.read_text(encoding="utf-8"))

    def test_pandoc_is_found_in_the_workspace_tools(self):
        fake = self.write(".tools/pandoc/bin/pandoc", "#!/bin/sh\n")
        fake.chmod(0o755)
        with patch.dict(os.environ, {"PATH": str(self.root / "empty")}):
            self.assertEqual(thesis.find_pandoc(self.root), str(fake))


class WordText(unittest.TestCase):

    def test_markers_become_comments_and_other_at_words_are_escaped(self):
        marker = "<!-- AI draft 2026-09-25 · rewrite in your own words, then delete this line -->"
        ids = iter(range(1, 10))
        text = thesis.word_text(f"<!-- master: kit -->\n{marker}\nOpening words.\n\n"
                                f"## 2.1 Heat {{#heat}}\n\n{marker}\nAs @jumper2021 and @elonmusk said.\n",
                                ids)
        comment = ('[AI draft 2026-09-25 · rewrite in your own words, then delete this comment]'
                   '{{.comment-start id="{0}" author="thesis-kit" date="2026-09-25T00:00:00Z"}}'
                   '[]{{.comment-end id="{0}"}}')
        self.assertEqual(text, f"{comment.format(1)}Opening words.\n\n"
                               f"## 2.1 Heat{comment.format(2)} {{#heat}}\n\n"
                               "As @jumper2021 and \\@elonmusk said.\n")

    def test_at_words_in_code_and_links_stay_as_written(self):
        text = ("```java\n@Override\n```\nUse `@property`, see <https://medium.com/@user/post>, ask @Someone.\n"
                "```\nunclosed @x\n")
        self.assertEqual(thesis.word_text(text, iter(range(1, 9))),
                         text.replace("@Someone", "\\@Someone").replace("@x", "\\@x"))


class CleanCsl(unittest.TestCase):

    def title(self, title, subtitle):
        return thesis.clean_csl({"title": [title], "subtitle": subtitle}, "k")["title"]

    def test_the_subtitle_belongs_to_the_title(self):
        self.assertEqual(self.title("The Pen Is Mightier Than the Keyboard",
                                    ["Advantages of Longhand Over Laptop Note Taking."]),
                         "The Pen Is Mightier Than the Keyboard: Advantages of Longhand Over Laptop Note Taking")
        self.assertEqual(self.title("Does it matter?", ["Evidence from cities"]),
                         "Does it matter? Evidence from cities")
        self.assertEqual(self.title("Heat: A study of cities", ["a study of cities"]), "Heat: A study of cities")
        self.assertEqual(self.title("Heat", []), "Heat")


@needs_pandoc
class Export(Workspace):

    def setUp(self):
        super().setUp()
        self.write("thesis/sources.md", SOURCES)
        self.write(".tools/styles/apa.csl", csl_style("author-date"))
        self.write(".tools/styles/ieee.csl", csl_style("numeric"))
        self.fetched = []
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(thesis, "find_pandoc", return_value=PANDOC))
        stack.enter_context(patch.object(thesis, "fetch_json", side_effect=self.fake_doi_org))
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("network")))
        self.addCleanup(stack.close)
        self.offline = self.no_record = False

    def fake_doi_org(self, url, accept=None, **kw):
        self.fetched.append((url, accept))
        if self.offline:
            raise OSError("no network")
        if self.no_record:
            raise thesis.NotFound(url)
        return JUMPER_CSL

    def docx_markdown(self, name):
        return subprocess.run([PANDOC, str(self.root / name), "-t", "markdown", "--wrap=none",
                               "--track-changes=all"], capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout

    def write_chapters(self):
        self.write("thesis/chapters/01-intro.md", (
            "<!-- master: kit -->\n# 1 Introduction\n\n"
            "<!-- AI draft 2026-09-25 · rewrite in your own words, then delete this line -->\n"
            "Proteins fold [@jumper2021]. Heat [@lund2020]. Ask @elonmusk. Old (Smith, 2019).\n"
            "[CHECK: a source for this]\n"))
        self.write("thesis/chapters/02-method.md", "# 2 Method\n\nAs @jumper2021 showed.\n")
        self.write("thesis/chapters/03-results.md",
                   "<!-- master: word · thesis/word/t.docx · synced 2026-09-01 -->\n# 3 Results\n")

    def test_export_writes_a_new_word_file(self):
        self.write_chapters()
        code, out = self.main("export")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], f"exported: thesis/export/thesis-{TODAY}.docx")
        self.assertIn("style: apa\n", out)
        self.assertIn("1 [CHECK] markers, 1 AI-draft sections", out)
        self.assertIn("  thesis/chapters/01-intro.md:5: cites [@lund2020], which is unchecked", out)
        self.assertIn("looks like a citation typed by hand: (Smith, 2019)", out)
        self.assertEqual(self.fetched, [("https://doi.org/10.1038/s41586-021-03819-2",
                                         "application/vnd.citationstyles.csl+json")])
        records = json.loads(self.read("thesis/references.json"))
        self.assertEqual(records, [{
            "id": "jumper2021", "type": "article-journal",
            "title": "Highly accurate protein structure prediction with AlphaFold",
            "container-title": "Nature", "page": "583-589", "volume": "596",
            "DOI": "10.1038/s41586-021-03819-2",
            "author": [{"family": "Jumper", "given": "John"}],
            "issued": {"date-parts": [[2021, 8, 26]]}}])
        text = self.docx_markdown(f"thesis/export/thesis-{TODAY}.docx")
        heading = next(line for line in text.splitlines() if line.startswith("# 1 Introduction"))
        self.assertIn('[AI draft 2026-09-25 · rewrite in your own words, then delete this comment]'
                      '{.comment-start id="1" author="thesis-kit" date="2026-09-25T00:00:00Z"}', heading)
        self.assertIn("(Jumper, 2021)", text)
        self.assertIn("**lund2020?**", text)
        self.assertIn("\\@elonmusk", text)
        self.assertNotIn("3 Results", text)
        self.assertIn("# References", text)
        self.assertIn("John Jumper (2021). [Highly accurate protein structure prediction with AlphaFold]",
                      text)

    def test_records_are_cached_and_files_never_overwritten(self):
        self.write_chapters()
        self.main("export")
        self.offline = True
        self.fetched.clear()
        code, out = self.main("export")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], f"exported: thesis/export/thesis-{TODAY}-2.docx")
        self.assertEqual(self.fetched, [])
        self.assertTrue((self.root / f"thesis/export/thesis-{TODAY}.docx").exists())

    def test_offline_without_cached_records_exports_nothing(self):
        self.write_chapters()
        self.offline = True
        code, out = self.main("export")
        self.assertEqual((code, out), (1, "could not reach doi.org for jumper2021; nothing exported\n"))
        self.assertFalse((self.root / "thesis/export").exists())

    def test_sources_without_doi_need_a_record_typed_in_once(self):
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nCities [@bergnd].\n")
        code, out = self.main("export")
        self.assertEqual(code, 1)
        self.assertIn("from the entry's Reference as given line or the first page of its PDF "
                      "(not from memory)", out)
        self.assertNotIn("PDF: take the rest", out)
        skeleton = json.loads(out[out.index("{"):out.index("\nReference as given")])
        self.assertEqual(skeleton, {"id": "bergnd", "type": "book", "title": "Stadtklima",
                                    "author": [{"family": "Berg", "given": ""}],
                                    "publisher": "Springer Verlag"})
        self.assertIn("Reference as given: Berg, K. (o. J.). Stadtklima. Springer Verlag.", out)
        self.assertFalse((self.root / "thesis/export").exists())

        skeleton["author"][0]["given"] = "Karl"
        self.write("thesis/references.json", json.dumps([skeleton]))
        code, out = self.main("export")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], f"exported: thesis/export/01-intro-{TODAY}.docx")
        self.assertIn("Typed from your sources list; check these against the book or page:\n"
                      "  Karl Berg Stadtklima\n", out)

    def test_a_doi_without_a_record_at_doi_org_needs_one_typed_in(self):
        self.write("thesis/sources.md", SOURCES.replace(
            "- Found via: Consensus\n", "- Found via: Consensus\n- PDF: papers/jumper.pdf\n"))
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nProteins [@jumper2021].\n")
        self.no_record = True
        code, out = self.main("export")
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[0], "doi.org has no record for the DOI of jumper2021: "
                                              "check the DOI in thesis/sources.md, or type in the record below.")
        self.assertNotIn("could not reach", out)
        record = json.loads(out[out.index("{"):out.index("\nReference as given")])
        self.assertEqual((record["id"], record["title"]), ("jumper2021", "Highly accurate protein "
                                                            "structure prediction with AlphaFold"))
        self.assertIn('PDF: take the rest from its first page: '
                      'python3 kit/scripts/sources.py pdf "thesis/papers/jumper.pdf" --pages 1', out)
        self.assertFalse((self.root / "thesis/export").exists())

        record["author"][0]["given"] = "John"
        self.write("thesis/references.json", json.dumps([record]))
        self.fetched.clear()
        code, out = self.main("export")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.fetched, [])
        self.assertIn("Typed from your sources list; check these against the book or page:\n"
                      "  John Jumper (2021). Highly accurate", out)

    def test_broken_references_json_is_reported(self):
        self.write("thesis/chapters/01-intro.md", "# 1 Intro\n\nCities [@bergnd].\n")
        self.write("thesis/references.json", json.dumps([{"id": "bergnd", "type": "book",
                                                           "author": "Berg"}]))
        code, out = self.main("export")
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines(), [
            'thesis/references.json: record bergnd: needs "title"',
            'thesis/references.json: record bergnd: "author" must look like '
            '[{"family": "Müller", "given": "Jana"}]'])

    def test_numeric_style_shows_drafts_author_year(self):
        self.write("thesis/profile.md", PROFILE.replace("APA 7", "IEEE"))
        self.write("thesis/drafts/2.1-heat.md", "## 2.1 Heat\n\nProteins [@jumper2021].\n")
        code, out = self.main("export", "thesis/drafts/2.1-heat.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.splitlines()[0], f"exported: thesis/export/2.1-heat-{TODAY}.docx")
        self.assertIn("style: apa\n  note: shown author-year; number them in your Word file", out)

    def test_numeric_style_warns_for_some_chapters(self):
        self.write("thesis/profile.md", PROFILE.replace("APA 7", "IEEE"))
        self.write_chapters()
        out = self.main("export", "thesis/chapters/02-method.md")[1]
        self.assertIn("style: ieee\n  note: numbers start at [1] in this file", out)
        out = self.main("export")[1]                   # 03-results.md lives in Word
        self.assertIn("style: ieee\n  note: numbers start at [1] in this file", out)
        (self.root / "thesis/chapters/03-results.md").unlink()
        self.assertNotIn("numbers start", self.main("export")[1])

    def test_word_master_file_is_skipped(self):
        self.write_chapters()
        code, out = self.main("export", "thesis/chapters/03-results.md")
        self.assertEqual(code, 1)
        self.assertIn("skipped thesis/chapters/03-results.md: it lives in the Word file", out)


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------

WORD_FILE = """Front text of the thesis.

# 1 Introduction[AI draft 2026-09-01 · rewrite in your own words, then delete this comment]{.comment-start id="1" author="thesis-kit" date="2026-09-01T00:00:00Z"}[]{.comment-end id="1"}

Intro text with [new words]{.insertion author="Prof. Weber" date="2026-09-20T00:00:00Z"} and \\[CHECK: a source\\].

## 1.1 Background

A [Needs a source]{.comment-start id="2" author="Prof. Weber" date="2026-09-21T10:00:00Z"}bold claim[]{.comment-end id="2"} here.

# 2 Literature review

Review text from Word[ as given]{.deletion author="Prof. Weber" date="2026-09-20T00:00:00Z"}.

# References

Jumper, J. (2021). Highly accurate.
"""


class SplitChapters(unittest.TestCase):

    def test_word_anchors_and_heading_attributes_are_dropped(self):
        front, chapters = thesis.split_chapters(
            "Title page\n\n# []{#_Toc1 .anchor}1 Introduction {#introduction}\n\nText []{#_Ref2 .anchor}here.\n\n"
            "## 1.1 Aim {.unnumbered}\n\n# 2. Method\n")
        self.assertEqual(front, "Title page")
        self.assertEqual(chapters, ["# 1 Introduction\n\nText here.\n\n## 1.1 Aim", "# 2. Method"])
        self.assertEqual(thesis.heading_parts(chapters[1].split("\n")[0]), (2, "Method"))
        self.assertIsNone(thesis.split_chapters("No headings\n\n## Only level two\n"))


class PickDocx(Workspace):

    def pick(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            path = thesis.pick_docx(self.root, None)
        return path, out.getvalue()

    def test_which_word_file(self):
        self.write("thesis/export/thesis-2026-09-01.docx", "")
        self.assertEqual(self.pick(), (None, (
            "no Word file in thesis/word/\nto keep working on an exported file, save it into "
            "thesis/word/ (in thesis/export/: thesis-2026-09-01.docx)\n")))
        self.write("thesis/word/template.docx", "")
        self.write("thesis/word/~$thesis.docx", "")
        self.write("thesis/word/thesis.docx", "")
        self.assertEqual(self.pick(), (self.root / "thesis/word/thesis.docx", ""))
        self.write("thesis/word/copy.docx", "")
        self.assertEqual(self.pick(), (None, "several Word files in thesis/word/ (ask which one the "
                                             "student works in): copy.docx, thesis.docx\n"))
        self.write("thesis/chapters/01-intro.md",
                   "<!-- master: word · thesis/word/thesis.docx · synced 2026-09-01 -->\n# 1 Intro\n")
        os.utime(self.root / "thesis/word/copy.docx", (0, 0))
        self.assertEqual(self.pick(), (self.root / "thesis/word/thesis.docx", ""))
        # saved under a new name after the last sync (File > Save As)
        self.write("thesis/word/thesis-v2.docx", "")
        os.utime(self.root / "thesis/word/thesis.docx", (1, 1))
        self.assertEqual(self.pick(), (None, "several Word files in thesis/word/ (ask which one the "
                                             "student works in): thesis/word/thesis.docx, read last "
                                             "time; newer: thesis-v2.docx\n"))


@needs_pandoc
class Sync(Workspace):

    def setUp(self):
        super().setUp()
        patcher = patch.object(thesis, "find_pandoc", return_value=PANDOC)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_docx(self, markdown, name="thesis/word/thesis.docx"):
        (self.root / name).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([PANDOC, "-f", "markdown", "-o", str(self.root / name)], input=markdown,
                       capture_output=True, text=True, encoding="utf-8", check=True)

    def test_sync_mirrors_word_chapters_and_collects_comments(self):
        self.make_docx(WORD_FILE)
        kit_chapter = "<!-- master: kit -->\n# 2 Literature review\n\nKit text.\n"
        self.write("thesis/chapters/02-literature-review.md", kit_chapter)
        code, out = self.main("sync")
        self.assertEqual(code, 0, out)
        master = f"<!-- master: word · thesis/word/thesis.docx · synced {TODAY} -->"
        self.assertEqual(self.read("thesis/chapters/00-front-matter.md"),
                         master + "\nFront text of the thesis.\n")
        intro = self.read("thesis/chapters/01-introduction.md")
        self.assertTrue(intro.startswith(master + "\n# 1 Introduction\n"))
        self.assertIn("Intro text with new words and \\[CHECK: a source\\].", intro)
        self.assertNotIn("comment", intro)
        self.assertTrue(self.read("thesis/chapters/99-references.md").startswith(master + "\n# References"))
        self.assertEqual(self.read("thesis/chapters/02-literature-review.md"), kit_chapter)
        self.assertEqual(out.splitlines(), [
            "Word file: thesis/word/thesis.docx",
            "Text before the first heading → thesis/chapters/00-front-matter.md: new",
            '"1 Introduction" → thesis/chapters/01-introduction.md: new',
            '"2 Literature review" → thesis/chapters/02-literature-review.md: still written in the kit, '
            "not changed (Word text differs)",
            '"References" (the reference list made by the export) → thesis/chapters/99-references.md: new',
            "Comments: Prof. Weber 1 (in thesis/feedback/word-comments.md)",
            "Tracked changes not yet accepted: Prof. Weber: 1 insertion, 1 deletion",
            "AI-draft comments still in Word: 1 Introduction",
            "[CHECK] markers: thesis/chapters/01-introduction.md 1",
        ])
        self.assertEqual(self.read("thesis/feedback/word-comments.md"), (
            f"# Comments in thesis.docx · synced {TODAY}\n\n"
            "## 1 Introduction\n\n"
            '- Prof. Weber (2026-09-20): inserted "new words" after "Intro text with"\n\n'
            "## 1 Introduction › 1.1 Background\n\n"
            '- Prof. Weber (2026-09-21): Needs a source — on "bold claim"\n\n'
            "## 2 Literature review\n\n"
            '- Prof. Weber (2026-09-20): deleted "as given" after "Review text from Word"\n\n'
            "Tracked changes not yet accepted: Prof. Weber: 1 insertion, 1 deletion.\n"))

        code, out = self.main("sync", "--move", "2")
        self.assertIn('"1 Introduction" → thesis/chapters/01-introduction.md: no change', out)
        self.assertIn('"2 Literature review" → thesis/chapters/02-literature-review.md: moved to Word', out)
        self.assertEqual(self.read("thesis/chapters/02-literature-review.md"),
                         master + "\n# 2 Literature review\n\nReview text from Word.\n")

    def test_matching_existing_chapters_by_heading(self):
        self.make_docx("# 1 Einleitung und Ziele\n\nText.\n\n# Methode\n\nMehr.\n")
        self.write("thesis/chapters/01-intro.md", "<!-- master: word · x · synced 2026-09-01 -->\n"
                                                  "# 1 Einleitung und Ziel\n\nAlt.\n")
        self.write("thesis/chapters/05-methods.md", "<!-- master: word · x · synced 2026-09-01 -->\n"
                                                    "# 5 Methode\n\nAlt.\n")
        out = self.main("sync")[1]
        self.assertIn('"1 Einleitung und Ziele" → thesis/chapters/01-intro.md: updated', out)
        self.assertIn('"Methode" → thesis/chapters/05-methods.md: updated', out)
        self.assertEqual(sorted(p.name for p in (self.root / "thesis/chapters").iterdir()),
                         ["01-intro.md", "05-methods.md"])

    def test_footnotes_stay_in_their_chapter(self):
        self.make_docx("# 1 Intro\n\nText.[^1]\n\n[^1]: A footnote.\n\n# References\n\nList.\n")
        self.main("sync")
        self.assertIn("[^1]: A footnote.", self.read("thesis/chapters/01-intro.md"))
        self.assertNotIn("[^1]", self.read("thesis/chapters/99-references.md"))

    def test_move_takes_the_number_in_the_word_heading(self):
        for name, heading in (("01-einleitung", "1 Einleitung"), ("02-methode", "2 Methode"),
                              ("03-ergebnisse", "3 Ergebnisse")):
            self.write(f"thesis/chapters/{name}.md", f"<!-- master: kit -->\n# {heading}\n\nKit text.\n")
        self.make_docx("# 1 Einleitung\n\nA.\n\n# 2 Stand der Forschung\n\nB.\n\n# 3 Methode\n\nC.\n\n"
                       "# 4 Ergebnisse\n\nD.\n")
        out = self.main("sync", "--move", "3", "9")[1]
        self.assertIn('"3 Methode" → thesis/chapters/02-methode.md: moved to Word', out)
        self.assertIn('"4 Ergebnisse" → thesis/chapters/03-ergebnisse.md: still written in the kit', out)
        self.assertIn("no chapter matches --move 9\n", out)
        self.assertNotIn("--move 3", out)
        self.assertEqual(self.read("thesis/chapters/03-ergebnisse.md"),
                         "<!-- master: kit -->\n# 3 Ergebnisse\n\nKit text.\n")

    def test_an_unchanged_export_reads_as_the_same_text(self):
        self.write("thesis/sources.md", SOURCES)
        self.write(".tools/styles/apa.csl", csl_style("author-date"))
        self.write("thesis/references.json", json.dumps([thesis.clean_csl(JUMPER_CSL, "jumper2021")]))
        chapter = ("<!-- master: kit -->\n# 1 Introduction {#intro}\n\n"
                   "<!-- AI draft 2026-09-25 · rewrite in your own words, then delete this line -->\n"
                   "Proteins fold [@jumper2021, p. 5]. It's \"new\" -- ask @elonmusk. [CHECK: a source]\n")
        self.write("thesis/chapters/01-intro.md", chapter)
        self.assertEqual(self.main("export")[0], 0)
        (self.root / "thesis/word").mkdir()
        shutil.copy(self.root / f"thesis/export/01-intro-{TODAY}.docx", self.root / "thesis/word/thesis.docx")
        same = ('"1 Introduction" → thesis/chapters/01-intro.md: still written in the kit, not changed '
                "(Word text same)")
        self.assertIn(same, self.main("sync")[1])
        # A broken record no chapter cites stops export, not the comparison.
        self.write("thesis/references.json", json.dumps(
            [thesis.clean_csl(JUMPER_CSL, "jumper2021"), {"id": "unused2020", "type": "book"}, 7]))
        self.assertIn(same, self.main("sync")[1])
        self.assertEqual(self.main("export")[0], 1)
        self.write("thesis/chapters/01-intro.md", chapter.replace("Proteins fold", "Proteins change"))
        self.assertIn(same.replace("same", "differs"), self.main("sync")[1])

    def test_heading_attributes_do_not_hide_a_kit_chapter(self):
        self.make_docx("# 2 Methode\n\nText.\n")
        self.write("thesis/chapters/02-methode.md", "<!-- master: kit -->\n# 2 Methode {#sec:methode}\n\nText.\n")
        self.assertIn('"2 Methode" → thesis/chapters/02-methode.md: still written in the kit, not changed '
                      "(Word text same)", self.main("sync")[1])
        self.assertEqual([p.name for p in (self.root / "thesis/chapters").iterdir()], ["02-methode.md"])

    def test_mirrors_of_chapters_gone_from_the_word_file_are_removed(self):
        self.write("thesis/chapters/05-kit.md", "# 5 Written in the kit\n\nKit.\n")
        self.write("thesis/chapters/07-other.md",
                   "<!-- master: word · thesis/word/other.docx · synced 2026-09-01 -->\n# 7 Other\n")
        self.make_docx("# 1 Einleitung\n\nA.\n\n# 2 Methode\n\nB.\n")
        self.main("sync")
        self.make_docx("# 1 Einleitung\n\nA.\n\n# 2 Forschungsdesign und Methode\n\nB.\n")
        out = self.main("sync")[1]
        self.assertIn("thesis/chapters/02-methode.md: removed, no longer in the Word file", out)
        self.assertEqual(sorted(p.name for p in (self.root / "thesis/chapters").iterdir()),
                         ["01-einleitung.md", "02-forschungsdesign-und-methode.md", "05-kit.md", "07-other.md"])

    def test_word_file_without_heading_1_is_refused(self):
        self.make_docx("Just text.\n\n## Only a level-two heading\n\nMore.\n")
        code, out = self.main("sync")
        self.assertEqual((code, out), (1, "the Word file uses no Heading 1 styles, so chapters "
                                          "can't be told apart\n"))
        self.assertFalse((self.root / "thesis/chapters").exists())
        self.assertFalse((self.root / "thesis/feedback").exists())


if __name__ == "__main__":
    unittest.main()
