"""Public synthetic raw receipts only; never execute candidate Python or processes."""
from __future__ import annotations
import ast,base64,copy,json,pathlib,socket,subprocess,tempfile,time,types,unittest
from unittest.mock import patch
from evolution import project_executor as p,engineering_broker as broker,tool_broker
from test_project_executor import FakeDocker,FILES,CONTRACT

HERE=pathlib.Path(__file__).resolve().parent
SYNTAX="VALUE = '"+"\\"+"'\n"
ERROR=b"SyntaxError: unterminated string literal (detected at line 1)\n"

class FailedChecks(FakeDocker):
    def rows(self,inp):
        rows=super().rows(inp)
        for row in rows:
            row.update(exit_code=1,outcome={'recipe':row['recipe'],'completed':False},
                stdout_base64='',stdout_sha256=p.sha(b''),stdout_bytes=0,
                stderr_base64=base64.b64encode(ERROR).decode(),stderr_sha256=p.sha(ERROR),stderr_bytes=len(ERROR),
                observed_bytes=len(ERROR),output_files={name:{'missing':True} for name in row['output_files']})
        return rows

class RuntimeFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='runtime-failure-pure-',dir=HERE);self.addCleanup(self.temp.cleanup)
        self.base=pathlib.Path(self.temp.name)
        for obj,name in [(subprocess,n) for n in ('Popen','run','call','check_call','check_output')]+[(socket,n) for n in ('socket','create_connection')]:
            fence=patch.object(obj,name,side_effect=AssertionError('live process/network forbidden'));fence.start();self.addCleanup(fence.stop)

    def bad_files(self,kind):
        files=copy.deepcopy(FILES)
        if kind=='syntax':files['sample_pkg/core.py']=SYNTAX
        elif kind=='missing':del files['sample_pkg/core.py']
        elif kind=='empty-map':files={}
        else:
            for name in files:
                if name.endswith('.py'):files[name]={'empty':'','pass':'pass\n','docstring':'"only documentation"\n','ellipsis':'def f():\n    ...\n'}[kind]
        return files

    def execute(self,files,artifacts=None,fake=None,contract=None):
        fake=fake or FailedChecks()
        artifacts=artifacts or self.base/'execution'
        with patch.object(p,'_capture',fake):
            checked,summary=p.validate_with_project_execution(files,contract or CONTRACT,artifacts,60)
        return checked,summary,fake

    def test_syntax_empty_and_missing_sources_are_executed_known_failures(self):
        for kind in ('syntax','empty','pass','docstring','ellipsis','empty-map','missing'):
            with self.subTest(kind=kind):
                files=self.bad_files(kind);directory=self.base/kind
                checked,summary,fake=self.execute(files,directory)
                self.assertEqual(summary['status'],'EXECUTED',summary);self.assertFalse(summary['unknown'])
                self.assertTrue(checked['integrity_ok']);self.assertFalse(checked['ok'])
                self.assertEqual(checked['checks_passed'],0);self.assertEqual(len(fake.calls),8)
                diagnostic=checked['diagnostics'][0]
                self.assertEqual(diagnostic['stderr'],ERROR.decode())
                self.assertEqual(diagnostic['stderr_sha256'],p.sha(ERROR));self.assertEqual(diagnostic['stderr_bytes'],len(ERROR))
                self.assertEqual(diagnostic['id'],'unit');self.assertIs(diagnostic['completed'],False)
                with patch.object(p,'_capture',side_effect=AssertionError('pure read cannot execute')):
                    reread,_,_=p.read_project_receipt(files,CONTRACT,directory,summary['receipt_sha256'])
                self.assertEqual(reread,checked)

    def test_default_registration_and_trusted_test_syntax_stay_strict(self):
        for kind in ('syntax','empty','pass','docstring','ellipsis','empty-map','missing'):
            with self.subTest(kind=kind),self.assertRaises((SyntaxError,ValueError)):
                p._prepare(self.bad_files(kind),CONTRACT)
        trusted=copy.deepcopy(CONTRACT);trusted['trusted_files']['registered_tests.py']='def broken(:\n'
        with self.assertRaises(SyntaxError):p.validate_contract(trusted)
        with self.assertRaises(SyntaxError):p._prepare(FILES,trusted,runtime_snapshot=True)

    def test_fixed_checker_rejects_vacuous_tests_before_importing_them(self):
        checker=ast.parse(p.CHECKER)
        function=next(n for n in checker.body if isinstance(n,ast.FunctionDef) and n.name=='require_implementation')
        guard_call=next(n for n in checker.body if isinstance(n,ast.Try)).body[0]
        self.assertIsInstance(guard_call,ast.Expr);self.assertEqual(guard_call.value.func.id,'require_implementation')
        # Execute only trusted guard, which parses source AST; never submitted code.
        for kind in ('syntax','empty','pass','docstring','ellipsis','empty-map'):
            files=self.bad_files(kind)
            class SourcePath:
                def __init__(self,name):self.name=name
                def __truediv__(self,name):return SourcePath(name)
                def read_text(self,**kwargs):return files[self.name]
            env={'ast':ast,'Path':SourcePath,'inp':{'files_sha256':{name:'0'*64 for name in files}}}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'trusted-checker-guard','exec'),env)
            with self.subTest(kind=kind),self.assertRaises((SyntaxError,RuntimeError)):
                env['require_implementation']()

    def test_module_runtime_guard_binds_origin_before_runpy(self):
        checker=ast.parse(p.CHECKER);main=next(n for n in checker.body if isinstance(n,ast.Try))
        module_branch=main.body[1].orelse[0].orelse
        calls=[n for statement in module_branch for n in ast.walk(statement) if isinstance(n,ast.Call)]
        self.assertTrue(any(isinstance(n.func,ast.Attribute) and n.func.attr=='find_spec' for n in calls))
        self.assertLess(p.CHECKER.index('find_spec('),p.CHECKER.index('runpy.run_module('))

    def test_runtime_scope_secret_ambiguity_bounds_are_not_relaxed(self):
        bad_cases=[{'../escape.py':'x=1\n'},dict(FILES,**{'sample_pkg/core/__init__.py':'x=1\n'}),
            dict(FILES,**{'secret.txt':'sk-synthetic-credential-123456789'}),{'huge.py':'x'*(p.MAX_FILE_BYTES+1)}]
        for files in bad_cases:
            with self.subTest(names=list(files)),self.assertRaises(ValueError):p._prepare(files,CONTRACT,runtime_snapshot=True)
        for value in (1,None,'runtime'):
            with self.assertRaises(ValueError):p._prepare(FILES,CONTRACT,runtime_snapshot=value)

    def test_raw_tamper_and_changed_snapshot_remain_unknown_without_reexecution(self):
        files=self.bad_files('syntax');checked,summary,fake=self.execute(files)
        self.assertEqual(summary['status'],'EXECUTED',summary)
        changed=dict(files);changed['assets/input.txt']='changed\n'
        with patch.object(p,'_capture',side_effect=AssertionError('no reexecution')):
            with self.assertRaises(ValueError):p.read_project_receipt(changed,CONTRACT,self.base/'execution')
            (self.base/'execution/04-start-attach.stdout.raw').write_bytes(b'tamper')
            with self.assertRaises(ValueError):p.read_project_receipt(files,CONTRACT,self.base/'execution')
        self.assertEqual(len(fake.calls),8)

    def test_cleanup_unknown_and_bad_stream_never_expose_diagnostics(self):
        for mode in ('cleanup','stream-hash','create-timeout'):
            checked,summary,fake=self.execute(FILES,self.base/mode,FakeDocker(mode))
            self.assertTrue(summary['unknown']);self.assertFalse(checked['integrity_ok'])
            self.assertEqual(checked['diagnostics'],[])

    def test_diagnostic_stream_secret_and_size_guards_precede_feedback(self):
        for raw in (b'sk-synthetic-credential-123456789',b'x'*(p.CHECK_OUTPUT_LIMIT+1)):
            class InvalidStream(FailedChecks):
                def rows(self,inp):
                    rows=super().rows(inp);row=rows[0]
                    row.update(stderr_base64=base64.b64encode(raw).decode(),stderr_sha256=p.sha(raw),
                        stderr_bytes=len(raw),observed_bytes=len(raw))
                    return rows
            checked,summary,_=self.execute(FILES,self.base/p.sha(raw),InvalidStream())
            self.assertTrue(summary['unknown']);self.assertFalse(checked['integrity_ok'])
            self.assertEqual(checked['diagnostics'],[])

    def test_broker_keeps_known_failure_repairable_and_transmits_verified_diagnostics(self):
        workspace=self.base/'repo';workspace.mkdir()
        for name,text in FILES.items():
            path=workspace/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))
        task={'id':'public-runtime-failure','family':'synthetic','prompt':'Repair public package.',
            'initial_files':copy.deepcopy(FILES),'writable_files':['sample_pkg/core.py'],
            'required_tools':['repo_read','repo_patch','repo_validate','repo_status'],'engineering_contract':copy.deepcopy(CONTRACT)}
        with patch.object(tool_broker,'git_command',return_value=types.SimpleNamespace(returncode=0,stdout=b'',stderr=b'')):
            b=broker.create_broker(workspace,task,self.base/'mock-git',audit_file=self.base/'broker.jsonl',
                deadline=time.time()+60,execution_artifacts=self.base/'validations')
            before=b.snapshot();b.call('repo_read',{'paths':['sample_pkg/core.py']})
            b.call('repo_patch',{'operations':[{'path':'sample_pkg/core.py','old_sha256':before['sample_pkg/core.py'],'new_text':SYNTAX}]})
            with patch.object(p,'_capture',FailedChecks()):failed=b.call('repo_validate',{})
            self.assertFalse(failed['ok']);self.assertFalse(failed['execution']['unknown']);self.assertIsNone(b.terminal_result)
            self.assertEqual(failed['diagnostics'][0]['stderr'],ERROR.decode())
            original=copy.deepcopy(failed['diagnostics']);failed['diagnostics'][0]['stderr']='unverified hint'
            final_failed=json.dumps({'summary':'Public failing package.','validation':'failed','helper_gap':'project_tool unavailable in bounded broker'})
            with patch.object(p,'execute_project',side_effect=AssertionError('final score cannot execute')):
                corrupt=broker.quality_from_current_receipts(b,before,final_failed,[],[])
            self.assertTrue(corrupt['execution_state_unknown']);failed['diagnostics']=original
            b.call('repo_read',{'paths':['sample_pkg/core.py']})
            b.call('repo_patch',{'operations':[{'path':'sample_pkg/core.py','old_sha256':b.snapshot()['sample_pkg/core.py'],'new_text':FILES['sample_pkg/core.py']+'# repaired\n'}]})
            failed['diagnostics'][0]['stderr']='unverified historical hint'
            with patch.object(p,'execute_project',side_effect=AssertionError('stale read cannot execute')):
                corrupt=broker.quality_from_current_receipts(b,before,final_failed,[],[])
            self.assertTrue(corrupt['execution_state_unknown']);failed['diagnostics']=original
            with patch.object(p,'_capture',FakeDocker()):passed=b.call('repo_validate',{})
            self.assertTrue(passed['ok']);self.assertEqual(passed['diagnostics'],[]);b.call('repo_status',{})
            trace=[];previous=None
            for event in b.events:
                row={'previous_chain_sha256':previous,'broker_sequence':event['sequence'],'broker_event_sha256':p.sha(p.canonical(event)),
                    'arguments_sha256':event['arguments_sha256'],'result_sha256':event['result_sha256']}
                row['chain_sha256']=p.sha(p.canonical(row));previous=row['chain_sha256'];trace.append(row)
            final=json.dumps({'summary':'Public repaired package.','validation':'passed','helper_gap':'project_tool unavailable in bounded broker'})
            with patch.object(p,'execute_project',side_effect=AssertionError('final score cannot execute')):
                quality=broker.quality_from_current_receipts(b,before,final,trace,[])
            self.assertTrue(quality['hard_pass'],quality)

