"""Single finite-registry native/accounting/project/phase evidence consumer.

No model, producer adapter, Git, backend or project execution. Known mechanical
FAIL stays FAIL. Missing/unknown/late/raw mutation never becomes a success.
Actual launch remains controlled by the separately fixed owner registration.
"""
import copy
import importlib
from pathlib import Path
import sys
from managed_contract_primary import canonical, sha, validate_registry, number, valid_sha
from reader_binding_primary import HERE, require, check_source_pins

READINESS_BINDINGS = {'actual_registration':'UNBOUND', 'implementation':'SOURCE_IMPLEMENTED_PENDING_REVIEW_AND_REAL_CALIBRATION'}
DEPENDENCIES = ('raw_auditor_primary.py','reader_binding_primary.py','native_instruction_primary.py',
    'native_auditor_primary.py','project_auditor_primary.py','project_receipt_kernels_primary.py',
    'phase_auditor_primary.py','managed_contract_primary.py','frozen/fee_kernels.py','frozen/parser_kernels.py',
    'repository/evolution/project_executor.py')

def module(name):
    if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
    value = importlib.import_module(name)
    require(Path(value.__file__).resolve() == HERE/(name+'.py'), 'foreign-independent-reader-module')
    return value

def registry_for(protocol, actor_registry=None):
    registry = protocol.get('actor_registry') if actor_registry is None else actor_registry
    if 'actor_registry' in protocol:
        require(canonical(registry) == canonical(protocol['actor_registry']), 'registry-explicit-versus-protocol')
    return validate_registry(registry, registry_identity=protocol['ledger_registry_identity'])

def returned_result_matches(saved, returned, raw_sha):
    value = copy.deepcopy(returned)
    extra = value.get('receipt',{}).pop('result_file_sha256',None)
    require(extra == raw_sha and value == saved, 'returned-result-exact-original-with-explicit-file-binding')

def verify_entry(view, protocol, task, context, record, registry):
    actor_id = record['actor_id']; budget = registry[actor_id]
    pins = protocol['actor_bindings'][actor_id]
    require(set(pins) == {'task_sha256','context_sha256','system_context_sha256','registered_entry_sha256'}, 'actor-binding-exact-fields')
    require(record['provider'] == budget['provider'] and record['workflow_id'] == budget['workflow_id']
        and record['role'] == budget['role'] and record['arm'] == budget['arm'], 'immutable-actor-role-registration')
    require(record['workspace_ref'] == 'workspaces/'+budget['workflow_id']
        and record['artifact_ref'] == 'actors/'+actor_id+'/artifacts'
        and record['task_ref'] == 'actors/'+actor_id+'/task.json'
        and record['context_ref'] == 'actors/'+actor_id+'/context.json', 'fixed-actor-record-paths')
    task_sha = sha(view.raw(record['task_ref'])); context_sha = sha(view.raw(record['context_ref']))
    require(record['task_sha256'] == task_sha and record['context_sha256'] == context_sha
        and pins['context_sha256'] == context_sha, 'original-task-context-bindings')
    require(pins['task_sha256'] == task_sha if budget['role']=='source' else
        pins['task_sha256'] == 'DERIVE_VERIFIED_SOURCE_HANDOFF_V1', 'frozen-or-derived-task-binding')
    entry = record['registered_entry']
    require(set(entry) == {'skill','plan_text','system_context','input_context_sha256'}
        and all(type(entry[n]) is str for n in entry)
        and entry['input_context_sha256'] == sha(canonical(context)), 'registered-entry-exact-context')
    require(sha(canonical(entry)+b'\n') == pins['registered_entry_sha256'] == record['registered_entry_sha256']
        and entry['system_context'] == record['system_context']
        and sha(entry['system_context'].encode('utf-8')) == pins['system_context_sha256'] == record['system_context_sha256'], 'registered-package-plan-system-binding')
    timing = record['actor_timing']
    require(set(timing) == {'schema','started_monotonic','work_deadline_monotonic'}
        and timing['schema'] == 'collector-first-setup-absolute-work-deadline-v1'
        and number(timing['started_monotonic']) and number(timing['work_deadline_monotonic'])
        and timing['work_deadline_monotonic']-timing['started_monotonic'] == 180, 'first-setup-exact-absolute-deadline')
    require(record['result']['actor_timing']==timing
        and record['result']['work_deadline_monotonic']==timing['work_deadline_monotonic']
        and record['result']['settlement_deadline_monotonic']==timing['work_deadline_monotonic']+600,
        'result-same-original-absolute-actor-clock')
    plan = record['planner_receipt']
    require(set(plan) == {'ref','sha256'} and sha(view.raw(plan['ref'])) == plan['sha256'], 'original-planner-reference')
    receipt = view.json(plan['ref'])
    if protocol.get('study_kind') == 'API7_PHASE_CALIBRATION_DEVELOPMENT':
        require(receipt == {'schema_version':'public-calibration-no-runtime-planner-v1','actor_id':actor_id,
            'system_context_sha256':record['system_context_sha256'],'registered_entry_sha256':record['registered_entry_sha256'],
            'governance_planner_executed':False}, 'calibration-explicit-no-governance-planner')
    else:
        import base64
        require(receipt['schema_version'] == 'stdlib-project-runtime-planner-v7'
            and receipt['matches_expected'] is True and receipt['returncode'] == 0 and receipt['timeout'] is False
            and receipt['error'] is None and receipt['expected_plan_utf8_sha256'] == sha(entry['plan_text'].encode())
            and base64.b64decode(receipt['stdout_base64'],validate=True) == entry['plan_text'].encode()
            and base64.b64decode(receipt['stderr_base64'],validate=True) == b''
            and receipt['argv'] == [protocol['host']['python']['path'],'-B',receipt['argv'][2],'--context',str(view.path(record['context_ref'])),'--json']
            and receipt['cwd'] == str(view.root)
            and valid_sha(receipt['script_sha256']) and number(receipt['wall_seconds']) and receipt['wall_seconds'] >= 0,
            'real-fixed-runtime-planner')
        expected_script = HERE/'frozen'/('full-runtime' if budget['arm']=='full' else 'baseline-runtime')/'scripts/plan_governance.py'
        require(Path(receipt['argv'][2]).resolve() == expected_script.resolve()
            and sha(expected_script.read_bytes()) == receipt['script_sha256'], 'frozen-planner-current-bytes')

def _replay(view, protocol, workflow_spec, record, registry, *, current_disk):
    project = module('project_auditor_primary'); native = module('native_auditor_primary'); phase_reader = module('phase_auditor_primary')
    actor_id = record['actor_id']; task = view.json(record['task_ref']); context = view.json(record['context_ref'])
    verify_entry(view,protocol,task,context,record,registry)
    original = view.raw(record['result_ref']); saved = view.json(record['result_ref'])
    require(record['result_ref'] == record['artifact_ref']+'/actor.result.json' and sha(original) == record['result_sha256'], 'original-result-file-binding')
    returned_result_matches(saved,record['result'],sha(original))
    phase = phase_reader.phase_header(view,record,registry[actor_id]['cut_policy'])
    transport = native.verify_actor_transport(view.root,actor_id,saved,actor_registry=registry)
    require(transport['accounting_complete'] is True and transport['owned_request_workers_closed'] is True, 'all-owned-workers-and-accounting-closed')
    mechanical = project.verify_actor(view,actor_id,task,record['system_context'],record,[],
        actor_registry=registry,phase=phase,require_current_disk=current_disk)
    phase_proof = phase_reader.verify_phase(view,record,task,phase,files=mechanical['_replayed_files'],
        events=mechanical['_events'],traces=mechanical['_traces'],transport=transport) if phase else {
            'phase_cut_verified':False,'controlled_policy':None,'verified_final_state_sha256':saved['final_state_sha256']}
    return task,context,mechanical,transport,phase_proof

def verify_actor(*,run_root,protocol,workflow_spec,actor_record,source_record,actor_registry=None):
    pins = protocol.get('reader_source_pins',{})
    require(set(DEPENDENCIES) <= set(pins), 'complete-independent-reader-source-pins')
    check_source_pins(pins)
    registry = registry_for(protocol,actor_registry)
    project = module('project_auditor_primary'); native = module('native_auditor_primary')
    view = project.View(run_root)
    require(view.json('host-identity.json') == protocol['host'], 'registered-actual-host-identity')
    actor_id = actor_record['actor_id']; budget = registry[actor_id]
    task,context,mechanical,transport,phase = _replay(view,protocol,workflow_spec,actor_record,registry,current_disk=True)
    if budget['role'] == 'source':
        require(task == workflow_spec['source_task'] and context == workflow_spec['source_context']
            and budget['cut_policy'] == workflow_spec['cut_policy'], 'frozen-source-task-contract')
    else:
        require(type(source_record) is dict and source_record['actor_id'] in registry, 'receiver-source-original-record-required')
        source_id = source_record['actor_id']; source_budget = registry[source_id]
        require(source_budget['role']=='source' and source_budget['workflow_id']==budget['workflow_id']
            and source_budget['provider'] != budget['provider'] and source_record['workspace_ref']==actor_record['workspace_ref']
            and source_record['git_entry']['baseline_commit']==actor_record['git_entry']['baseline_commit'], 'same-physical-project-cross-provider-source')
        source_task,source_context,source_mechanical,source_transport,source_phase = _replay(view,protocol,workflow_spec,source_record,registry,current_disk=False)
        require(source_task == workflow_spec['source_task'] and source_context == workflow_spec['source_context']
            and source_phase['phase_cut_verified'] is True and source_budget['cut_policy']==workflow_spec['cut_policy'], 'receiver-source-independent-valid-cut')
        files = source_mechanical['_replayed_files']
        expected_task = copy.deepcopy(source_task)
        expected_task.update(id=workflow_spec['receiver']['task_id'],initial_files=files)
        require(task == expected_task and context == workflow_spec['receiver']['context'], 'receiver-task-actual-source-bytes-no-prior-chat')
        handoff = view.json('actors/'+actor_id+'/handoff-input.json')
        require(handoff == {'schema_version':'verified-current-project-handoff-v1','source_actor_id':source_id,
            'receiver_actor_id':actor_id,'source_result_sha256':source_record['result_sha256'],
            'workspace_ref':actor_record['workspace_ref'],'source_provider':source_budget['provider'],'receiver_provider':budget['provider'],
            'received_files':files,'received_snapshot_sha256':source_phase['verified_final_state_sha256'],
            'prior_chat_transferred':False}, 'original-handoff-byte-acknowledgement')
    ledger = view.json('accounting.json'); configuration = view.json('profile-configuration.json')
    require(ledger['actor_clocks'][actor_id] == actor_record['actor_timing'], 'ledger-same-first-setup-origin')
    ledger_proof = native.verify_ledger(view.root,ledger,actor_registry=registry,configuration=configuration,
        registry_identity=protocol['ledger_registry_identity'],finalization_policy=protocol['finalization_policy'])
    require(ledger_proof['accounting_complete'] is True, 'whole-prefix-accounting-complete')
    raw_map_sha = view.after()
    public = {n:v for n,v in mechanical.items() if not n.startswith('_')}
    public.update(phase, raw_integrity=True, accounting_complete=True,
        owned_request_workers_closed=transport['owned_request_workers_closed'],
        known_reported_tokens=transport['known_reported_tokens'], native_request_count=transport['request_count'],
        verified_raw_map_sha256=raw_map_sha, observed_whole_ledger_tokens=ledger_proof['known_reported_tokens'],
        resource_bound_is_success=False, primary_benefit_assessment='NOT_ASSESSED')
    if budget['role']=='receiver':
        public.update(verified_source_actor_id=source_id,source_phase_cut_verified=True,
            source_verified_final_state_sha256=source_phase['verified_final_state_sha256'],source_completed=False,source_graded=False)
    return public

def verify_workflow(*,run_root,protocol,workflow_spec,source_record,receiver_record=None,actor_registry=None):
    """Terminal caller verifies each physical project once, at its latest actor.

    A receiver proof includes independent historical source replay plus the
    original byte handoff. Comparing that old source to a receiver's later disk
    would be invalid. A source without a receiver still requires its current disk.
    """
    if receiver_record is None:
        proof=verify_actor(run_root=run_root,protocol=protocol,workflow_spec=workflow_spec,
            actor_record=source_record,source_record=None,actor_registry=actor_registry)
        return {'source':proof,'receiver':None,'workflow_success':proof['independent_task_pass']if workflow_spec['cut_policy']is None else False}
    proof=verify_actor(run_root=run_root,protocol=protocol,workflow_spec=workflow_spec,
        actor_record=receiver_record,source_record=source_record,actor_registry=actor_registry)
    return {'source':{'phase_cut_verified':proof['source_phase_cut_verified'],
        'verified_final_state_sha256':proof['source_verified_final_state_sha256'],
        'source_completed':False,'source_graded':False},'receiver':proof,'workflow_success':proof['independent_task_pass']}
