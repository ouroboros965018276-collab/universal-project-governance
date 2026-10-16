"""Single outside first-auditor process and its independently observed exit.

No model, project execution, transport or alternate reader. The external exit
receipt lives in the registered control root, outside the nine sealed reader
artifacts. Unknown exit/publication never licenses another first audit.
"""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import HERE,protocol,roots,module,regular_bytes,strict_json,sha,require,immutable,source_observation
from run_once import run_parent

AUDIT_CAP_SECONDS=1200


def qualify_publication(p,out,terminal_sha,owner_exit_sha,protocol_sha):
    out=Path(out);require(not(out/'failure-tail.json').exists(),'reader failure-tail retained')
    report_raw=regular_bytes(out/'first-audit.json');report=strict_json(report_raw)
    seal_raw=regular_bytes(out/'audit.seal.json');seal=strict_json(seal_raw)
    require(report['schema']=='primary-first-raw-audit-v1'and report['status']=='RAW_PASS'
        and report['first_error']is None and report['first_audit']is True
        and report['raw_integrity']is True and report['accounting_complete']is True,'reader did not close RAW_PASS')
    require(report['protocol_sha256']==protocol_sha and report['terminal_sha256']==terminal_sha and report['owner_exit_sha256']==owner_exit_sha
        and report['first_auditor_source_sha256']==p['first_auditor_source_sha256'],'original reader input/source bridge')
    require(seal['schema']=='primary-first-raw-audit-seal-v1'and seal.get('status')=='RAW_PASS'
        and seal.get('first_error')is None and seal['first_raw_audit_sha256']==sha(report_raw),'reader success seal/report bridge')
    expected=p['first_audit_required_artifacts'];require(len(expected)==len(set(expected))==8,'fixed eight required reader artifacts')
    require(set(seal['required_artifacts'])==set(expected),'required reader artifact set')
    require(seal['required_artifacts']['first-audit.json']==sha(report_raw),'required report equals captured original report')
    buffers={'first-audit.json':report_raw,'audit.seal.json':seal_raw}
    for name,digest in seal['required_artifacts'].items():
        require(type(name)is str and '/'not in name and '\\'not in name and ':'not in name and name not in('.','..'),'required reader artifact path')
        if name not in buffers:buffers[name]=regular_bytes(out/name)
        require(sha(buffers[name])==digest,'required reader artifact bytes')
    require({path.name for path in out.iterdir()}==set(expected)|{'audit.seal.json'},'closed nine-file reader namespace')
    require(all(regular_bytes(out/name)==captured for name,captured in buffers.items()),'captured publication readback differs')
    return sha(report_raw),sha(seal_raw)


def child(bundle,protocol_sha,terminal_sha,owner_exit_sha,auditor_sha):
    p,manifest=protocol(bundle,protocol_sha);run,owner,supervisor=roots(p)
    require(auditor_sha==p['first_auditor_source_sha256']==manifest['source_map']['first_auditor.py'],'first auditor exact source')
    require(sha(regular_bytes(run/'terminal.json'))==terminal_sha
        and sha(regular_bytes(supervisor/'owner-exit.json'))==owner_exit_sha,'registered postexit inputs')
    reader=module('primary_first_once_reader','first_auditor.py',manifest)
    require(reader.READINESS_BINDINGS=={'actual_entry_authorization':'UNBOUND'},'unexpected reader activation')
    reader.READINESS_BINDINGS['actual_entry_authorization']=reader.AUTHORIZATION
    try:return reader.audit(bundle,protocol_sha,terminal_sha,owner_exit_sha,auditor_sha,p['first_audit_root'])
    finally:reader.READINESS_BINDINGS['actual_entry_authorization']='UNBOUND'


def parent(bundle,protocol_sha,terminal_sha,owner_exit_sha,auditor_sha,*,root_authorized=False):
    start=time.perf_counter();require(root_authorized,'separate exact source postexit root once grant absent')
    p,manifest=protocol(bundle,protocol_sha);run,owner,supervisor=roots(p)
    require(auditor_sha==p['first_auditor_source_sha256']==manifest['source_map']['first_auditor.py'],'bound first reader source before spawn')
    require(sha(regular_bytes(run/'terminal.json'))==terminal_sha,'terminal exact input before reader spawn')
    exit_raw=regular_bytes(supervisor/'owner-exit.json');owner_exit=strict_json(exit_raw)
    require(sha(exit_raw)==owner_exit_sha and owner_exit['confirmed']is True and owner_exit['process_exited']is True
        and owner_exit['worker_alive']is False and owner_exit['exit_code']==0,'independent prior owner exit before reader spawn')
    out=Path(p['first_audit_root']).resolve();control=Path(p['first_audit_control_root']).resolve()
    require(p['first_audit_exit_path']==str(control/'first-audit-exit.json')and not out.exists()and not control.exists(),'new registered reader/control roots; no resume')
    paths=(HERE,Path(bundle).resolve(),run,owner,supervisor,out,control)
    require(all(a!=b and a not in b.parents and b not in a.parents for i,a in enumerate(paths)for b in paths[i+1:]
        if not(a==HERE and b==Path(bundle).resolve())), 'disjoint reader/control namespace')
    require(p['first_audit_cap_seconds']==AUDIT_CAP_SECONDS,'prospective independent audit observation cap')
    source=source_observation(bundle,protocol_sha)
    import owner as owner_source
    require(Path(owner_source.__file__).resolve()==HERE/'owner.py','fixed shared bounded reaper origin')
    argv=[p['host']['python']['path'],'-I','-B','-u',str(HERE/'audit_once.py'),'--child','--bundle',str(Path(bundle).resolve()),
        '--protocol-sha256',protocol_sha,'--terminal-sha256',terminal_sha,'--owner-exit-sha256',owner_exit_sha,'--auditor-sha256',auditor_sha]
    control.mkdir(parents=False,exist_ok=False)
    immutable(control/'STARTED.json',{'schema':'primary-first-audit-owner-v1','started_monotonic':start,
        'protocol_sha256':protocol_sha,'terminal_sha256':terminal_sha,'owner_exit_sha256':owner_exit_sha,
        'first_auditor_source_sha256':auditor_sha,'child_argv':argv,'cwd':str(HERE),'audit_cap_seconds':AUDIT_CAP_SECONDS,
        'independent_review_cost':'separate from primary paired operational wall; observed owned-process time'})
    immutable(control/'source.before.json',source)
    pid,reap,failure=run_parent(argv,HERE,control,start+AUDIT_CAP_SECONDS,reaper=owner_source.reap_owned_child)
    report_sha=None;seal_sha=None;qualification_error=None
    try:
        require(source_observation(bundle,protocol_sha)==source,'source drift across first reader process')
        immutable(control/'source.after.json',source)
        report_sha,seal_sha=qualify_publication(p,out,terminal_sha,owner_exit_sha,protocol_sha)
    except BaseException as error:qualification_error=type(error).__name__
    confirmed=(reap['observed_exited']is True and type(reap['returncode'])is int and reap['returncode']==0
        and not reap['errors']and failure is None and qualification_error is None)
    receipt={'schema':'primary-first-audit-exit-v1','process_exited':reap['observed_exited'],
        'exit_code':reap['returncode'],'worker_alive':False if reap['observed_exited']is True else None,'confirmed':confirmed,
        'observed_exit_monotonic':time.perf_counter(),'first_raw_audit_sha256':report_sha,'seal_sha256':seal_sha,
        'first_auditor_source_sha256':auditor_sha,'protocol_sha256':protocol_sha,'auditor_pid':pid,
        'first_exception_class':failure,'qualification_exception_class':qualification_error,
        'observed_independent_review_seconds':time.perf_counter()-start,'replay_or_reaudit_authorized':False}
    immutable(control/'first-audit-exit.json',receipt)
    return 0 if confirmed else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in('bundle','protocol-sha256','terminal-sha256','owner-exit-sha256','auditor-sha256'):parser.add_argument('--'+field,required=True)
    parser.add_argument('--child',action='store_true');parser.add_argument('--root-first-audit-authorized',action='store_true');args=parser.parse_args()
    if args.child:raise SystemExit(child(args.bundle,args.protocol_sha256,args.terminal_sha256,args.owner_exit_sha256,args.auditor_sha256))
    raise SystemExit(parent(args.bundle,args.protocol_sha256,args.terminal_sha256,args.owner_exit_sha256,args.auditor_sha256,
        root_authorized=args.root_first_audit_authorized))
