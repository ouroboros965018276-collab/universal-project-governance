"""Finite inclusive publication boundary, with a separately observed owner end.

Workflow end is sampled only after its raw/chain/ledger/publication receipt is
durable and read back. The terminal records that sample; its own cost is shared.
The owner samples after final terminal persistence and readback. Publication of
that final cost observation is the fixed measurement boundary, not a zero cost.
"""
import copy
import os
from pathlib import Path
import time
from managed_contract_primary import canonical, sha, number, valid_sha, derive_caps
from reader_binding_primary import require, owned_raw

MEASUREMENT_BOUNDARY = 'owner-after-final-terminal-durable-readback-before-final-cost-observation-publication-v1'
SHARED_ALLOCATION = 'equal-registered-workflow-share-v1'

def immutable(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(value)+b'\n'
    with path.open('xb')as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    require(owned_raw(path)==raw,'publication-original-readback')
    return sha(raw)

def finalize_workflow(run_root,workflow_id,started,chain_sha256,ledger,*,clock=time.perf_counter):
    require(number(started)and valid_sha(chain_sha256),'workflow-publication-arguments')
    cap=ledger.caps['workflow_seconds_soft'][workflow_id]
    ledger.refresh_tail()
    before=clock()
    require(number(before)and before>=started,'workflow-monotonic-before-publication')
    ref='workflow-publication/'+workflow_id+'.json'
    record={'schema_version':'inclusive-workflow-publication-v1','workflow_id':workflow_id,
        'workflow_started_monotonic':started,'before_publication_monotonic':before,
        'chain_record_sha256':chain_sha256,'ledger_before_publication_sha256':sha(owned_raw(ledger.path)),
        'limit_seconds':cap,'measurement_boundary':MEASUREMENT_BOUNDARY}
    digest=immutable(Path(run_root)/ref,record)
    end=clock()  # Includes this publication and its durable readback.
    require(number(end)and end>=before,'workflow-monotonic-after-publication')
    observation={'workflow_id':workflow_id,'started_monotonic':started,'completed_monotonic':end,
        'inclusive_seconds':end-started,'publication_ref':ref,'publication_sha256':digest,
        'chain_record_sha256':chain_sha256,'limit_seconds':cap,'overrun':end-started>=cap}
    if observation['overrun']:
        ledger.stop('inclusive-workflow-publication-overrun-global-stop')
    return observation

def owner_observation(run_root,terminal,*,round_started_monotonic,owner_completed_monotonic,actor_registry,
                      configuration,registry_identity,finalization_policy):
    """Pure construction by the outer owner after the final durable terminal."""
    run=Path(run_root)
    require(number(round_started_monotonic)and number(owner_completed_monotonic)
        and owner_completed_monotonic>=round_started_monotonic,'owner-round-monotonic-interval')
    require(owned_raw(run/'terminal.json')==canonical(terminal)+b'\n','owner-after-final-terminal-exact')
    caps=derive_caps(actor_registry,configuration,registry_identity=registry_identity,finalization_policy=finalization_policy)
    observations=terminal['workflow_finalization_observations']
    seen=set();previous=round_started_monotonic;total=0.;workflows={}
    for observation in observations:
        workflow=observation['workflow_id']
        require(workflow in caps['workflow_seconds_soft']and workflow not in seen,'registered-unique-workflow-cost')
        seen.add(workflow)
        start,end=observation['started_monotonic'],observation['completed_monotonic']
        require(number(start)and number(end)and previous<=start<=end<=owner_completed_monotonic
            and observation['inclusive_seconds']==end-start,'nonoverlapping-inclusive-workflow-interval')
        before=owned_raw(run/observation['publication_ref'])
        require(sha(before)==observation['publication_sha256'],'original-workflow-publication')
        from managed_contract_primary import strict_json
        record=strict_json(before)
        require(record['workflow_id']==workflow and record['workflow_started_monotonic']==start
            and start<=record['before_publication_monotonic']<=end
            and record['chain_record_sha256']==observation['chain_record_sha256']
            and sha(owned_raw(run/'chains'/(workflow+'.json')))==record['chain_record_sha256']
            and record['limit_seconds']==caps['workflow_seconds_soft'][workflow]
            and observation['limit_seconds']==record['limit_seconds']
            and observation['overrun']is(end-start>=record['limit_seconds']), 'exact-workflow-publication-interval')
        total+=end-start;previous=end;workflows[workflow]=end-start
    wall=owner_completed_monotonic-round_started_monotonic
    shared=wall-total
    require(shared>=0,'shared-cost-cannot-be-negative-or-double-counted')
    denominator=len(caps['workflow_seconds_soft'])
    # Missing/unfinished workflows retain null. No observed future work is zero.
    attributed={key:(workflows[key]+shared/denominator if key in workflows else None)
                for key in caps['workflow_seconds_soft']}
    return {'schema_version':'primary-owner-inclusive-round-observation-v1','measurement_boundary':MEASUREMENT_BOUNDARY,
        'shared_allocation':SHARED_ALLOCATION,'registered_workflow_denominator':denominator,
        'round_started_monotonic':round_started_monotonic,'owner_completed_monotonic':owner_completed_monotonic,
        'terminal_sha256':sha(owned_raw(run/'terminal.json')),'runtime_inclusive_seconds':wall,
        'observed_workflow_seconds':workflows,'shared_inclusive_seconds':shared,
        'attributed_inclusive_workflow_seconds':attributed,'round_limit_seconds':caps['round_seconds_soft'],
        'round_overrun':wall>=caps['round_seconds_soft'],
        'all_workflows_observed':len(workflows)==denominator,
        'last_cost_observation_publication_seconds':None,'research_preparation_seconds':None,
        'independent_review_seconds':None,'total_research_net_benefit':'UNASSESSED'}

def observe_owner_completion(run_root,terminal,*,round_started_monotonic,actor_registry,configuration,
                             registry_identity,finalization_policy,clock=time.perf_counter):
    """Called after collect returns/raises and its terminal has been persisted.

    Reads the final bytes before sampling. No process or task is started here.
    An owner must preserve this exact boundary in its prospectively fixed code.
    """
    require(owned_raw(Path(run_root)/'terminal.json')==canonical(terminal)+b'\n','owner-terminal-before-end-sample')
    end=clock()
    return owner_observation(run_root,terminal,round_started_monotonic=round_started_monotonic,
        owner_completed_monotonic=end,actor_registry=actor_registry,configuration=configuration,
        registry_identity=registry_identity,finalization_policy=finalization_policy)
