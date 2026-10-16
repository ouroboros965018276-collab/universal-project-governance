"""Inert API-only sole parent owner. No child can launch before Job + GO."""
import argparse,ctypes,datetime,hashlib,importlib,importlib.util,json,os,subprocess,sys,time,uuid
from ctypes import wintypes as W
from pathlib import Path
HERE=Path(__file__).resolve().parent
OWNER_LIMITS={'active_process_limit':16,'job_memory_bytes':4*1024**3,'stdout_stderr_bytes_each_soft':65536,'job_ready_seconds':15,'cleanup_observation_seconds':5,'child_terminate_wait_seconds':5,'child_kill_wait_seconds':5}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def load_json(raw):
    def pairs(rows):
        value={}
        for key,item in rows:
            if key in value:raise ValueError('duplicate owner JSON')
            value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite owner JSON')))
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);raw=canonical(value)+b'\n'
    with path.open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return sha(raw)
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
def admission(bundle,expected_protocol,expected_plan):
    """Only stdlib reads/hashes before any candidate or child process exists."""
    bundle=Path(bundle).resolve();raw=(bundle/'execution-plan.json').read_bytes()
    if sha(raw)!=expected_plan:raise ValueError('external execution-plan SHA')
    plan=load_json(raw);protocol_raw=(bundle/'protocol.json').read_bytes()
    if sha(protocol_raw)!=expected_protocol or plan['protocol_sha256']!=expected_protocol:raise ValueError('external protocol SHA')
    p=load_json(protocol_raw);map_raw=(bundle/'assembly-source-map.json').read_bytes()
    if sha(map_raw)!=p['assembly_source_manifest_sha256']or plan['assembly_source_manifest_sha256']!=p['assembly_source_manifest_sha256']or plan['source_manifest_sha256']!=p['source_manifest_sha256']:raise ValueError('external source-map SHA')
    m=load_json(map_raw)
    for name,expected in m['source_map'].items():
        if '\\'in name or ':'in name or any(x in('','..','.')for x in name.split('/')):raise ValueError('owner source path')
        path=HERE.joinpath(*name.split('/'))
        if HERE not in path.resolve().parents:raise ValueError('owner source outside candidate')
        for target in(path,*path.parents):
            if target==HERE.parent:break
            info=target.lstat()
            if target.is_symlink()or getattr(info,'st_file_attributes',0)&1024:raise ValueError('owner linked source')
        if path.stat().st_nlink!=1 or sha(path.read_bytes())!=expected:raise ValueError('owner source differs:'+name)
    if m['source_map'].get('owner.py')!=sha(Path(__file__).read_bytes()):raise ValueError('owner entry not bound')
    host_raw=(bundle/'host-identity.json').read_bytes()
    if sha(host_raw)!=p['host_identity_sha256']:raise ValueError('owner host identity')
    host=load_json(host_raw)
    for name in('python','git','docker'):
        if sha(Path(host[name]['path']).read_bytes())!=host[name]['sha256']:raise ValueError('owner runtime binary:'+name)
    if Path(sys.executable).resolve()!=Path(host['python']['path']).resolve():raise ValueError('owner Python actual entry')
    command_raw=(bundle/'commands.json').read_bytes()
    if sha(command_raw)!=plan['command_sha256']:raise ValueError('owner exact command bytes')
    command=load_json(command_raw)
    runtime={name:host[name]for name in('python','git','docker')}
    if plan['runtime']!=runtime:raise ValueError('execution plan runtime identity')
    expected_launcher=[str(HERE/'launch.py'),'--bundle',str(bundle),'--protocol-sha256',expected_protocol,'--root-launch-authorized']
    child_prefix=[host['python']['path'],'-I','-B','-u',str(HERE/'owner.py'),'--child','--bundle',str(bundle),'--protocol-sha256',expected_protocol,'--execution-plan-sha256',expected_plan]
    if command!={'schema':'api-managed-exact-commands-v2','cwd':str(HERE),'launcher_main_argv':expected_launcher,'launcher_process_policy':'main call in same Job child; no second OS spawn',
        'child_argv_prefix':child_prefix[:-1]+['EXTERNAL_EXECUTION_PLAN_SHA256'],
        'parent_argv_template':child_prefix[:5]+child_prefix[6:-1]+['EXTERNAL_EXECUTION_PLAN_SHA256','--root-launch-authorized'],
        'job_name_argument':'--job-name owner-generated UUID'}:
        raise ValueError('owner argv/cwd differs from exact registered construction')
    if p['owner_policy']!='windows-job-before-go-api-owner-v3'or p['round_caps']['round_seconds_soft']!=54840 or p['owner_limits']!=OWNER_LIMITS:raise ValueError('owner policy/cap')
    return p,m,plan,command,child_prefix
def active_processes(job):
    class Accounting(ctypes.Structure):
        _fields_=[('user',ctypes.c_longlong),('kernel',ctypes.c_longlong),('period_user',ctypes.c_longlong),('period_kernel',ctypes.c_longlong),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]
    k=job.k;k.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p];k.QueryInformationJobObject.restype=W.BOOL
    value=Accounting()
    if not k.QueryInformationJobObject(job.handle,1,ctypes.byref(value),ctypes.sizeof(value),None):raise ctypes.WinError(ctypes.get_last_error())
    return int(value.active)
def child_input():return sys.stdin.buffer
def observed_argv():return list(sys.orig_argv)
def reap_owned_child(process):
    """One owned handle, bounded terminate/wait/kill/wait; never relaunch."""
    started=time.perf_counter();steps=[];errors=[];known=None
    def attempt(phase,callback,exit_result=False):
        before=time.perf_counter();row={'phase':phase,'status':'RETURNED','exception_class':None,'returncode':None}
        try:
            value=callback()
            if exit_result:
                if value is not None and type(value)is not int:raise TypeError('owned-child exit observation must be int or None')
                row['returncode']=value
        except BaseException as error:
            row.update(status='ERROR',exception_class=type(error).__name__);errors.append({'phase':phase,'exception_class':type(error).__name__})
        finally:row['wall_seconds']=time.perf_counter()-before;steps.append(row)
        return row
    if process is None:
        return {'status':'NOT_STARTED','observed_exited':False,'returncode':None,'steps':steps,'errors':errors,'wall_seconds':time.perf_counter()-started}
    initial=attempt('initial-poll',lambda:process.poll(),True)
    if initial['status']=='RETURNED'and type(initial['returncode'])is int:known=initial['returncode']
    if known is None:
        attempt('terminate',lambda:process.terminate())
        waited=attempt('wait-after-terminate',lambda:process.wait(timeout=OWNER_LIMITS['child_terminate_wait_seconds']),True)
        if waited['status']=='RETURNED'and type(waited['returncode'])is int:known=waited['returncode']
        if known is None:
            attempt('kill',lambda:process.kill())
            waited=attempt('wait-after-kill',lambda:process.wait(timeout=OWNER_LIMITS['child_kill_wait_seconds']),True)
            if waited['status']=='RETURNED'and type(waited['returncode'])is int:known=waited['returncode']
        final=attempt('final-poll',lambda:process.poll(),True)
        if final['status']=='RETURNED'and type(final['returncode'])is int:
            if known is not None and known!=final['returncode']:errors.append({'phase':'exit-consistency','exception_class':'ReturncodeMismatch'})
            known=final['returncode']
        elif final['status']=='RETURNED'and known is not None:
            errors.append({'phase':'exit-consistency','exception_class':'WaitPollContradiction'});known=None
    return {'status':'EXITED_CONFIRMED'if known is not None else'UNKNOWN_RETAINED','observed_exited':known is not None,'returncode':known,
        'steps':steps,'errors':errors,'wall_seconds':time.perf_counter()-started}
def after_go_launch(command):
    # The entire candidate bootstrap is verified before this import. -I removes
    # ambient PYTHONPATH; only the exact sibling package is then made available.
    sys.path.insert(0,str(HERE));launch=load_module('managed_api_launch_after_job',HERE/'launch.py')
    old=list(sys.argv);sys.argv=command['launcher_main_argv']
    try:return launch.main()
    finally:sys.argv=old
def child(bundle,protocol_sha,plan_sha,job_name):
    # Only stdlib and the fixed generic Job capability are loaded before READY.
    p,m,plan,command,_=admission(bundle,protocol_sha,plan_sha)
    Job=load_module('managed_api_child_job_capability',HERE/'winjob.py').Job
    job=Job(job_name);job.join();owner=Path(p['owner_root'])
    try:
        write(owner/'JOB_READY.json',{'pid':os.getpid(),'job_membership_confirmed':True,'protocol_sha256':protocol_sha,
            'command_sha256':plan['command_sha256'],'job_name':job_name,'observed_child_argv':observed_argv(),'observed_child_cwd':str(Path.cwd().resolve())})
        if child_input().readline()!=b'GO\n':raise ValueError('parent GO absent; no launcher or key')
        go=load_json((owner/'GO.json').read_bytes())
        if go['command_sha256']!=plan['command_sha256']or go['job_ready_sha256']!=sha((owner/'JOB_READY.json').read_bytes()):raise ValueError('parent GO binding')
        admission(bundle,protocol_sha,plan_sha)
        if time.perf_counter()>=load_json((owner/'STARTED.json').read_bytes())['owner_deadline_monotonic']:raise TimeoutError('owner round deadline before launcher')
        return after_go_launch(command)
    finally:job.close()
def parent(bundle,protocol_sha,plan_sha):
    started=time.perf_counter();p,m,plan,command,prefix=admission(bundle,protocol_sha,plan_sha)
    sys.path.insert(0,str(HERE));common=importlib.import_module('common')
    if Path(common.__file__).resolve()!=HERE/'common.py':raise ValueError('foreign parent common admission module')
    common.protocol(bundle,protocol_sha)
    owner=Path(p['owner_root']);run=Path(p['run_root'])
    if owner.exists()or run.exists():raise ValueError('owner/raw root exists; no resume or repeated launch')
    owner.mkdir(parents=True,exist_ok=False)
    write(owner/'STARTED.json',{'identity':p['identity'],'protocol_sha256':protocol_sha,'source_manifest_sha256':p['source_manifest_sha256'],
        'owner_policy':p['owner_policy'],'command_sha256':plan['command_sha256'],'execution_plan_sha256':plan_sha,
        'replay_or_resume_authorized':False,'explicit_root_single_launch_grant':True,'started_monotonic':started,'owner_deadline_monotonic':started+54840,
        'observed_parent_argv':observed_argv(),'observed_parent_cwd':str(Path.cwd().resolve()),
        'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    write(owner/'commands-verified.json',{'raw_sha256':plan['command_sha256'],'command':command,'runtime':plan['runtime'],
        'source_manifest_sha256':p['source_manifest_sha256'],'owner_bootstrap_sha256':m['source_map']['owner.py'],'all_inputs_verified_before_spawn':True})
    process=None;job=None;error=None;cleanup={'active_before':None,'active_after':None,'query_after_confirmed':False,'terminate_error':None,'query_error':None,'close_error':None};code=None;job_name='UPG-managed-api-'+uuid.uuid4().hex
    try:
        Job=load_module('managed_api_parent_job_capability',HERE/'winjob.py').Job;job=Job(job_name,create=True,memory=4*1024**3)
        with(owner/'stdout.raw').open('xb')as out,(owner/'stderr.raw').open('xb')as err:
            write(owner/'SPAWN.before.json',{'child_argv':[*prefix,'--job-name',job_name],'cwd':command['cwd'],'shell':False,
                'command_sha256':plan['command_sha256'],'source_manifest_sha256':p['source_manifest_sha256'],'all_inputs_verified_before_spawn':True})
            process=subprocess.Popen([*prefix,'--job-name',job_name],cwd=command['cwd'],stdin=subprocess.PIPE,stdout=out,stderr=err,shell=False)
            write(owner/'SPAWN.returned.json',{'pid':process.pid,'spawn_returned':True,'job_membership_not_yet_asserted':True})
            ready_deadline=min(started+54840,time.perf_counter()+15)
            while not(owner/'JOB_READY.json').is_file():
                if process.poll()is not None:raise RuntimeError('child exited before JOB_READY')
                if time.perf_counter()>=ready_deadline:raise TimeoutError('Job READY timeout; never GO')
                time.sleep(.02)
            ready_raw=(owner/'JOB_READY.json').read_bytes();ready=load_json(ready_raw)
            if ready!={'pid':process.pid,'job_membership_confirmed':True,'protocol_sha256':protocol_sha,'command_sha256':plan['command_sha256'],'job_name':job_name,
                'observed_child_argv':[*prefix,'--job-name',job_name],'observed_child_cwd':command['cwd']}:raise ValueError('exact child Job membership proof')
            admission(bundle,protocol_sha,plan_sha)
            if time.perf_counter()>=started+54840:raise TimeoutError('inclusive owner deadline before GO; never dispatch')
            write(owner/'GO.json',{'job_ready_sha256':sha(ready_raw),'command_sha256':plan['command_sha256'],'source_reverified_before_go':True})
            process.stdin.write(b'GO\n');process.stdin.flush();process.stdin.close()
            while process.poll()is None:
                if time.perf_counter()-started>=54840:raise TimeoutError('inclusive owner round deadline; outcome unknown no replay')
                if any((owner/name).stat().st_size>65536 for name in('stdout.raw','stderr.raw')):raise ValueError('owner output limit; unknown no replay')
                time.sleep(.05)
            code=process.returncode
            if code!=0:raise RuntimeError('child return not zero; no replay')
    except BaseException as problem:error=type(problem).__name__
    finally:
        if job is not None:
            try:cleanup['active_before']=active_processes(job)
            except BaseException as problem:cleanup['query_error']=type(problem).__name__
            try:job.terminate()
            except BaseException as problem:cleanup['terminate_error']=type(problem).__name__
            until=time.perf_counter()+5
            while True:
                try:cleanup['active_after']=active_processes(job);cleanup['query_after_confirmed']=True
                except BaseException as problem:cleanup['query_error']=type(problem).__name__;break
                if cleanup['active_after']==0 or time.perf_counter()>=until:break
                time.sleep(.02)
            try:job.close()
            except BaseException as problem:
                cleanup['close_error']=type(problem).__name__
                if error is None:error=type(problem).__name__
        try:child_reap=reap_owned_child(process)
        except BaseException as problem:
            child_reap={'status':'UNKNOWN_RETAINED','observed_exited':False,'returncode':None,'steps':[],
                'errors':[{'phase':'reap-handler','exception_class':type(problem).__name__}],'wall_seconds':None}
        code=child_reap['returncode']
        if error is None and child_reap['errors']:error=child_reap['errors'][0]['exception_class']
        if error is None and process is not None and not child_reap['observed_exited']:error='OwnedChildExitUnconfirmed'
        elapsed=time.perf_counter()-started;terminal=run/'terminal.json';terminal_sha=None
        try:terminal_sha=sha(terminal.read_bytes())if terminal.is_file()else None
        except BaseException as problem:
            if error is None:error=type(problem).__name__
        closed={'identity':p['identity'],'protocol_sha256':protocol_sha,'source_manifest_sha256':p['source_manifest_sha256'],
            'execution_plan_sha256':plan_sha,'terminal_sha256':terminal_sha,
            'exception_class':error,'child_pid':process.pid if process else None,'child_returncode':code,'child_observed_exited':child_reap['observed_exited'],'child_reap':child_reap,
            'job_cleanup':cleanup,'external_daemon_cleanup':'NOT_PROVEN_BY_WINDOWS_JOB','inclusive_owner_wall_seconds':elapsed,
            'round_seconds_soft':54840,'overrun':elapsed>54840,'post_deadline_cleanup_wall_is_included':True,
            'cleanup_scope':'Job membership and direct owned-child reap are separate; Docker daemon cleanup independently checked from project receipts',
            'status':'CLOSED_KNOWN_CHILD'if error is None and code==0 and child_reap['observed_exited']and terminal_sha is not None and cleanup['active_after']==0 and cleanup['terminate_error']is None and cleanup['query_error']is None else'UNKNOWN_NO_REPLAY'}
        try:write(owner/'CLOSED.json',closed)
        except BaseException as problem:
            closed['status']='UNKNOWN_NO_REPLAY';closed['close_publication_error']=type(problem).__name__
            # First publication is never repeated. This metadata-only fallback
            # cannot turn an unconfirmed owner close into an actual completion.
            try:write(owner/'OWNER-FAILURE.json',{'status':'UNKNOWN_NO_REPLAY','first_exception':error,'publication_error':type(problem).__name__})
            except BaseException:
                sys.stderr.write('OWNER_CLOSE_UNPUBLISHED_UNKNOWN_NO_REPLAY\n');sys.stderr.flush()
    return closed
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True);parser.add_argument('--protocol-sha256',required=True);parser.add_argument('--execution-plan-sha256',required=True)
    parser.add_argument('--root-launch-authorized',action='store_true');parser.add_argument('--child',action='store_true');parser.add_argument('--job-name');args=parser.parse_args()
    if args.child:
        if not args.job_name:raise ValueError('named Job required')
        return child(args.bundle,args.protocol_sha256,args.execution_plan_sha256,args.job_name)
    if not args.root_launch_authorized:raise ValueError('explicit root API launch grant absent')
    _,_,plan,command,_=admission(args.bundle,args.protocol_sha256,args.execution_plan_sha256)
    expected=[args.execution_plan_sha256 if x=='EXTERNAL_EXECUTION_PLAN_SHA256'else x for x in command['parent_argv_template']]
    if list(sys.orig_argv)!=expected or Path.cwd().resolve()!=HERE:raise ValueError('actual parent argv/cwd differs from registered command bytes')
    result=parent(args.bundle,args.protocol_sha256,args.execution_plan_sha256)
    print(json.dumps({'status':result['status'],'terminal_sha256':result['terminal_sha256'],'owner_closed_sha256':sha((Path(load_json((Path(args.bundle)/'protocol.json').read_bytes())['owner_root'])/'CLOSED.json').read_bytes())}))
    return 0 if result['status']=='CLOSED_KNOWN_CHILD'else 1
if __name__=='__main__':raise SystemExit(main())
