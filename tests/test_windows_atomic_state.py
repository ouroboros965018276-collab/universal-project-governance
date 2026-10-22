"""Bounded atomic state replacement under temporary Windows reader locks."""
import ctypes
import errno
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "governance-src/runtime-scripts"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


STATE = module("atomic_state_contract", SCRIPTS / "state_tool.py")
GUARDS = module("atomic_state_guards", SCRIPTS / "process_guard.py")
with patch.dict("sys.modules", state_tool=STATE, process_guard=GUARDS):
    PROJECT = module("atomic_state_project", SCRIPTS / "project_tool.py")


class AtomicStateTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "eval-workspaces"
        parent.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="atomic-state-", dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / ".governance/upg.json"
        self.path.parent.mkdir()
        self.original = b'{"original": true}\n'
        self.path.write_bytes(self.original)

    def fake_os(self, platform, replace):
        # A local proxy leaves pathlib's actual host platform unchanged.
        return SimpleNamespace(name=platform, fstat=os.fstat, fsync=os.fsync, replace=replace)

    def permission_error(self, code):
        error = PermissionError(errno.EACCES, "controlled replacement denial")
        error.winerror = code
        return error

    def assert_no_temporary_files(self):
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_transient_windows_errors_retry_without_exposing_partial_json(self):
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                self.path.write_bytes(self.original)
                attempts = []

                def replace(source, destination):
                    attempts.append(source)
                    self.assertEqual(self.path.read_bytes(), self.original)
                    if len(attempts) < 3:
                        raise self.permission_error(code)
                    os.replace(source, destination)

                with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                        patch.object(PROJECT.time, "sleep") as sleep:
                    PROJECT.write_json_atomic(self.path, {"completed": True})
                self.assertEqual(json.loads(self.path.read_text()), {"completed": True})
                self.assertEqual(len(attempts), 3)
                self.assertEqual(len(set(attempts)), 1, "retries must retain the owned temporary file")
                self.assertEqual(sleep.call_count, 2)
                self.assert_no_temporary_files()

    def test_permanent_windows_denial_is_bounded_and_preserves_original_error(self):
        error = self.permission_error(5)
        with patch.object(PROJECT, "os", self.fake_os("nt", None)) as proxy, \
                patch.object(PROJECT.time, "sleep") as sleep:
            proxy.replace = Mock(side_effect=error)
            with self.assertRaises(PermissionError) as failure:
                PROJECT.write_json_atomic(self.path, {"replacement": True})
        self.assertIs(failure.exception, error)
        self.assertGreater(proxy.replace.call_count, 1)
        self.assertLessEqual(proxy.replace.call_count, 20)
        self.assertEqual(sleep.call_count, proxy.replace.call_count - 1)
        self.assertGreater(sum(call.args[0] for call in sleep.call_args_list), 0)
        self.assertLess(sum(call.args[0] for call in sleep.call_args_list), 1)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporary_files()

    def test_other_platforms_and_errors_propagate_without_retry(self):
        for platform, error in (("posix", self.permission_error(5)),
                                ("nt", self.permission_error(87)),
                                ("nt", PermissionError(errno.EACCES, "no Windows error code")),
                                ("nt", OSError(errno.ENOSPC, "storage full"))):
            with self.subTest(platform=platform, error=error):
                replace = Mock(side_effect=error)
                with patch.object(PROJECT, "os", self.fake_os(platform, replace)), \
                        patch.object(PROJECT.time, "sleep") as sleep:
                    with self.assertRaises(type(error)) as failure:
                        PROJECT.write_json_atomic(self.path, {"replacement": True})
                self.assertIs(failure.exception, error)
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assert_no_temporary_files()

    def test_retry_rejects_replaced_temporary_identity_and_preserves_foreign_file(self):
        attempts = []
        moved = self.root / "original-owned-temporary"

        def replace(source, destination):
            attempts.append(Path(source))
            raise self.permission_error(32)

        def swap_temporary(delay):
            temporary = attempts[0]
            temporary.rename(moved)
            temporary.write_bytes(b"foreign temporary file\n")

        with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                patch.object(PROJECT.time, "sleep", side_effect=swap_temporary):
            with self.assertRaisesRegex(ValueError, "temporary path changed"):
                PROJECT.write_json_atomic(self.path, {"replacement": True})
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(attempts[0].read_bytes(), b"foreign temporary file\n")
        self.assertEqual(json.loads(moved.read_text()), {"replacement": True})

    def test_retry_rejects_modified_same_inode_content_and_cleans_owned_temporary(self):
        replace = Mock(side_effect=self.permission_error(32))

        def mutate_temporary(delay):
            temporary = Path(replace.call_args.args[0])
            before = temporary.stat()
            temporary.write_bytes(b"changed same-inode content\n")
            after = temporary.stat()
            self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))

        with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                patch.object(PROJECT.time, "sleep", side_effect=mutate_temporary):
            with self.assertRaisesRegex(ValueError, "temporary write failed readback"):
                PROJECT.write_json_atomic(self.path, {"replacement": True})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assert_no_temporary_files()

    def create_symlink(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest("native symlink capability unavailable: %s" % error)

    def test_retry_rejects_destination_changed_to_symlink(self):
        outside = self.root / "outside.json"
        outside.write_bytes(b"outside content\n")
        # Probe this capability before changing the managed destination.
        probe = self.root / "symlink-probe"
        self.create_symlink(probe, outside)
        probe.unlink()
        replace = Mock(side_effect=self.permission_error(5))

        def swap_destination(delay):
            self.path.unlink()
            self.path.symlink_to(outside)

        with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                patch.object(PROJECT.time, "sleep", side_effect=swap_destination):
            with self.assertRaisesRegex(ValueError, "destination changed to a symlink"):
                PROJECT.write_json_atomic(self.path, {"replacement": True})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(outside.read_bytes(), b"outside content\n")
        self.assert_no_temporary_files()

    def test_retry_rejects_parent_changed_to_symlink(self):
        outside = self.root / "outside"
        outside.mkdir()
        outside_state = outside / self.path.name
        outside_state.write_bytes(b"outside content\n")
        probe = self.root / "symlink-probe"
        self.create_symlink(probe, outside, directory=True)
        probe.unlink()
        moved = self.root / "original-governance"
        replace = Mock(side_effect=self.permission_error(5))
        foreign_temporary = []

        def swap_parent(delay):
            temporary_name = Path(replace.call_args.args[0]).name
            self.path.parent.rename(moved)
            # Even the same owned inode must not authorize deletion through a
            # replacement parent symlink into another directory.
            foreign = outside / temporary_name
            os.link(str(moved / temporary_name), str(foreign))
            foreign_temporary.append(foreign)
            self.path.parent.symlink_to(outside, target_is_directory=True)

        with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                patch.object(PROJECT.time, "sleep", side_effect=swap_parent):
            with self.assertRaisesRegex(ValueError, "destination changed to a symlink"):
                PROJECT.write_json_atomic(self.path, {"replacement": True})
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(outside_state.read_bytes(), b"outside content\n")
        self.assertEqual((moved / self.path.name).read_bytes(), self.original)
        self.assertTrue(foreign_temporary[0].is_file())

    @unittest.skipUnless(os.name == "nt", "native Windows sharing semantics")
    def test_native_reader_without_delete_sharing_releases_during_retry(self):
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        # GENERIC_READ / FILE_SHARE_READ / OPEN_EXISTING, deliberately omitting
        # FILE_SHARE_DELETE. No ACL or host settings are changed.
        handle = create(str(self.path), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value, ctypes.get_last_error())
        self.addCleanup(lambda: close(handle) if handle is not None else None)
        errors = []

        def replace(source, destination):
            try:
                os.replace(source, destination)
            except PermissionError as error:
                errors.append(error.winerror)
                self.assertEqual(self.path.read_bytes(), self.original)
                raise

        def release_reader(delay):
            nonlocal handle
            self.assertTrue(close(handle), ctypes.get_last_error())
            handle = None

        with patch.object(PROJECT, "os", self.fake_os("nt", replace)), \
                patch.object(PROJECT.time, "sleep", side_effect=release_reader):
            PROJECT.write_json_atomic(self.path, {"completed": True})
        self.assertEqual(len(errors), 1)
        self.assertIn(errors[0], (5, 32, 33))
        self.assertEqual(json.loads(self.path.read_text()), {"completed": True})
        self.assert_no_temporary_files()


if __name__ == "__main__":
    unittest.main()
