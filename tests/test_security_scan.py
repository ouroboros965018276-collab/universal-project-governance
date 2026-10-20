"""Secret scanning must prune excluded trees without losing eligible findings."""
import errno
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.security_audit import secret_scan


class SecretScanTests(unittest.TestCase):
    def setUp(self):
        directory=ROOT/'eval-workspaces/tmp-security-scan'
        directory.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(dir=directory)
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.token='gh'+'p_'+'A'*24

    def put(self,path,value=None):
        target=self.root/path
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(self.token if value is None else value,encoding='utf-8')
        return target

    def scan(self,path=None):
        errors=[]
        secret_scan(self.root if path is None else path,errors)
        return errors

    def expected(self,path,label='github-pat'):
        return '{}: secret-like {} pattern detected'.format(path,label)

    def test_excluded_subtrees_are_not_enumerated(self):
        ignored={'.git','.venv','dist','build','__pycache__','eval-workspaces'}
        for name in ignored:self.put('nested/{}/deep/token.py'.format(name))
        self.put('nested/eligible.py')
        real=os.scandir
        def observed(path):
            self.assertFalse(set(Path(path).relative_to(self.root).parts)&ignored)
            return real(path)
        with mock.patch('tools.security_audit.os.scandir',side_effect=observed):
            self.assertEqual(self.scan(),[self.expected(Path('nested/eligible.py'))])

    def test_all_families_and_stable_path_pattern_order(self):
        fence='-'*5
        values=[('private-key',fence+'BE'+'GIN '+prefix+'PRI'+'VATE KEY'+fence)
                for prefix in ('','RSA ','EC ','OPENSSH ')]
        values += [('github-pat',self.token),('github-pat','git'+'hub_'+'pat_'+'b'*24),
                   ('aws-access-key','AK'+'IA'+'1'*16),('bearer-token','Be'+'arer '+'Q'*24),
                   ('bearer-token','be'+'ARER\t'+'r'*25)]
        for i,(_,value)in reversed(list(enumerate(values))):self.put('{}.txt'.format(i),value)
        self.assertEqual(self.scan(),[self.expected('{}.txt'.format(i),label)for i,(label,_)in enumerate(values)])

    def test_file_eligibility_and_size_boundary(self):
        self.put('ok.JSON');self.put('LICENSE');self.put('.gitignore');self.put('not-scanned.bin')
        self.put('exact.txt',self.token+' '*(1_000_000-len(self.token)))
        self.put('large.txt',self.token+' '*1_000_000)
        self.assertEqual(self.scan(),[self.expected(name)for name in sorted(map(Path,('.gitignore','LICENSE','exact.txt','ok.JSON')))])

    def test_nested_eligible_files_and_hardlinks(self):
        source=self.put('deep/a.py')
        try:os.link(source,self.root/'b.py')
        except OSError:self.skipTest('hardlink creation unavailable')
        self.assertEqual(self.scan(),[self.expected('b.py'),self.expected(Path('deep/a.py'))])

    def test_symlink_file_and_directory_do_not_extend_scope(self):
        target=self.put('outside/a.txt')
        root=self.root/'links';root.mkdir()
        try:
            os.symlink(target,root/'file.txt')
            os.symlink(target.parent,root/'directory',target_is_directory=True)
        except OSError:self.skipTest('symlink creation unavailable')
        self.assertEqual(self.scan(root),[])

    def test_missing_or_file_root_is_empty(self):
        self.assertEqual(self.scan(self.root/'missing'),[])
        self.assertEqual(self.scan(self.put('file.txt')),[])

    def test_scandir_iteration_error_is_not_success(self):
        class Broken:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def __iter__(self):return self
            def __next__(self):raise OSError(errno.EIO,'owned synthetic iteration failure')
        with mock.patch('tools.security_audit.os.scandir',return_value=Broken()):
            with self.assertRaises(OSError):self.scan()

    def test_unreadable_eligible_directory_is_not_clean(self):
        self.put('denied/secret.txt')
        real=os.scandir
        def observed(path):
            if Path(path)==self.root/'denied':raise PermissionError('owned synthetic permission failure')
            return real(path)
        with mock.patch('tools.security_audit.os.scandir',side_effect=observed):
            with self.assertRaises(PermissionError):self.scan()

    def test_unclassifiable_entry_is_not_clean(self):
        class Entry:
            name='eligible'
            def is_dir(self,follow_symlinks=True):raise OSError(errno.EIO,'owned synthetic classification failure')
        class Entries:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def __iter__(self):return iter([Entry()])
        with mock.patch('tools.security_audit.os.scandir',return_value=Entries()):
            with self.assertRaises(OSError):self.scan()


if __name__=='__main__':unittest.main()
