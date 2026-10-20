"""One outer owned-parent launch; no replay, resume, API or second ledger.

The outer clock begins before admission. Parent exit is observed via its owned
Popen handle, after which original terminal/source/tail observations are durable
before the final sample. Publication of that last observation is explicitly
outside its own operational sample; no recursive receipt or zero-cost claim.
"""
import argparse
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import HERE,protocol,roots,require,regular_bytes,strict_json,sha,immutable,source_observation,file_map,shared_module,canonical

ROUND_CAP=54840


def run_parent(argv,cwd,output_root,deadline,*,popen=subprocess.Popen,clock=time.perf_counter,sleep=time.sleep,reaper=None):
    """The single subprocess owner path. Pure tests inject a non-process handle."""
    require(clock()<deadline,'outer cap exhausted before parent spawn')
    process=None;failure=None
    try:
        with(output_root/'parent.stdout.raw').open('xb')as out,(output_root/'parent.stderr.raw').open('xb')as err:
            process=popen(argv,cwd=cwd,stdout=out,stderr=err,shell=False)
            immutable(output_root/'parent-SPAWN.returned.json',{'pid':process.pid,'argv':argv,'cwd':str(cwd),'shell':False})
            while process.poll()is None:
                if clock()>=deadline:raise TimeoutError('outer first-setup cap; never replay')
                require(all((output_root/name).stat().st_size<=65536 for name in('parent.stdout.raw','parent.stderr.raw')),'outer output cap')
                sleep(.05)
    except BaseException as error:failure=type(error).__name__
    finally:
        require(reaper is not None,'fixed generic owned-handle reaper required')
        reap=reaper(process)
        immutable(output_root/'parent-reap.json',{'schema':'primary-owned-parent-reap-v1','pid':process.pid if process else None,
            'first_exception_class':failure,'reap':reap})
    return process.pid if process else None,reap,failure


def owner_exit_value(p,closed_raw,*,parent_pid,reap,failure,observed_exit):
    closed=strict_json(closed_raw)
    exited=reap.get('observed_exited')is True
    require(type(reap.get('returncode'))is int if exited else reap.get('returncode')is None,'typed owned-parent exit')
    child_closed=closed.get('child_observed_exited')is True and closed.get('job_cleanup',{}).get('active_after')==0
    cleanup=closed.get('job_cleanup',{})
    confirmed=(exited and reap['returncode']==0 and not reap.get('errors')and failure is None
        and closed.get('status')=='CLOSED_KNOWN_CHILD'and child_closed and cleanup.get('query_after_confirmed')is True
        and all(cleanup.get(name)is None for name in('terminate_error','query_error','close_error')))
    return {'schema':'primary-owner-exit-v1','run_root':p['run_root'],'process_exited':exited,
        'worker_alive':False if confirmed else None,'exit_code':reap.get('returncode'),'confirmed':confirmed,
        'observed_exit_monotonic':observed_exit,'owner_parent_pid':parent_pid,
        'owner_closed_sha256':sha(closed_raw),
        'first_exception_class':failure,'job_and_direct_child_cleanup_confirmed':confirmed}


def run(bundle,protocol_sha,plan_sha,*,root_authorized=False):
    started=time.perf_counter() # Before protocol/source/host/setup: strict outer cap.
    require(root_authorized,'explicit exact primary root once grant absent')
    p,_=protocol(bundle,protocol_sha);raw,owner,supervisor=roots(p)
    require(not any(path.exists()for path in(raw,owner,supervisor)),'no resume/reuse of any original root')
    import owner as owner_source
    require(Path(owner_source.__file__).resolve()==HERE/'owner.py','foreign sole parent owner')
    _,_,plan,command,_=owner_source.admission(bundle,protocol_sha,plan_sha)
    require(plan['outer_cap_seconds']==ROUND_CAP,'fixed prospective outer cap')
    argv=[plan_sha if item=='EXTERNAL_EXECUTION_PLAN_SHA256'else item for item in command['parent_argv_template']]
    supervisor.mkdir(parents=False,exist_ok=False)
    immutable(supervisor/'STARTED.json',{'schema':'primary-outer-first-setup-v1','protocol_sha256':protocol_sha,
        'execution_plan_sha256':plan_sha,'started_monotonic':started,'deadline_monotonic':started+ROUND_CAP,
        'observed_argv':list(sys.orig_argv),'observed_cwd':str(Path.cwd().resolve()),'parent_argv':argv,
        'no_replay_or_resume':True,'final_measurement_metadata_publication':'unmeasured outside own last operational sample'})
    immutable(supervisor/'source.before.json',source_observation(bundle,protocol_sha))
    pid,reap,failure=run_parent(argv,HERE,supervisor,started+ROUND_CAP,reaper=owner_source.reap_owned_child)
    # The parent cannot self-report its own exit. Only its owned external handle
    # and the original child/Job receipts determine this exit bridge.
    closed_raw=regular_bytes(owner/'CLOSED.json');closed=strict_json(closed_raw)
    exit_receipt=owner_exit_value(p,closed_raw,parent_pid=pid,reap=reap,failure=failure,observed_exit=time.perf_counter())
    immutable(supervisor/'owner-exit.json',exit_receipt)
    immutable(supervisor/'source.after.json',source_observation(bundle,protocol_sha))
    immutable(supervisor/'raw-tail-map.json',file_map(raw))
    immutable(supervisor/'parent-tail-map.json',file_map(owner))
    terminal_raw=regular_bytes(raw/'terminal.json');terminal=strict_json(terminal_raw)
    require(sha(terminal_raw)==closed['terminal_sha256'],'parent original terminal after owned exit')
    configuration_raw=regular_bytes(Path(bundle)/'profile-configuration.json');configuration=strict_json(configuration_raw)
    require(sha(canonical(configuration))==p['configuration_sha256'],'owner bound profile configuration')
    publication=shared_module(bundle,'publication_primary',protocol_sha)
    # All necessary original tail writes and readbacks precede this fixed sample.
    end=time.perf_counter()
    observation=publication.owner_observation(raw,terminal,round_started_monotonic=started,owner_completed_monotonic=end,
        actor_registry=p['actor_registry'],configuration=configuration,
        registry_identity=p['ledger_registry_identity'],finalization_policy=p['finalization_policy'])
    observation.update(owner_exit_sha256=sha(regular_bytes(supervisor/'owner-exit.json')),
        parent_cleanup_confirmed=exit_receipt['confirmed'],measurement_metadata_publication_seconds=None)
    immutable(supervisor/'round-observation.json',observation)
    return 0 if exit_receipt['confirmed']and observation['round_overrun']is False else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True)
    parser.add_argument('--protocol-sha256',required=True);parser.add_argument('--execution-plan-sha256',required=True)
    parser.add_argument('--root-launch-authorized',action='store_true');args=parser.parse_args()
    raise SystemExit(run(args.bundle,args.protocol_sha256,args.execution_plan_sha256,root_authorized=args.root_launch_authorized))
