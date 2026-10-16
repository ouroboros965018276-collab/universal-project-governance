"""Prospective 54-workflow scheduler, disabled until every dependency is bound.

It schedules one current physical project per workflow. API7 owns transport
and repository delivery, the primary ledger owns durable budgets, and the
independent auditor owns raw reconstruction. No fixture/reference is imported.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import order_primary
if Path(order_primary.__file__).resolve() != HERE / 'order_primary.py':
    raise ValueError('foreign primary order module')
from order_primary import ARMS, PROVIDERS, COUNTS, CUT_POLICIES, make_order, actor_registry
LOCAL = HERE
ENABLED = False
ACTUAL_ENTRY_AUTHORIZATION = 'UNBOUND'
ANALYSIS_REGISTRATION_SHA256 = '50b5d41812424c1c0cb2bb950473546bd15cf0fc12ca9dace0f410da0767caec'
POLICY = 'work-deadline-accounting-only-settlement-600s-v1'
PROFILE = 'thinking-disabled-deepseek-pro-mimo-flash-8192-v1'
BACKEND = 'docker-cpython-project-v1'
BROKER_PROFILE = 'stdlib-python-project-v1'
CONNECT_RETRY_POLICY = 'confirmed-pre-http-connect-once-v1'
ATTENTION = 'Keep the response concise and avoid unnecessary engineering.'
TIMING_SCHEMA = 'collector-first-setup-absolute-work-deadline-v1'
clock = time.perf_counter


class PrimaryUnbound(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_json(raw):
    def pairs(items):
        value = {}
        for name, item in items:
            if name in value:
                raise ValueError('duplicate JSON key')
            value[name] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda unused: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def read_json(path):
    return parse_json(Path(path).read_bytes())


def immutable(path, value):
    raw = canonical(value) + b'\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('immutable readback differs')
    return sha(raw)


def verify_sources(bundle, protocol):
    source_raw = (Path(bundle) / 'source-map.json').read_bytes()
    if sha(source_raw) != protocol['source_manifest_sha256']:
        raise ValueError('external source manifest differs')
    source_manifest = parse_json(source_raw)
    if type(source_manifest.get('source_map')) is not dict or not source_manifest['source_map']:
        raise PrimaryUnbound('empty source closure')
    for name, digest in source_manifest['source_map'].items():
        if (type(name) is not str or '\\' in name or ':' in name
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('source reference is not relative')
        path = HERE.joinpath(*name.split('/'))
        for parent in (path, *path.parents):
            if parent == HERE.parent:
                break
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
                raise ValueError('linked source namespace')
        if sha(path.read_bytes()) != digest:
            raise ValueError('source differs')
    return source_manifest


def require_registration(bundle, expected_protocol_sha256):
    # No run-root creation, import or key access before explicit root authority.
    if ENABLED is not True or ACTUAL_ENTRY_AUTHORIZATION == 'UNBOUND':
        raise PrimaryUnbound('primary source has no actual root authorization')
    bundle = Path(bundle)
    raw = (bundle / 'protocol.json').read_bytes()
    if sha(raw) != expected_protocol_sha256:
        raise ValueError('protocol external SHA differs')
    protocol = parse_json(raw)
    if (protocol.get('schema_version') != 'primary-managed-54-workflows-v1'
            or protocol.get('counts') != COUNTS or protocol.get('arms') != list(ARMS)
            or protocol.get('providers') != list(PROVIDERS)
            or protocol.get('analysis_registration_sha256') != ANALYSIS_REGISTRATION_SHA256
            or protocol.get('actor_caps') != {'seconds': 180, 'requests': 12, 'tools': 32, 'minimum_dispatch_seconds': 15}
            or protocol.get('settlement_policy') != POLICY or protocol.get('settlement_max_seconds') != 600
            or protocol.get('study_class') != 'DEVELOPMENT'
            or protocol.get('fixture_backend_qualification') != 'KNOWN_INDEPENDENT_FIXED_CONTROLS_PASS'
            or protocol.get('api7_real_calibration') != 'KNOWN_INDEPENDENT_NEW_HOOK_PATHS_PASS'
            or protocol.get('inclusive_publication_accounting') != 'BOUND_OWNER_OBSERVED_WORKFLOW_AND_SHARED_COST_V1'):
        raise PrimaryUnbound('primary boundaries or independent prerequisites remain unbound')
    for name in ('api_source_sha256', 'ledger_source_sha256', 'raw_auditor_source_sha256', 'native_auditor_source_sha256', 'project_auditor_source_sha256',
                 'phase_auditor_source_sha256', 'fixture_binding_sha256', 'order_sha256',
                 'contexts_sha256', 'workflow_specs_sha256', 'source_manifest_sha256', 'owner_closure_sha256'):
        if re.fullmatch('[0-9a-f]{64}', protocol.get(name, '')) is None:
            raise PrimaryUnbound('required prospective source binding absent')
    verify_sources(bundle, protocol)
    values = {'protocol': protocol}
    for filename, field, key in [('workflow-order.json', 'order_sha256', 'order'),
                                  ('workflow-specs.json', 'workflow_specs_sha256', 'specs'),
                                  ('arm-contexts.json', 'contexts_sha256', 'contexts')]:
        raw = (bundle / filename).read_bytes()
        if sha(raw) != protocol[field]:
            raise ValueError('registered bundle differs')
        values[key] = parse_json(raw)
    order, specs = values['order'], values['specs']['workflows']
    headers = [{'case_id': row['case_id'], 'cut_policy': row['cut_policy']} for row in specs]
    if make_order(headers, order['seed']) != order:
        raise ValueError('fair registered workflow order differs')
    values['actors'] = actor_registry(order)
    if protocol.get('actor_registry') != values['actors']:
        raise PrimaryUnbound('primary complete finite map not frozen in protocol')
    registry_identity = protocol.get('ledger_registry_identity')
    expected_identity = {'source_sha256': sha((HERE / 'order_primary.py').read_bytes()),
                         'actor_registry_sha256': sha(canonical(values['actors'])), 'expected_actor_count': 66}
    if registry_identity != expected_identity:
        raise PrimaryUnbound('primary immutable actor registry/source/count not bound')
    if (len({row['block_id'] for row in values['actors'].values()}) != 18
            or len({row['workflow_id'] for row in values['actors'].values()}) != 54):
        raise ValueError('primary block/workflow denominator differs')
    from managed_contract_primary import derive_caps, FINALIZATION_POLICY
    from publication_primary import MEASUREMENT_BOUNDARY, SHARED_ALLOCATION
    if (protocol.get('finalization_policy') != FINALIZATION_POLICY
            or protocol.get('cost_measurement_boundary') != MEASUREMENT_BOUNDARY
            or protocol.get('shared_cost_allocation') != SHARED_ALLOCATION):
        raise PrimaryUnbound('inclusive publication boundary and fixed shared allocation absent')
    configuration_raw = (bundle / 'profile-configuration.json').read_bytes()
    configuration = parse_json(configuration_raw)
    if sha(canonical(configuration)) != protocol['configuration_sha256']:
        raise ValueError('registered profile configuration differs')
    if protocol['round_caps'] != derive_caps(values['actors'], configuration,
            registry_identity=registry_identity, finalization_policy=protocol['finalization_policy']):
        raise ValueError('prospective complete-map caps differ')
    if set(protocol.get('actor_bindings', {})) != set(values['actors']):
        raise PrimaryUnbound('complete actor evidence bindings missing')
    values['configuration'] = configuration
    return values


def validate_arm_contexts(specs, contexts, build_prompt):
    """C11 context construction and attention-only baseline equality remain fixed."""
    for spec in specs:
        for role in ('source', 'receiver'):
            if role == 'receiver' and spec['cut_policy'] is None:
                continue
            context = spec['source_context'] if role == 'source' else spec['receiver']['context']
            entries = contexts['cases'][spec['case_id']][role]
            if set(entries) != set(ARMS):
                raise ValueError('exact three arm contexts required')
            for arm in ARMS:
                entry = entries[arm]
                system = build_prompt(entry['skill'], entry['plan_text'], '', terminal_report='native-tool', execution_backend=BACKEND)
                if arm == 'attention':
                    system += '\n\n' + ATTENTION
                if (entry['system_context'] != system or entry['input_context_sha256'] != sha(canonical(context))
                        or entry['skill_sha256'] != sha(entry['skill'].encode('utf-8'))
                        or entry['plan_sha256'] != sha(entry['plan_text'].encode('utf-8'))
                        or entry['system_sha256'] != sha(system.encode('utf-8'))):
                    raise ValueError('arm context bytes or payload binding differs')
            baseline, attention = entries['rc19'], entries['attention']
            if (baseline['skill'], baseline['plan_text']) != (attention['skill'], attention['plan_text']):
                raise ValueError('attention arm changed baseline package or plan')


def derive_receiver(spec, files):
    """The source's verified current bytes replace only initial_files and id."""
    source, receiver = spec['source_task'], spec['receiver']
    if spec['cut_policy'] not in CUT_POLICIES or type(receiver) is not dict:
        raise ValueError('receiver requires a controlled source contract')
    if set(receiver) != {'task_id', 'context'} or type(receiver['task_id']) is not str:
        raise ValueError('receiver immutable descriptor')
    if not set(files) <= set(source['initial_files']) | set(source['writable_files']):
        raise ValueError('receiver namespace outside registered source')
    missing = set(source['initial_files']) - set(files)
    if not missing <= set(source['writable_files']):
        raise ValueError('receiver mandatory protected file missing')
    if any(files.get(name) != text for name, text in source['initial_files'].items() if name not in source['writable_files']):
        raise ValueError('receiver cannot rebaseline protected bytes')
    task = copy.deepcopy(source)
    task.update(id=receiver['task_id'], initial_files=copy.deepcopy(files))
    if not set(task.get('required_read_paths', [])) <= set(files):
        raise ValueError('receiver required read path is missing')
    return task


def source_eligible(spec, result, raw):
    return (spec['cut_policy'] in CUT_POLICIES and raw.get('raw_integrity') is True
        and raw.get('accounting_complete') is True and raw.get('phase_cut_verified') is True
        and raw.get('controlled_policy') == spec['cut_policy']
        and raw.get('owned_request_workers_closed') is True
        and all(result.get(key) is False for key in ('unknown_usage', 'execution_state_unknown', 'execution_infrastructure_failed', 'work_deadline_reached'))
        and result.get('status') == 'controlled-phase-stop-unfinished'
        and result.get('quality', {}).get('task_success') is None
        and result.get('quality', {}).get('source_completed') is False
        and result.get('quality', {}).get('source_graded') is False
        and type(result.get('final_state_sha256')) is str
        and re.fullmatch('[0-9a-f]{64}', result['final_state_sha256']) is not None
        and raw.get('verified_final_state_sha256') == result['final_state_sha256'])


def strict_success(result, raw):
    return (raw.get('raw_integrity') is True and raw.get('accounting_complete') is True
        and raw.get('independent_task_pass') is True and raw.get('owned_request_workers_closed') is True
        and result.get('status') == 'completed'
        and all(result.get(key) is False for key in ('unknown_usage', 'execution_state_unknown', 'execution_infrastructure_failed', 'work_deadline_reached')))


def final_stop_reason(result, raw):
    if result.get('unknown_usage') is True or raw.get('accounting_complete') is not True:
        return 'unknown-accounting-global-stop'
    if result.get('execution_state_unknown') is True or result.get('execution_infrastructure_failed') is True:
        return 'unknown-project-or-infrastructure-global-stop'
    if raw.get('raw_integrity') is not True:
        return 'raw-integrity-global-stop'
    if raw.get('owned_request_workers_closed') is not True:
        return 'owned-worker-lifecycle-unconfirmed-global-stop'
    return None


def phase_guard(api, artifacts, policy):
    def guard(observed):
        if observed.get('policy_id') != policy:
            raise ValueError('registered cut policy differs')
        authorization = dict(copy.deepcopy(observed), kind='controlled-phase-stop-authorization')
        relative = 'control/phase-stop-authorization.json'
        identity = immutable(Path(artifacts) / relative, authorization)
        return api.ControlledPhaseStopRequested(relative, identity)
    return guard


def _load_runtime():
    root = HERE / 'repository'
    if 'evolution' in sys.modules and Path(sys.modules['evolution'].__file__).resolve() != (root / 'evolution/__init__.py').resolve():
        raise ValueError('foreign evolution package')
    sys.path.insert(0, str(root))
    from evolution import provider_tools, engineering_broker
    from evolution.tool_campaign import build_prompt
    import ledger_primary
    import raw_auditor_primary
    return provider_tools, engineering_broker, ledger_primary, raw_auditor_primary, build_prompt


def collect(bundle, run_root, expected_protocol_sha256, lazy_key_loader):
    """One frozen schedule; no retry/resume, fallback, model grader or registry creation."""
    round_first_start = clock()
    values = require_registration(bundle, expected_protocol_sha256)
    protocol, order, specs, contexts, actors = (values[key] for key in ('protocol', 'order', 'specs', 'contexts', 'actors'))
    api, broker, ledger_source, auditor, build_prompt = _load_runtime()
    if auditor.READINESS_BINDINGS.get('actual_registration') == 'UNBOUND':
        raise PrimaryUnbound('independent raw consumer is not registered')
    validate_arm_contexts(specs['workflows'], contexts, build_prompt)
    specs = {spec['case_id']: spec for spec in specs['workflows']}
    for spec in specs.values():
        broker.validate_task(copy.deepcopy(spec['source_task']))
    run = Path(run_root).resolve()
    if str(run) != protocol['run_root'] or run.exists():
        raise ValueError('new fixed one-use actual root required')
    run.mkdir(parents=False, exist_ok=False)
    immutable(run / 'host-identity.json', protocol['host'])
    immutable(run / 'profile-configuration.json', values['configuration'])
    immutable(run / 'STARTED.json', {'protocol_sha256': expected_protocol_sha256, 'round_first_start': round_first_start,
        'counts': COUNTS, 'replay_or_resume_authorized': False})
    ledger = ledger_source.Ledger(run / 'accounting.json', configuration=values['configuration'],
        actor_registry=actors, registration_binding={'protocol_sha256': expected_protocol_sha256,
            'order_sha256': protocol['order_sha256'], 'fixture_binding_sha256': protocol['fixture_binding_sha256'],
            'analysis_registration_sha256': ANALYSIS_REGISTRATION_SHA256}, caps=protocol['round_caps'],
        finalization_policy=protocol['finalization_policy'],
        registry_identity=protocol['ledger_registry_identity'],
        clock=clock, started_monotonic=round_first_start,
        connect_retry_policy=ledger_source.CONNECT_RETRY_POLICY)
    from publication_primary import finalize_workflow
    records, chains, publications, active_role, status = {}, [], [], None, 'running'
    first_error, unknown, last_workflow = None, False, None
    try:
        for workflow in order['workflows']:
            if ledger.state['status'] != 'running':
                break
            spec = specs[workflow['case_id']]
            workflow_start = clock()  # Before actor admission, setup or any derived receiver state.
            project, source, baseline = run / 'workspaces' / workflow['workflow_id'], None, None
            chain = dict(workflow, workflow_started_monotonic=workflow_start, source_eligible=False,
                         workflow_success=False, actor_record_refs=[], status='source-entered')
            last_workflow = chain
            for role in ('source', 'receiver'):
                if role == 'receiver' and (spec['cut_policy'] is None or not chain['source_eligible']):
                    break
                if clock()-workflow_start >= ledger.caps['workflow_seconds_soft'][workflow['workflow_id']]:
                    ledger.stop('inclusive-workflow-budget-before-actor-setup-global-stop')
                    break
                actor_id, provider = workflow[role + '_actor_id'], workflow[role + '_provider']
                actor_start = clock()  # The same absolute origin is sent to ledger and API7.
                timing = {'schema': TIMING_SCHEMA, 'started_monotonic': actor_start,
                          'work_deadline_monotonic': actor_start + 180}
                active_role = {'actor_id': actor_id, 'workflow_id': workflow['workflow_id'], 'role': role,
                               'timing': timing, 'phase': 'first-setup', 'api_invoked': False}
                ledger.start_actor(actor_id, timing)
                verify_sources(bundle, protocol)
                directory, artifacts = run / 'actors' / actor_id, run / 'actors' / actor_id / 'artifacts'
                directory.mkdir(parents=True, exist_ok=False)
                if role == 'source':
                    task, context = copy.deepcopy(spec['source_task']), spec['source_context']
                    project.mkdir(parents=True, exist_ok=False)
                    for name, text in task['initial_files'].items():
                        path = project / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open('xb') as stream:
                            stream.write(text.encode('utf-8'))
                else:
                    admitted = auditor.verify_actor(run_root=run, protocol=protocol, workflow_spec=spec,
                        actor_record=source, source_record=None)
                    if not source_eligible(spec, source['result'], admitted):
                        raise ValueError('source independent raw/phase admission is no longer current')
                    snapshot = source['result']['final_state_snapshot']
                    files = read_received_files(project, snapshot, spec['source_task'])
                    task, context = derive_receiver(spec, files), spec['receiver']['context']
                    if {name: sha(text.encode('utf-8')) for name, text in files.items()} != snapshot:
                        raise ValueError('receiver actual byte snapshot differs')
                    chain['receiver_received_state_sha256'] = sha(canonical(snapshot))
                    immutable(directory / 'handoff-input.json', {
                        'schema_version':'verified-current-project-handoff-v1','source_actor_id':source['actor_id'],
                        'receiver_actor_id':actor_id,'source_result_sha256':source['result_sha256'],
                        'workspace_ref':project.relative_to(run).as_posix(),
                        'source_provider':source['provider'],'receiver_provider':provider,
                        'received_files':files,'received_snapshot_sha256':sha(canonical(snapshot)),
                        'prior_chat_transferred':False})
                broker.validate_task(task)
                immutable(directory / 'task.json', task)
                immutable(directory / 'context.json', context)
                entry = contexts['cases'][spec['case_id']][role][workflow['arm']]
                registered_entry = {name:entry[name] for name in ('skill','plan_text','system_context','input_context_sha256')}
                active_role['phase'] = 'runtime-planner'
                planner = runtime_plan(workflow['arm'], directory / 'context.json', protocol['host']['python']['path'],
                    run, run / 'planner-receipts' / (actor_id + '.json'), entry['plan_text'], entry['planner_source_sha256'])
                active_role['phase'] = 'git-entry'
                git_ref = 'git-baselines/' + workflow['workflow_id'] + '/' + role + '.json'
                git = dict(git_entry(project, task, protocol['host']['git']['path'], run / git_ref, baseline))
                baseline, git['ref'] = git['baseline_commit'], git_ref
                task_sha = sha(canonical(task))
                def before(metadata):
                    if metadata['input_task_sha256'] != task_sha or metadata['work_deadline_monotonic'] != timing['work_deadline_monotonic']:
                        raise ValueError('same actor deadline/task binding required')
                    if clock()-workflow_start >= ledger.caps['workflow_seconds_soft'][workflow['workflow_id']]:
                        ledger.stop('inclusive-workflow-budget-before-reserve-global-stop')
                        raise ledger_source.StudyStop(ledger.state['status'])
                    if timing['work_deadline_monotonic'] - clock() < 15:
                        prior = ledger.path.read_bytes()
                        proof = {'kind': 'registered-primary-window-refusal-v1', 'actor_id': actor_id,
                            'request_metadata': copy.deepcopy(metadata), 'actor_budget': actors[actor_id],
                            'remaining_seconds': timing['work_deadline_monotonic'] - clock(),
                            'ledger_before_sha256': sha(prior), 'ledger_before_raw_utf8': prior.decode('utf-8'),
                            'ledger_after_sha256': sha(ledger.path.read_bytes()), 'request_slot_delta': 0,
                            'key_loader_invoked': False, 'http_dispatch_started': False}
                        immutable(artifacts / 'guards' / ('%02d.json' % metadata['request_index']), proof)
                        raise ledger_source.StudyStop('registered-primary-dispatch-window-before-reserve')
                    return ledger.before(actor_id, provider, actors[actor_id]['model'], metadata)
                def after(metadata):
                    return ledger.after(actor_id, provider, actors[actor_id]['model'], metadata)
                kwargs = {'max_requests': 12, 'timeout_seconds': 180, 'response_json_mode': False, 'thinking': 'disabled',
                    'profile_id': PROFILE, 'execution_backend': BACKEND, 'broker_profile_id': BROKER_PROFILE,
                    'before_request': before, 'after_request': after, 'actor_timing': timing, 'settlement_policy': POLICY,
                    'connect_retry_policy': CONNECT_RETRY_POLICY, 'tool_feedback_policy': None}
                if role == 'source' and spec['cut_policy'] is not None:
                    kwargs.update(controlled_phase_stop_policy=spec['cut_policy'],
                                  controlled_phase_stop_guard=phase_guard(api, artifacts, spec['cut_policy']))
                active_role.update(phase='api-inflight', api_invoked=True)
                result = api.run_actor(provider, actors[actor_id]['model'], task, project, artifacts,
                    protocol['host']['git']['path'], entry['system_context'],
                    ledger.guarded_key(actor_id, lazy_key_loader), **kwargs)
                active_role['phase'] = 'raw-verification'
                record = {'schema_version': 'primary-managed-actor-v1', 'actor_id': actor_id,
                    'workflow_id': workflow['workflow_id'], 'role': role, 'provider': provider, 'arm': workflow['arm'],
                    'task_ref': (directory / 'task.json').relative_to(run).as_posix(), 'task_sha256': sha(canonical(task) + b'\n'),
                    'context_ref': (directory / 'context.json').relative_to(run).as_posix(),
                    'context_sha256': sha((directory / 'context.json').read_bytes()),
                    'workspace_ref': project.relative_to(run).as_posix(), 'artifact_ref': artifacts.relative_to(run).as_posix(),
                    'git_entry': git, 'planner_receipt': planner, 'actor_timing': timing, 'result': result,
                    'registered_entry': registered_entry, 'registered_entry_sha256': sha(canonical(registered_entry)+b'\n'),
                    'system_context':entry['system_context'], 'system_context_sha256':sha(entry['system_context'].encode('utf-8')),
                    'result_ref': (artifacts / 'actor.result.json').relative_to(run).as_posix(),
                    'result_sha256': sha((artifacts / 'actor.result.json').read_bytes())}
                raw = auditor.verify_actor(run_root=run, protocol=protocol, workflow_spec=spec,
                    actor_record=record, source_record=source)
                record['raw_verification_receipt'] = {'ref': (directory / 'raw-verification.json').relative_to(run).as_posix(),
                    'sha256': immutable(directory / 'raw-verification.json', raw)}
                record['observed_actor_wall_before_record_publication_seconds'] = clock() - actor_start
                ref = 'actor-records/' + actor_id + '.json'
                immutable(run / ref, record)
                records[actor_id] = record
                chain['actor_record_refs'].append(ref)
                active_role = None
                ledger.refresh_tail()
                verify_sources(bundle, protocol)
                reason = final_stop_reason(result, raw)
                if reason:
                    ledger.stop(reason)
                    unknown = True
                if role == 'source':
                    source = record
                    chain['source_eligible'] = source_eligible(spec, result, raw) if spec['cut_policy'] else False
                    chain['workflow_success'] = strict_success(result, raw) if spec['cut_policy'] is None else False
                else:
                    chain['workflow_success'] = strict_success(result, raw)
                if ledger.state['status'] != 'running':
                    break
            chain['status'] = 'completed' if chain['workflow_success'] else 'known-workflow-failure'
            chain['observed_wall_before_chain_publication_seconds'] = clock() - workflow_start
            chain_sha = immutable(run / 'chains' / (workflow['workflow_id'] + '.json'), chain)
            chains.append(chain)
            publications.append(finalize_workflow(run,workflow['workflow_id'],workflow_start,chain_sha,ledger,clock=clock))
        status = 'completed' if len(chains) == 54 and ledger.state['status'] == 'running' else ledger.state['status']
    except BaseException as error:
        first_error = type(error).__name__
        unknown = unknown or bool(ledger.state.get('pending')) or (active_role is not None and active_role['api_invoked'])
        status = 'collector-failure-global-stop'
        ledger.stop(status)
        raise
    finally:
        if active_role is not None:
            active_role['observed_unfinished_prefix_seconds'] = clock() - active_role['timing']['started_monotonic']
        source_exact = False
        try:
            verify_sources(bundle, protocol)
            source_exact = True
        except (OSError, ValueError):
            status, unknown = 'source-drift-global-stop', True
        ledger.refresh_tail()
        if ledger.state['status'] != 'running':
            status = ledger.state['status']
        else:
            ledger.stop(status)
        terminal = {'schema_version': 'primary-managed-terminal-v1', 'status': status, 'first_error_class': first_error,
            'source_final_exact': source_exact, 'planned_counts': COUNTS, 'completed_actor_records': len(records),
            'completed_workflow_records': len(chains), 'unfinished_actor': active_role,
            'last_workflow': last_workflow['workflow_id'] if last_workflow else None, 'unknown': unknown,
            'ledger_pending': bool(ledger.state.get('pending')), 'ledger_persistence_fault': getattr(ledger, 'failure_observation', None),
            'round_first_start_monotonic': round_first_start, 'before_terminal_publication_monotonic': clock(),
            'inclusive_owner_publication_observations_required': True, 'primary_benefit_assessment': 'NOT_ASSESSED'}
        terminal['workflow_finalization_observations'] = publications
        immutable(run / 'terminal.json', terminal)
    return terminal


def git_entry(project,task,git_binary,path,baseline=None):
    from evolution.tool_broker import git_command
    rows=[];path=Path(path)
    def command(*args):
        start=clock();prefix=path.stem+'.command-%02d'%(len(rows)+1)
        before=immutable(path.with_name(prefix+'.before.json'),{'schema_version':'stdlib-project-git-command-before-v7',
            'git_binary':str(git_binary),'helper_arguments':list(args),'cwd':str(project),
            'scope':'fixed canonical git_command adds its pinned safe flags; not proof of completion'})
        try:value=git_command(git_binary,project,*args)
        except BaseException as error:
            partial_out=getattr(error,'stdout',None);partial_err=getattr(error,'stderr',None)
            immutable(path.with_name(prefix+'.error.json'),{'schema_version':'stdlib-project-git-command-error-v7',
                'before_receipt_sha256':before,'exception_class':type(error).__name__,'completion':'UNCONFIRMED',
                'argv':getattr(error,'cmd',None),
                'stdout_partial_base64':base64.b64encode(partial_out).decode() if type(partial_out) is bytes else None,
                'stderr_partial_base64':base64.b64encode(partial_err).decode() if type(partial_err) is bytes else None,
                'wall_seconds':clock()-start})
            raise
        row={'argv':list(value.args),'cwd':str(project),'returncode':value.returncode,
            'stdout_base64':base64.b64encode(value.stdout).decode(),'stderr_base64':base64.b64encode(value.stderr).decode(),
            'stdout_sha256':sha(value.stdout),'stderr_sha256':sha(value.stderr),'wall_seconds':clock()-start,
            'before_receipt_sha256':before}
        row['after_receipt_sha256']=immutable(path.with_name(prefix+'.after.json'),row)
        rows.append(row)
        if value.returncode:raise ValueError('registered Git setup failed')
        return value.stdout
    if baseline is None:
        command('init','--quiet');command('config','user.name','UPG Development Fixture')
        command('config','user.email','upg-development@example.invalid')
        command('add','--',*sorted(task['initial_files']));command('commit','--quiet','-m','Registered source initial snapshot')
    revision=command('rev-parse','HEAD').decode().strip()
    if baseline is not None and revision!=baseline:raise ValueError('receiver Git baseline changed')
    command('status','--porcelain=v1','--untracked-files=all')
    value={'schema_version':'stdlib-project-chain-git-entry-v7','baseline_commit':revision,
        'initial_commit_created':baseline is None,'commands':rows}
    return {'sha256':immutable(path,value),'baseline_commit':revision}


def read_received_files(project,expected,source_task):
    """Read the verified source namespace, including confirmed absence, on actual disk."""
    from evolution.tool_broker import MAX_FILES,MAX_FILE_BYTES,MAX_TOTAL_BYTES,relative
    project=Path(project).resolve();allowed=set(source_task['initial_files'])|set(source_task['writable_files'])
    if type(expected) is not dict or not 0<len(expected)<=MAX_FILES or not set(expected)<=allowed:
        raise ValueError('source final namespace is not registered')
    for name,digest in expected.items():
        relative(name)
        if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}',digest) is None:raise ValueError('source snapshot digest differs')
    def regular(path,folder=False):
        info=path.lstat()
        if (stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&1024
                or not (stat.S_ISDIR(info.st_mode) if folder else stat.S_ISREG(info.st_mode))
                or not folder and info.st_nlink!=1):raise ValueError('unsafe actual source path')
        return info
    regular(project,True)
    def names():
        found=set()
        for directory,dirs,leaves in os.walk(project,topdown=True,followlinks=False):
            root=Path(directory)
            for name in dirs:regular(root/name,True)
            if root==project:dirs[:]=[name for name in dirs if name!='.git']
            for name in leaves:
                path=root/name;regular(path);found.add(path.relative_to(project).as_posix())
        return found
    if names()!=set(expected):raise ValueError('actual namespace differs from source final receipt')
    files={};total=0
    for name in sorted(expected):
        path=project/name;before=regular(path);raw=path.read_bytes();after=regular(path)
        if (len(raw)>MAX_FILE_BYTES or sha(raw)!=expected[name]
                or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)):
            raise ValueError('actual source changed while receiving')
        files[name]=raw.decode('utf-8');total+=len(raw)
    if total>MAX_TOTAL_BYTES or names()!=set(expected):raise ValueError('actual source snapshot is not bounded/stable')
    return files


def runtime_plan(arm,context_path,python_binary,run_root,receipt_path,expected_plan,expected_script_sha256):
    """Same fixed Python -B/context/json planner contract as v6, never helpers."""
    import ledger_primary as ledger_source
    package=LOCAL/'frozen'/('full-runtime' if arm=='full' else 'baseline-runtime')
    script=package/'scripts/plan_governance.py'
    if arm not in ARMS or sha(script.read_bytes())!=expected_script_sha256:
        raise ValueError('frozen planner script differs before invocation')
    argv=[str(python_binary),'-B',str(script),'--context',str(context_path),'--json']
    started=clock();timed_out=False;error=None;returncode=None;stdout=stderr=b''
    try:
        observed=subprocess.run(argv,cwd=run_root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
        returncode,stdout,stderr=observed.returncode,observed.stdout,observed.stderr
    except subprocess.TimeoutExpired as failure:
        timed_out=True;stdout=failure.stdout or b'';stderr=failure.stderr or b'';error='TimeoutExpired'
    except OSError as failure:error=type(failure).__name__
    value={'schema_version':'stdlib-project-runtime-planner-v7','argv':argv,'cwd':str(run_root),
        'script_sha256':expected_script_sha256,'returncode':returncode,'timeout':timed_out,'error':error,
        'stdout_base64':base64.b64encode(stdout).decode(),'stderr_base64':base64.b64encode(stderr).decode(),
        'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'wall_seconds':clock()-started,
        'expected_plan_utf8_sha256':sha(expected_plan.encode()),'matches_expected':error is None and returncode==0
            and stdout==expected_plan.encode() and stderr==b'',
        'scope':'real fixed planner process only; no --project-root or helper lifecycle; no retry'}
    digest=immutable(receipt_path,value)
    if value['matches_expected'] is not True:raise ledger_source.StudyStop('runtime-planner-failed-or-drift-global-stop')
    return {'ref':Path(receipt_path).relative_to(run_root).as_posix(),'sha256':digest}
