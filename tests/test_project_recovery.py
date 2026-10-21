"""No-model tests of bounded recovery and its compiled handoff/planner integration."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "universal-project-governance"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / "scripts" / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


FACTS = module("recovery_facts_test", "project_facts.py")
STATE = module("recovery_state_test", "state_tool.py")
with patch.object(sys, "path", [str(RUNTIME / "scripts")] + sys.path):
    PLAN = module("recovery_plan_test", "plan_governance.py")


class ProjectRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = ROOT / "eval-workspaces"
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="recovery-test-", dir=directory)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.imports = patch.dict(sys.modules, project_facts=FACTS, state_tool=STATE)
        self.imports.start()
        self.addCleanup(self.imports.stop)

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def recover(self, scope, **kwargs):
        return FACTS.recover(self.root, scope, **kwargs)

    def ref(self, path):
        return {"path": path, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()}

    def save(self, recovery, **extra):
        handoff = {"updated_at": "2026-10-13T00:00:00Z", "goal": "recover task facts", "status": "in_progress",
                   **{key: [] for key in ("completed", "in_progress", "decisions", "invariants", "risks", "next_actions", "validation", "canonical_sources")},
                   "recovery": recovery, **extra}
        self.write(".governance/handoff.json", json.dumps(handoff))

    def seed(self, scope):
        return self.recover(scope)["recovery"]

    def evidence(self, path="result.json", kind="static", **extra):
        return {"id": "check-1", "kind": kind, "claim": "bounded claim", "reference": self.ref(path),
                "coverage": "explicit fixture", "invalidation_conditions": ["changed inputs or config"], **extra}

    def synthetic_git(self, *, sha256=False):
        """Only this test's disposable repository receives Git configuration."""
        binary = shutil.which("git")
        if binary is None: self.skipTest("registered Git unavailable")
        environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                           GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
        prefix = [binary, "--no-optional-locks", "-c", "core.hooksPath=" + os.devnull,
                  "-c", "core.fsmonitor=false", "-c", "core.attributesFile=" + os.devnull,
                  "-c", "core.autocrlf=false", "-c", "commit.gpgSign=false",
                  "-c", "user.name=Recovery Test", "-c", "user.email=recovery@example.invalid"]
        def git(*args, input=None):
            completed = subprocess.run(prefix + list(args), cwd=self.root, env=environment, input=input,
                                       capture_output=True, timeout=10, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return completed.stdout
        git("init", "--template=", *( ["--object-format=sha256"] if sha256 else []))
        return binary, git

    def commit_git(self, git, *paths):
        git("add", "--", *paths)
        git("commit", "--no-gpg-sign", "--no-verify", "-m", "synthetic source identity")

    def test_default_is_read_only_scope_only_and_intent_unknown(self):
        self.write("main.py", "value = 1\n")
        self.write("unrelated.txt", "do not read\n")
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self.recover(["main.py"])
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result["recovery"]["scope"], ["main.py"])
        self.assertIn("prior intent remains unknown", " ".join(result["recovery"]["gaps"]))
        self.assertFalse(result["coverage"]["completion_proved"])
        self.assertFalse(result["coverage"]["project_code_executed"])
        self.assertEqual(result["canonical_state"], ".governance/handoff.json")

    def test_declarations_do_not_import_or_execute_project_code(self):
        self.write("main.py", "import missing_dependency\nfrom app.core import run\nif __name__ == '__main__':\n    open('executed', 'w').write('bad')\n")
        self.write("package.json", json.dumps({"scripts": {"start": "touch SECRET"}, "dependencies": {"lib": "*"}}))
        result = self.recover(["main.py", "package.json"])
        rows = result["recovery"]["static_observations"]
        self.assertIn("__main__ guard", [row["name"] for row in rows])
        self.assertIn("missing_dependency", [row["name"] for row in rows])
        self.assertIn("start", [row["name"] for row in rows])
        self.assertNotIn("touch SECRET", json.dumps(rows))
        self.assertFalse((self.root / "executed").exists())
        self.assertTrue(all(row["basis"] == "static-declaration-only" for row in rows))

    def test_static_parse_budget_remains_partial(self):
        self.write("main.py", "\n" * (128 * 1024 + 1))
        view = self.seed(["main.py"])
        self.assertIn("static declaration analysis partial", " ".join(view["gaps"]))
        self.assertEqual(view["semantic_completion"], "unassessed")

    def test_unsafe_explicit_scope_is_rejected(self):
        for path in ("../other", "/root", "C:/file", "a\\b", "a//b", "a/./b", "a:ads", "a.", "nul.txt", ".git/config", ".aws/config", ".env", "auth.json"):
            with self.subTest(path=path), self.assertRaises(ValueError): self.recover([path])
        with self.assertRaises(ValueError): self.recover(["x"] * 2)
        with self.assertRaises(ValueError): self.recover(["/".join(["a"] * 17)])

    @unittest.skipUnless(os.name == "nt", "Windows scope alias check")
    def test_windows_case_aliases_rejected(self):
        with self.assertRaisesRegex(ValueError, "aliases"): self.recover(["a", "A"])

    def test_hardlink_scope_rejected(self):
        original = self.write("source.txt", "body")
        try: os.link(original, self.root / "linked.txt")
        except OSError as error: self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "hardlinked"): self.recover(["linked.txt"])

    def test_symlink_scope_rejected(self):
        original = self.write("source.txt", "body")
        try: os.symlink(original, self.root / "linked.txt")
        except OSError as error: self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "symlink/reparse"): self.recover(["linked.txt"])

    def test_reparse_and_hardlink_metadata_rejected_without_creation_privilege(self):
        target = self.write("source.txt", "body")
        original = Path.lstat
        for override, message in (({"st_file_attributes": 1024}, "symlink/reparse"), ({"st_nlink": 2}, "hardlinked")):
            def lstat(path, *args, **kwargs):
                value = original(path, *args, **kwargs)
                if path == target:
                    return SimpleNamespace(st_mode=value.st_mode, st_nlink=value.st_nlink,
                                           **({"st_file_attributes": 0} if "st_file_attributes" not in override else {}),
                                           **override) if "st_nlink" not in override else SimpleNamespace(st_mode=value.st_mode, **override)
                return value
            with self.subTest(override=override), patch.object(Path, "lstat", lstat), self.assertRaisesRegex(ValueError, message):
                FACTS.safe_path(self.root, "source.txt")

    def test_changed_read_charges_actual_bytes_and_is_not_replayed(self):
        self.write("source.txt", "body")
        reader = FACTS.Reader(self.root)
        original = os.fstat
        calls = []
        def fstat(fd):
            value = original(fd)
            calls.append(fd)
            return SimpleNamespace(st_mode=value.st_mode, st_nlink=value.st_nlink, st_dev=value.st_dev,
                                   st_ino=value.st_ino, st_size=value.st_size,
                                   st_mtime_ns=value.st_mtime_ns + (1 if len(calls) == 2 else 0))
        with patch.object(FACTS.os, "fstat", fstat), self.assertRaisesRegex(ValueError, "changed"):
            reader.read("source.txt")
        self.assertEqual(reader.total_bytes, 4)
        self.assertEqual(reader.cache, {})
        with self.assertRaisesRegex(ValueError, "no automatic retry"): reader.read("source.txt")

    def test_directories_and_missing_files_do_not_count_as_observed(self):
        (self.root / "folder").mkdir()
        result = self.recover(["folder", "missing"])
        self.assertEqual([row["status"] for row in result["recovery"]["source_state"]["files"]], ["unavailable"] * 2)
        self.assertFalse(result["coverage"]["completion_proved"])

    def test_byte_and_file_budgets_leave_explicit_gaps(self):
        self.write("a.txt", "1234"); self.write("b.txt", "5678")
        with patch.object(FACTS, "MAX_TOTAL_BYTES", 6):
            result = self.recover(["a.txt", "b.txt"])
        self.assertEqual(result["coverage"]["bytes_read"], 4)
        self.assertEqual(result["recovery"]["source_state"]["files"][1]["status"], "unavailable")
        with patch.object(FACTS, "MAX_FILE_BYTES", 2):
            # Reader default argument is deliberately fixed; a per-call limit still rejects the file.
            with self.assertRaisesRegex(ValueError, "bounded read limit"): FACTS.Reader(self.root).read("a.txt", 2)
        with patch.object(FACTS, "MAX_FILES", 1):
            reader = FACTS.Reader(self.root)
            with self.assertRaises(OSError): reader.read("absent")
            with self.assertRaisesRegex(ValueError, "file read budget"): reader.read("a.txt")

    def test_unavailable_read_is_not_automatically_retried(self):
        reader = FACTS.Reader(self.root)
        with self.assertRaises(OSError): reader.read("missing")
        self.write("missing", "now exists")
        with self.assertRaisesRegex(ValueError, "no automatic retry"): reader.read("missing")

    def test_duplicate_and_nonfinite_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'[' * 10000 + b'0' + b']' * 10000):
            with self.assertRaises(ValueError): FACTS.strict_json(raw)
            path = self.write("bad.json", raw.decode("ascii"))
            with self.assertRaises(ValueError): STATE.load(path)

    def test_deep_handoff_is_unknown_not_a_cli_traceback(self):
        self.write("main.py", "pass")
        self.write("handoff.json", "[" * 10000 + "0" + "]" * 10000)
        result = self.recover(["main.py"], handoff="handoff.json")
        self.assertIn("prior intent remains unknown", " ".join(result["recovery"]["gaps"]))

    def test_missing_invalid_handoff_does_not_invent_intent(self):
        self.write("main.py", "pass\n")
        self.write(".governance/handoff.json", '{"goal":"one","goal":"two"}')
        result = self.recover(["main.py"], handoff=".governance/handoff.json")
        self.assertIn("prior intent remains unknown", " ".join(result["recovery"]["gaps"]))
        self.assertEqual(result["recovery"]["evidence"], [])

    def test_changed_and_out_of_scope_references_are_not_inherited(self):
        self.write("result.json", "{}")
        self.write("outside.txt", "outside")
        view = self.seed(["result.json"])
        view["evidence"] = [self.evidence()]
        view["evidence_checks"] = [{"id": "check-1", "fixity": "match", "validity": "eligible-for-review", "semantic_truth": "unassessed"}]
        view["carry_forward_refs"] = [self.ref("outside.txt")]
        # The source-bound invariant rejects invented standalone carried references.
        self.assertTrue(FACTS.recovery_errors(view))
        view["carry_forward_refs"] = []
        view["evidence"][0]["inputs"] = [self.ref("outside.txt")]
        view["evidence_checks"][0].update(fixity="unverified", validity="unverified")
        self.save(view)
        self.write("result.json", '{"new":true}')
        result = self.recover(["result.json"], handoff=".governance/handoff.json")
        self.assertEqual([row["status"] for row in result["recovery"]["reference_checks"]], ["changed", "out-of-scope"])
        self.assertEqual(result["recovery"]["carry_forward_refs"], [])
        self.assertTrue(result["recovery"]["decision_delta"])
        self.assertEqual(result["coverage"]["files_read"], 2)

    def test_equal_hashes_only_offer_review_not_semantic_truth(self):
        self.write("result.json", "{}")
        view = self.seed(["result.json"])
        view["evidence"] = [self.evidence()]
        view["evidence_checks"] = [{"id": "check-1", "fixity": "match", "validity": "eligible-for-review", "semantic_truth": "unassessed"}]
        view["carry_forward_refs"] = [self.ref("result.json")]
        self.save(view)
        result = self.recover(["result.json"], handoff=".governance/handoff.json")
        self.assertEqual(result["recovery"]["evidence_checks"][0]["semantic_truth"], "unassessed")
        self.assertEqual(result["recovery"]["carry_forward_refs"], [self.ref("result.json")])
        self.assertEqual(result["recovery"]["semantic_completion"], "unassessed")

    def test_dynamic_evidence_requires_all_bound_contexts_and_current_revision(self):
        for name in ("result.json", "input.json", "config.json", "environment.json"): self.write(name, "{}")
        scope = ["result.json", "input.json", "config.json", "environment.json"]
        view = self.seed(scope)
        view["evidence"] = [self.evidence(kind="dynamic", inputs=[self.ref("input.json")], configuration=[self.ref("config.json")], environment=self.ref("environment.json"), tested_revision="a" * 40)]
        view["evidence_checks"] = [{"id": "check-1", "fixity": "match", "validity": "unverified", "semantic_truth": "unassessed"}]
        self.save(view)
        git = dict(view["source_state"]["git"], available=True, revision="a" * 40, root=str(self.root), branch="main")
        with patch.object(FACTS, "git_state", return_value=(git, [])):
            result = self.recover(scope, handoff=".governance/handoff.json")
        self.assertEqual(result["recovery"]["evidence_checks"][0]["validity"], "eligible-for-review")
        self.write("input.json", '{"changed":true}')
        with patch.object(FACTS, "git_state", return_value=(git, [])):
            result = self.recover(scope, handoff=".governance/handoff.json")
        self.assertEqual(result["recovery"]["evidence_checks"][0]["validity"], "unverified")

    def test_dynamic_claim_without_context_stays_unverified(self):
        self.write("result.json", "{}")
        view = self.seed(["result.json"])
        view["evidence"] = [self.evidence(kind="dynamic")]
        view["evidence_checks"] = [{"id": "check-1", "fixity": "match", "validity": "unverified", "semantic_truth": "unassessed"}]
        self.save(view)
        result = self.recover(["result.json"], handoff=".governance/handoff.json")
        self.assertEqual(result["recovery"]["evidence_checks"][0]["validity"], "unverified")

    def test_no_progress_switch_and_contradictions_are_preserved(self):
        self.write("main.py", "pass")
        view = self.seed(["main.py"])
        view["attempts"] = [{"method": "same search", "progress": False}] * 2
        view["contradictions"] = ["declaration and claimed execution disagree"]
        view["hypotheses"] = ["unverified route"]
        self.save(view)
        result = self.recover(["main.py"], handoff=".governance/handoff.json")
        self.assertIn("Switch analysis method", " ".join(result["next_actions"]))
        self.assertEqual(result["recovery"]["contradictions"], view["contradictions"])
        self.assertEqual(result["recovery"]["hypotheses"], view["hypotheses"])

    def test_saved_identity_inconsistency_is_rejected_by_state_validation(self):
        self.write("main.py", "pass")
        view = self.seed(["main.py"])
        view["source_state"]["scope_sha256"] = "0" * 64
        self.save(view)
        self.assertTrue(STATE.validate_file(self.root / ".governance/handoff.json", "handoff"))
        result = self.recover(["main.py"], handoff=".governance/handoff.json")
        self.assertIn("handoff unavailable or invalid", " ".join(result["recovery"]["gaps"]))

    def test_fixed_git_queries_are_scoped_sanitized_and_do_not_invoke_hooks(self):
        self.write("main.py", "pass\n")
        commands = []
        attributes = b"".join(b"main.py\0" + name.encode() + b"\0unspecified\0"
                              for name in ("filter", "text", "eol", "working-tree-encoding", "ident", "crlf"))
        oid = hashlib.sha1(b"blob 9\0old pass\n").hexdigest().encode()
        replies = [str(self.root).encode() + b"\n", b"a" * 40 + b"\n", b"main\n", attributes,
                   b"100644 " + oid + b" 0\tmain.py\0", b""]
        def run(command, **kwargs):
            commands.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, replies.pop(0), b"")
        with patch.object(FACTS, "_bounded_git_query", side_effect=run), patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_SSH_COMMAND": "unsafe"}):
            result, gaps = FACTS.git_state(self.root, ["main.py"], sys.executable)
        self.assertTrue(result["available"]); self.assertFalse(gaps)
        self.assertEqual(result["changed_paths"], ["main.py"])
        self.assertEqual(len(commands), 6)
        self.assertEqual(commands[-1][0][-1], ":(literal)main.py")
        self.assertEqual(commands[3][0][-1], "main.py")  # check-attr takes literal names, not pathspec magic.
        self.assertIn("--stage", commands[4][0]); self.assertIn("--cached", commands[5][0])
        for command, kwargs in commands:
            self.assertIn("core.fsmonitor=false", command)
            self.assertIn("core.hooksPath=" + os.devnull, command)
            self.assertIn("core.attributesFile=" + os.devnull, command)
            self.assertNotIn("status", command); self.assertNotIn("--modified", command)
            self.assertNotIn("GIT_CONFIG_COUNT", kwargs["env"])
            self.assertNotIn("GIT_SSH_COMMAND", kwargs["env"])
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertEqual(kwargs["timeout"], 5)

    def test_git_unknown_and_scope_escape_do_not_claim_clean(self):
        with patch.object(FACTS, "_bounded_git_query", side_effect=subprocess.TimeoutExpired("git", 5)):
            state, gaps = FACTS.git_state(self.root, ["main.py"], sys.executable)
        self.assertFalse(state["available"]); self.assertTrue(gaps)
        with self.assertRaises(ValueError): FACTS.git_state(self.root, ["main.py"], "git")

    def test_real_git_untracked_and_ignored_scoped_files_are_dirty(self):
        binary = shutil.which("git")
        if binary is None: self.skipTest("registered Git unavailable")
        environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if key in os.environ}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                           GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
        prefix = [binary, "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false",
                  "-c", "user.name=Recovery Test", "-c", "user.email=recovery@example.invalid"]
        def git(*args):
            completed = subprocess.run(prefix + list(args), cwd=self.root, env=environment, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        git("init", "--template=")
        self.write("tracked.txt", "tracked")
        self.write(".gitignore", "ignored.py\n")
        git("add", "--", "tracked.txt", ".gitignore")
        git("commit", "--no-gpg-sign", "--no-verify", "-m", "test source identity")
        self.write("untracked.py", "pass\n")
        self.write("ignored.py", "pass\n")
        for name in ("untracked.py", "ignored.py"):
            state, gaps = FACTS.git_state(self.root, [name], binary)
            self.assertTrue(state["available"], gaps)
            self.assertEqual(state["changed_paths"], [name])
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], [])

    def test_real_git_clean_filter_never_executes_or_inherits_dynamic_validity(self):
        binary, git = self.synthetic_git()
        content = b'open("filter.marker", "ab").write(b"clean\\n")\n# before\n'
        tracked = self.root / "tracked.txt"
        tracked.write_bytes(content)
        self.write(".gitattributes", "tracked.txt filter=upg-recovery-test\n")
        # Stage the raw bytes before registering a program that changes them.
        self.commit_git(git, "tracked.txt", ".gitattributes")
        executable = sys.executable.replace("\\", "/")
        git("config", "--local", "filter.upg-recovery-test.clean", '"' + executable + '"' if " " in executable else executable)
        git("config", "--local", "filter.upg-recovery-test.required", "true")
        revision = git("rev-parse", "HEAD").decode().strip()
        initial_time = tracked.stat().st_mtime_ns
        for raw in (content, content.replace(b"before", b"after!")):
            with self.subTest(same_bytes=raw == content):
                tracked.write_bytes(raw)
                os.utime(tracked, ns=(initial_time + 3000000000,) * 2)
                state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
                self.assertFalse(state["available"])
                self.assertIn("active filter or normalization", " ".join(gaps))
                self.assertFalse((self.root / "filter.marker").exists())
        tracked.write_bytes(content)
        view = self.seed(["tracked.txt"])
        ref = self.ref("tracked.txt")
        view["evidence"] = [self.evidence("tracked.txt", kind="dynamic", inputs=[ref],
                                           configuration=[ref], environment=ref, tested_revision=revision)]
        view["evidence_checks"] = [{"id": "check-1", "fixity": "match", "validity": "unverified", "semantic_truth": "unassessed"}]
        self.save(view)
        result = self.recover(["tracked.txt"], handoff=".governance/handoff.json", git_binary=binary)
        self.assertEqual(result["recovery"]["evidence_checks"][0]["validity"], "unverified")
        self.assertFalse(result["coverage"]["project_code_executed"])
        self.assertFalse((self.root / "filter.marker").exists())

    def test_real_git_normalization_attributes_never_claim_raw_equality_is_clean(self):
        binary, git = self.synthetic_git()
        (self.root / "tracked.txt").write_bytes(b"same raw bytes\n")
        self.commit_git(git, "tracked.txt")
        for attribute in ("text", "text=auto", "eol=crlf", "working-tree-encoding=UTF-8", "ident", "crlf"):
            with self.subTest(attribute=attribute):
                self.write(".gitattributes", "tracked.txt " + attribute + "\n")
                state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
                self.assertFalse(state["available"])
                self.assertIn("normalization", " ".join(gaps))
        self.write(".gitattributes", "tracked.txt -filter -text -eol -working-tree-encoding -ident -crlf\n")
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], [])
        (self.root / "tracked.txt").write_bytes(b"same raw bytes\r\n")
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])

    def test_real_git_staged_missing_unmerged_and_empty_intent_to_add_are_dirty(self):
        binary, git = self.synthetic_git()
        tracked = self.write("tracked.txt", "original\n")
        self.commit_git(git, "tracked.txt")
        tracked.write_bytes(b"staged\n")
        git("add", "--", "tracked.txt")
        for raw in (b"staged\n", b"original\n"):
            tracked.write_bytes(raw)
            state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
            self.assertTrue(state["available"], gaps)
            self.assertEqual(state["changed_paths"], ["tracked.txt"])
        git("add", "--", "tracked.txt")
        oid = git("ls-files", "--stage", "--", "tracked.txt").split()[1].decode()
        tracked.unlink()
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])
        tracked.write_bytes(b"original\n")
        entries = "0 %s\ttracked.txt\n" % ("0" * len(oid))
        entries += "".join("100644 %s %s\ttracked.txt\n" % (oid, stage) for stage in (1, 2, 3))
        git("update-index", "--index-info", input=entries.encode())
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])
        self.write("empty.txt", "")
        git("add", "--intent-to-add", "--", "empty.txt")
        state, gaps = FACTS.git_state(self.root, ["empty.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["empty.txt"])

    def test_real_git_nested_root_keeps_literal_scope_and_cached_paths(self):
        binary, git = self.synthetic_git()
        tracked = self.write("nested/file[1].txt", "original")
        self.write("nested/file1.txt", "decoy")
        self.commit_git(git, "nested/file[1].txt", "nested/file1.txt")
        state, gaps = FACTS.git_state(self.root / "nested", ["file[1].txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], [])
        tracked.write_bytes(b"staged")
        git("add", "--", "nested/file[1].txt")
        state, gaps = FACTS.git_state(self.root / "nested", ["file[1].txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["file[1].txt"])

    def test_real_git_sha256_blob_identity_detects_equal_length_edit(self):
        binary, git = self.synthetic_git(sha256=True)
        tracked = self.write("tracked.txt", "before")
        self.commit_git(git, "tracked.txt")
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(len(state["revision"]), 64)
        self.assertEqual(state["changed_paths"], [])
        tracked.write_bytes(b"after!")
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])

    def test_git_raw_comparison_reuses_bounded_bytes_and_rejects_observation_drift(self):
        binary, git = self.synthetic_git()
        tracked = self.write("tracked.txt", "original")
        self.commit_git(git, "tracked.txt")
        reader = FACTS.Reader(self.root)
        raw = reader.read("tracked.txt")
        with patch.object(FACTS.os, "open", wraps=os.open) as opened:
            state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary, reader=reader)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], [])
        self.assertFalse(any(str(call.args[0]) == str(tracked) for call in opened.call_args_list))
        self.assertEqual(reader.total_bytes, len(raw))
        before = tracked.stat().st_mtime_ns
        tracked.write_bytes(b"after!!!")
        os.utime(tracked, ns=(before + 3000000000,) * 2)
        state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary, reader=reader)
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])
        self.assertEqual(reader.total_bytes, len(raw))
        with patch.object(FACTS, "MAX_TOTAL_BYTES", 0):
            state, gaps = FACTS.git_state(self.root, ["tracked.txt"], binary, reader=FACTS.Reader(self.root))
        self.assertTrue(state["available"], gaps)
        self.assertEqual(state["changed_paths"], ["tracked.txt"])

    def test_git_attribute_metadata_must_cover_each_exact_literal_path(self):
        self.write("main.py", "pass\n")
        attributes = b"".join(b"main.py\0" + name.encode() + b"\0unspecified\0"
                              for name in ("filter", "text", "eol", "working-tree-encoding", "ident", "crlf"))
        for invalid in (attributes.replace(b"main.py", b":(literal)main.py"),
                        attributes + b"main.py\0filter\0unspecified\0", attributes.rsplit(b"main.py\0", 1)[0]):
            replies = [str(self.root).encode() + b"\n", b"a" * 40 + b"\n", b"main\n", invalid]
            with self.subTest(metadata=invalid), patch.object(FACTS, "_bounded_git_query", side_effect=[
                    subprocess.CompletedProcess([], 0, reply, b"") for reply in replies]) as run:
                state, gaps = FACTS.git_state(self.root, ["main.py"], sys.executable)
            self.assertFalse(state["available"])
            self.assertTrue(gaps)
            self.assertEqual(run.call_count, 4)

    def test_canonical_validation_revision_and_retest_remain_historical(self):
        self.write("main.py", "pass")
        record = {"validation_runs": [{"run_id": "scoped-check", "scope": "unit task", "result": "passed",
                                      "tested_revision": "b" * 40, "passed": 1, "total": 1, "pending_retest": True}]}
        self.write("result.json", json.dumps(record))
        scope = ["main.py", "result.json"]
        view = self.seed(scope)
        self.save(view, validation_ref=dict(self.ref("result.json"), run_id="scoped-check"))
        git = dict(view["source_state"]["git"], available=True, revision="a" * 40, root=str(self.root), branch="main")
        with patch.object(FACTS, "git_state", return_value=(git, [])):
            result = self.recover(scope, handoff=".governance/handoff.json")
        self.assertIn("historical or pending retest", " ".join(result["recovery"]["gaps"]))
        self.assertEqual(result["recovery"]["semantic_completion"], "unassessed")

    def test_normal_plan_no_new_block_and_recovery_is_conditional(self):
        index = PLAN.load_index()
        normal = PLAN.compile_plan(index, {"operation": "edit", "domains": ["code"]})
        self.assertNotIn("recovery", normal)
        self.assertEqual(len(index["default_rules"]), 3)
        self.assertEqual(len(index["hot_path"]), 8)
        for signal in ("interrupted", "stale-evidence", "contradiction", "no-progress", "handoff-missing", "opaque-artifact"):
            result = PLAN.compile_plan(index, {"operation": "edit", "domains": ["code"], "signals": [signal]})
            self.assertIn("HANDOFF_CONTINUITY", result["active_rules"])
            self.assertIn(signal, result["recovery"]["triggers"])
            self.assertIn("Project fact recovery", PLAN.render_markdown(result))
        self.assertEqual(result["recovery"]["mode"], "specialist-needed")

    def test_planner_imported_by_path_resolves_exact_sibling_without_sys_path(self):
        with patch.object(sys, "path", [path for path in sys.path if path != str(RUNTIME / "scripts")]), patch.dict(sys.modules, {"project_facts": None}):
            result = PLAN.compile_plan(PLAN.load_index(), {"operation": "edit", "domains": ["code"], "signals": ["interrupted"]})
        self.assertEqual(result["recovery"]["mode"], "static")

    def test_cli_read_only_contract_and_legacy_handoff_compatibility(self):
        self.write("main.py", "pass")
        completed = subprocess.run([sys.executable, "-B", str(RUNTIME / "scripts/state_tool.py"), "recover", str(self.root), "--scope", "main.py"], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["recovery"]["scope"], ["main.py"])
        self.assertFalse((self.root / ".governance").exists())
        self.save(self.seed(["main.py"]))
        handoff = self.root / ".governance/handoff.json"
        self.assertEqual(STATE.validate_file(handoff, "handoff"), [])
        self.assertIn("do not establish semantic truth", STATE.render(handoff, "handoff"))
        legacy = json.loads(handoff.read_text()); legacy.pop("recovery")
        handoff.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(STATE.validate_file(handoff, "handoff"), [])


if __name__ == "__main__":
    unittest.main()
