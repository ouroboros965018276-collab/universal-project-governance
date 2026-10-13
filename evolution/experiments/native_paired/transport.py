"""Identical child-only HTTP CLI instrumentation, with no host config changes."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import time
import uuid

PROFILE_SOURCE=Path(__file__).resolve().parents[2]/'cli_transport.py'
PROFILE=runpy.run_path(str(PROFILE_SOURCE))['profile_overrides']()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write((json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode())
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


def install(native,config,registration):
    """Intercept only registered CLI exec; compiler/planner calls pass unchanged."""
    if registration['profile']!=PROFILE:raise ValueError('unregistered child transport profile')
    def verify_sources():
        source=registration['profile_source']
        if (Path(source['path']).resolve()!=PROFILE_SOURCE or sha(PROFILE_SOURCE.read_bytes())!=source['sha256']
                or sha(Path(__file__).read_bytes())!=registration['source_sha256']):
            raise ValueError('registered child transport source changed')
    verify_sources()
    original=native.subprocess.run
    state={'sample_id':None,'records':[]}
    binary=Path(config['binary']).resolve();artifact_root=Path(config['artifact_root']).resolve()
    def run(arguments,*args,**kwargs):
        if not isinstance(arguments,(list,tuple)) or not arguments or Path(str(arguments[0])).resolve()!=binary:
            return original(arguments,*args,**kwargs)
        argv=list(map(str,arguments))
        verify_sources()
        if argv[:4]!=[str(binary),'--ask-for-approval','never','exec'] or argv[-1]!='-':
            raise ValueError('unexpected official CLI command in bounded native worker')
        if state['sample_id'] is None:raise ValueError('CLI dispatch missing pending parent sample identity')
        if any(value.startswith(('model_provider=','model_providers.','features.unbounded_connection_retries=')) for value in argv):
            raise ValueError('native release argv already selects an unreviewed provider')
        effective=argv[:-1]+[part for value in PROFILE for part in ('-c',value)]+['-']
        directory=artifact_root/'transport';path=directory/(digest({'sample_id':state['sample_id']})+'.json')
        if path.exists():raise ValueError('transport dispatch receipt already exists; no replay')
        row={'schema_version':1,'sample_id':state['sample_id'],'profile':PROFILE,
             'transport_source_sha256':registration['source_sha256'],
             'profile_source_sha256':registration['profile_source']['sha256'],'argv':effective,'argv_sha256':digest(effective),
             'original_argv_sha256':digest(argv),'status':'pending','automatic_retry':False,
             'measurement':'child HTTP overrides, evidence writes and duration included in public callback and CLI wall',
             'receipt_path':str(path)}
        atomic(path,row);state['records'].append(row)
        started=time.perf_counter()
        try:
            completed=original(effective,*args,**kwargs)
        except BaseException as error:
            row.update(status='unknown',error_type=type(error).__name__,elapsed_seconds=time.perf_counter()-started)
            atomic(path,row);raise
        row.update(status='returned',exit_code=completed.returncode,elapsed_seconds=time.perf_counter()-started,
                   stdout_sha256=sha(completed.stdout),stderr_sha256=sha(completed.stderr))
        try:atomic(path,row)
        except Exception as error:
            # Preserve the actual process result so native can retain paid usage;
            # parent will fail the incomplete instrumentation evidence after charge.
            row['evidence_error']=type(error).__name__+': '+str(error)
        return completed
    native.subprocess.run=run
    return state
