"""Native pipe lifetime regression for bounded project-fact queries."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("bounded_git_query_lifetime_facts",ROOT/"governance-src/runtime-scripts/project_facts.py")
facts=importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)


class BoundedGitQueryLifetime(unittest.TestCase):
    def test_timeout_returns_before_descendant_releases_inherited_pipes(self):
        # Both children are finite and local. The direct process is killed by
        # the query; its descendant exits naturally without PID-based cleanup.
        command=[sys.executable,"-c",
            'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time;time.sleep(1.5)"]); time.sleep(10)']
        processes=[]
        native_popen=subprocess.Popen
        def launch(*args,**kwargs):
            process=native_popen(*args,**kwargs); processes.append(process)
            return process
        started=time.monotonic()
        with patch.object(facts.subprocess,"Popen",side_effect=launch):
            with self.assertRaises(subprocess.TimeoutExpired):
                facts._bounded_git_query(command,output_limit=1024,timeout=0.1,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        elapsed=time.monotonic()-started
        self.assertLess(elapsed,1.0,"query blocked until the descendant closed its pipes")
        self.assertIsNotNone(processes[0].poll())
        # Observe reader-owned closure and leave no test helper still running.
        deadline=time.monotonic()+4
        while time.monotonic()<deadline and not all(stream.closed for stream in (processes[0].stdout,processes[0].stderr)):
            time.sleep(0.02)
        self.assertTrue(processes[0].stdout.closed)
        self.assertTrue(processes[0].stderr.closed)


if __name__=="__main__": unittest.main()
