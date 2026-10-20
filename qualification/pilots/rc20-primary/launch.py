"""Future root-granted sole paid launch. No default activation or preparation."""
import argparse,datetime,hashlib,json,sys,time
from pathlib import Path
def bootstrap(bundle,protocol_sha256):
    """Verify the external protocol/map before importing any candidate module."""
    def loads(raw):
        def pairs(rows):
            result={}
            for key,value in rows:
                if key in result:raise ValueError('duplicate bootstrap JSON key')
                result[key]=value
            return result
        return json.loads(raw,object_pairs_hook=pairs)
    def digest(raw):return hashlib.sha256(raw).hexdigest()
    root=Path(__file__).resolve().parent;bundle=Path(bundle)
    raw=(bundle/'protocol.json').read_bytes()
    if digest(raw)!=protocol_sha256:raise ValueError('bootstrap protocol SHA differs')
    value=loads(raw);raw=(bundle/'assembly-source-map.json').read_bytes()
    if digest(raw)!=value['assembly_source_manifest_sha256']:raise ValueError('bootstrap map SHA differs')
    manifest=loads(raw)
    for name,expected in manifest['source_map'].items():
        if '\\'in name or ':'in name or any(p in('','..','.')for p in name.split('/')):raise ValueError('bootstrap source path')
        path=root.joinpath(*name.split('/'))
        if root not in path.resolve().parents:raise ValueError('bootstrap source escaped')
        for target in(path,*path.parents):
            if target==root.parent:break
            info=target.lstat()
            if target.is_symlink()or getattr(info,'st_file_attributes',0)&1024:raise ValueError('bootstrap linked source')
        if path.stat().st_nlink!=1 or digest(path.read_bytes())!=expected:raise ValueError('bootstrap source differs:'+name)
    if manifest['source_map'].get('launch.py')!=digest(Path(__file__).read_bytes()):raise ValueError('bootstrap entry omitted')
    return manifest
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True);parser.add_argument('--protocol-sha256',required=True)
    parser.add_argument('--root-launch-authorized',action='store_true');args=parser.parse_args()
    if not args.root_launch_authorized:raise ValueError('explicit root launch grant absent')
    started=time.perf_counter();bootstrap(args.bundle,args.protocol_sha256)
    from common import HERE,protocol,module,immutable,canonical,sha,roots
    p,m=protocol(args.bundle,args.protocol_sha256)
    RUN_ROOT,AUTH_ROOT,SUPERVISOR_ROOT=roots(p)
    if RUN_ROOT.exists()or not AUTH_ROOT.is_dir():raise ValueError('raw exists or sole parent owner absent')
    if m['source_map'].get('launch.py')!=sha(Path(__file__).read_bytes()):raise ValueError('launcher not in exact source map')
    import ctypes,os
    from ctypes import wintypes as W
    started_owner=json.loads((AUTH_ROOT/'STARTED.json').read_bytes());ready=json.loads((AUTH_ROOT/'JOB_READY.json').read_bytes());go=json.loads((AUTH_ROOT/'GO.json').read_bytes())
    if started_owner['protocol_sha256']!=args.protocol_sha256 or ready['pid']!=os.getpid()or go['job_ready_sha256']!=sha((AUTH_ROOT/'JOB_READY.json').read_bytes()):raise ValueError('sole owner READY/GO absent or differs')
    capability=module('managed_launch_job_capability','winjob.py',m);job=capability.Job(ready['job_name'])
    try:
        inside=W.BOOL();job.k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,ctypes.POINTER(W.BOOL)];job.k.IsProcessInJob.restype=W.BOOL
        if not job.k.IsProcessInJob(job.k.GetCurrentProcess(),job.handle,ctypes.byref(inside))or not inside.value:raise ValueError('launcher not inside exact parent Job')
    finally:job.close()
    immutable(AUTH_ROOT/'launch-STARTED.json',{'identity':p['identity'],'protocol_sha256':args.protocol_sha256,'source_manifest_sha256':p['source_manifest_sha256'],
        'launcher_sha256':sha(Path(__file__).read_bytes()),'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'runtime_switches':['collector.ENABLED only inside this granted launch'],
        'auditor_authorization':'UNBOUND until terminal/process exit and separate first-audit root grant','replay_or_resume_authorized':False})
    collector=module('managed_public_actual_collector','collector.py',m);vault=None;terminal=None;error=None
    def key(provider):
        nonlocal vault
        # Collector's guarded_key has already verified the durable reservation.
        if vault is None:vault=module('managed_public_dpapi_callback','credential_loader.py',m)
        return vault.load_key(provider)
    if collector.ENABLED is not False:raise ValueError('unexpected collector switch')
    collector.ENABLED=True;collector.ACTUAL_ENTRY_AUTHORIZATION=args.protocol_sha256
    try:terminal=collector.collect(args.bundle,args.protocol_sha256,key)
    except BaseException as problem:error=type(problem).__name__
    finally:collector.ENABLED=False;collector.ACTUAL_ENTRY_AUTHORIZATION='UNBOUND'
    terminal_path=RUN_ROOT/'terminal.json'
    elapsed=time.perf_counter()-started
    closed={'identity':p['identity'],'protocol_sha256':args.protocol_sha256,'source_manifest_sha256':p['source_manifest_sha256'],
        'terminal_sha256':sha(terminal_path.read_bytes())if terminal_path.is_file()else None,'exception_class':error,
        'inclusive_wall_after_terminal_publication_seconds':elapsed,'round_seconds_soft':54840,'overrun':elapsed>54840,
        'collector_restored_disabled':collector.ENABLED is False,'auditor_authorization':'UNBOUND',
        'scope':'Real wall includes setup/Git, API work, accounting tail, raw checks and terminal publication; excludes this final external fence write/process teardown.'}
    immutable(AUTH_ROOT/'launch-CLOSED.json',closed)
    print(__import__('json').dumps({'status':terminal['status']if terminal else'launch-failed','terminal_sha256':closed['terminal_sha256'],
        'launch_closed_sha256':sha((AUTH_ROOT/'launch-CLOSED.json').read_bytes()),'attempted_actor_records':terminal['completed_actor_records']if terminal else None,'independent_audit':'UNBOUND'}))
    return 0 if error is None else 1
if __name__=='__main__':raise SystemExit(main())
