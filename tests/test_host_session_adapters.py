"""Necessary host lifetime adapters: finite calibration without model requests."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

import test_git_watch as fixture

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "governance-src/runtime-scripts"
sys.dont_write_bytecode = True
sys.path.insert(0, str(RUNTIME))
SPEC = importlib.util.spec_from_file_location("host_session_adapter_runtime", RUNTIME / "git_watch.py")
WATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCH)


class HostAdapterContractTests(unittest.TestCase):
    def test_invalid_host_options_reject_before_project_mutation_or_launch(self):
        invalid = [
            {},
            {"command": []},
            {"command": [sys.executable, "\0"]},
            {"command": [sys.executable], "executable": sys.executable},
            {"host": "unknown"},
            {"host": "stdin", "command": [sys.executable]},
            {"host": "stdin", "executable": sys.executable},
            {"host": "codex-cli", "command": [sys.executable, "unreviewed prompt"]},
            {"host": "codex-cli", "executable": str(ROOT / "no-such-codex-adapter.exe")},
        ]
        for options in invalid:
            with self.subTest(options=options), mock.patch.object(WATCH.project, "ensure") as ensure, \
                    mock.patch.object(WATCH.guards, "acquire") as acquire, \
                    mock.patch.object(WATCH.lifetime, "run_host") as launch:
                with self.assertRaises(ValueError):
                    WATCH.session(ROOT, **options)
                ensure.assert_not_called()
                acquire.assert_not_called()
                launch.assert_not_called()

    def test_codex_profile_builds_only_fixed_foreground_project_argv(self):
        # An existing executable proves resolution and argv shape here. The
        # separate official Codex calibration owns the actual binary identity.
        argv = WATCH._session_command(ROOT, None, "codex-cli", sys.executable)
        self.assertTrue(Path(argv[0]).samefile(sys.executable))
        self.assertEqual(argv[1:], ["--no-daemon", "--no-alt-screen", "--cd", str(ROOT.resolve())])
        self.assertEqual(WATCH._session_command(ROOT, [sys.executable, "--version"],
                                                "command", None),
                         [sys.executable, "--version"])
        self.assertIsNone(WATCH._session_command(ROOT, None, "stdin", None))

    def test_stdin_adapter_rejects_regular_file_without_project_changes(self):
        with Path(__file__).open("rb") as regular_file, \
                mock.patch.object(WATCH.sys, "stdin", regular_file), \
                mock.patch.object(WATCH.project, "ensure") as ensure, \
                mock.patch.object(WATCH.guards, "acquire") as acquire:
            with self.assertRaises(ValueError):
                WATCH.session(ROOT, host="stdin")
            ensure.assert_not_called()
            acquire.assert_not_called()

    def test_pipe_reads_discard_split_input_with_bounded_memory_and_no_output(self):
        read_fd, write_fd = os.pipe()
        try:
            with mock.patch.object(WATCH, "_session_input_available", return_value=4096), \
                    mock.patch.object(WATCH.os, "read", side_effect=[b"{", b"private-client-data}", b""]) as read, \
                    contextlib.redirect_stdout(io.StringIO()) as stdout, \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                WATCH._read_session_input(read_fd, threading.Event())
                self.assertEqual(read.call_count, 3)
                self.assertTrue(all(call.args[0] == read_fd and 1 <= call.args[1] <= 4096
                                    for call in read.call_args_list))
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "")
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_pipe_read_error_propagates_and_cancelled_reader_does_no_io(self):
        read_fd, write_fd = os.pipe()
        try:
            with mock.patch.object(WATCH, "_session_input_available", return_value=4096), \
                    mock.patch.object(WATCH.os, "read", side_effect=OSError("owned pipe failed")):
                with self.assertRaisesRegex(OSError, "owned pipe failed"):
                    WATCH._read_session_input(read_fd, threading.Event())
            ended = threading.Event()
            ended.set()
            with mock.patch.object(WATCH, "_session_input_available") as available, \
                    mock.patch.object(WATCH.os, "read") as read:
                WATCH._read_session_input(read_fd, ended)
                available.assert_not_called()
                read.assert_not_called()
        finally:
            os.close(read_fd)
            os.close(write_fd)


@unittest.skipUnless(fixture.shutil.which("git"), "real Git executable required")
class GitStdinSessionTests(unittest.TestCase):
    setUp = fixture.GitWatchTests.setUp
    cleanup = fixture.GitWatchTests.cleanup
    write = fixture.GitWatchTests.write
    git = fixture.GitWatchTests.git
    cli = fixture.GitWatchTests.cli
    watch = fixture.GitWatchTests.watch
    configure = fixture.GitWatchTests.configure
    count = fixture.GitWatchTests.count
    validator_count = fixture.GitWatchTests.validator_count
    wait_for = fixture.GitWatchTests.wait_for
    state = fixture.GitWatchTests.state
    close_sessions = fixture.GitWatchTests.close_sessions

    def start_stdin_session(self):
        prefix = ".governance/owned-stdin-%s" % (len(self.sessions) + 1)
        output = self.root / (prefix + "-output.txt")
        error = self.root / (prefix + "-error.txt")
        command = [sys.executable, str(fixture.CLI), "git-watch", str(self.root),
                   "--action", "session", "--host", "stdin"]
        with output.open("wb") as stdout, error.open("wb") as stderr:
            process = subprocess.Popen(command, cwd=self.root, stdin=subprocess.PIPE,
                                       stdout=stdout, stderr=stderr)
        record = {"process": process, "output": output, "error": error,
                  "observations": [], "closed": False}
        self.sessions.append(record)
        def started():
            if process.poll() is not None:
                self.fail(error.read_text(encoding="utf-8", errors="replace") +
                          output.read_text(encoding="utf-8", errors="replace"))
            state = self.state()
            return (state.get("pid") and state.get("supervisor", {}).get("pid") and
                    state.get("supervisor", {}).get("status") == "watching")
        self.wait_for(started, timeout=30)
        state = self.state()
        record["observations"] = [fixture.ProcessObservation(state["pid"]),
                                  fixture.ProcessObservation(state["supervisor"]["pid"])]
        return record

    def finish_session(self, record, expected=(0,)):
        process = record["process"]
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()  # EOF from the actual host-owned pipe.
            process.wait(timeout=30)
            self.assertIn(process.returncode, expected,
                          record["error"].read_text(encoding="utf-8", errors="replace"))
            for observation in record["observations"]:
                self.wait_for(observation.exited, timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            for observation in record["observations"]:
                observation.close()
            record["observations"] = []
            record["closed"] = True

    def assert_native_guards_released(self):
        for name in WATCH.project.CONTROLLED_GUARDS:
            with self.subTest(guard=name):
                guard = WATCH.guards.acquire(self.root, name)
                self.assertIsNotNone(guard, name)
                guard.close()

    def test_owned_pipe_eof_stops_and_reentry_preserves_stages_and_deduplication(self):
        self.configure()
        first = self.start_stdin_session()
        first_state = self.state()
        # Contents are irrelevant to lifetime: split writes are discarded and
        # never interpreted as turn events, commands, prompts, or a close token.
        secret = b"adapter-private-payload-do-not-persist"
        for chunk in [b"{", secret, b"}\n", b"turn/completed\n"]:
            first["process"].stdin.write(chunk)
            first["process"].stdin.flush()
        self.write("source.txt", "first pipe session verified stage\n")
        self.wait_for(lambda: self.count() == 2, timeout=60)
        self.finish_session(first)
        stopped = self.state()
        self.assertTrue(stopped["desired_running"])
        self.assertEqual(stopped["session"]["status"], "ended")
        self.assertFalse(stopped.get("pid"))
        self.assertFalse(stopped.get("supervisor", {}).get("pid"))
        self.assert_native_guards_released()
        for file in [first["output"], first["error"], self.root / ".governance/upg.json"]:
            self.assertNotIn(secret, file.read_bytes())
        self.assertEqual(self.git("show", "HEAD:source.txt"),
                         b"first pipe session verified stage\n")
        self.write("source.txt", "next project entry required for this stage\n")
        self.cli("ensure", str(self.root))
        time.sleep(1.1)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.validator_count(), 1)
        second = self.start_stdin_session()
        second_state = self.state()
        self.assertNotEqual(second_state["session"]["token"], first_state["session"]["token"])
        self.wait_for(lambda: self.count() == 3, timeout=60)
        self.assertEqual(self.git("show", "HEAD:source.txt"),
                         b"next project entry required for this stage\n")
        # Native owner release is the publication barrier, rather than commit
        # visibility alone; a subsequent journal recovery may report committed.
        self.finish_session(second)
        self.assert_native_guards_released()
        before_tick = self.git("rev-parse", "HEAD")
        result = self.watch("tick")
        self.assertIn(result["watcher"]["status"], ("idle", "committed", "duplicate", "unchanged"))
        self.assertEqual(self.git("rev-parse", "HEAD"), before_tick)
        self.assertEqual(self.count(), 3)
        self.assertEqual(self.validator_count(), 2)


if __name__ == "__main__":
    unittest.main()
