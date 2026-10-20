"""Inert, once-only post-exit primary raw reader; never executes a project."""
import argparse
import copy
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
if Path(common.__file__).resolve() != Path(__file__).resolve().parent / 'common.py':
    raise ValueError('foreign first auditor common module')
from common import (HERE, IDENTITY, STUDY_KIND, COUNTS, canonical, sha, strict_json,
    require, regular_bytes, immutable, file_map, protocol, source_observation, runtime, roots)

READINESS_BINDINGS = {'actual_entry_authorization': 'UNBOUND'}
AUTHORIZATION = 'first-after-terminal-primary-nine-family-v1'
REQUIRED_ARTIFACTS = ('entry.STARTED.json', 'source.before.json', 'raw.before.json', 'owner.before.json',
    'source.after.json', 'raw.after.json', 'owner.after.json', 'first-audit.json')
REQUIRED = REQUIRED_ARTIFACTS + ('audit.seal.json',)


def safe_tail(out, value):
    raw = canonical(value) + b'\n'
    descriptor = None
    try:
        descriptor = os.open(Path(out) / 'failure-tail.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        offset = 0
        while offset < len(raw):
            size = os.write(descriptor, raw[offset:])
            if size <= 0:
                raise OSError('short failure-tail write')
            offset += size
        os.fsync(descriptor)
        return {'status': 'PUBLISHED', 'sha256': sha(raw)}
    except BaseException as error:
        metadata = {'status': 'UNPUBLISHED', 'exception_class': type(error).__name__, 'sha256': sha(raw)}
        try:
            sys.stderr.write(__import__('json').dumps({'first_audit_failure_tail': metadata}, sort_keys=True) + '\n')
            sys.stderr.flush()
        except BaseException:
            pass
        return metadata
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except BaseException:
                pass


def publish(out, name, value):
    expected = canonical(value) + b'\n'
    digest = immutable(Path(out) / name, value)
    require(regular_bytes(Path(out) / name) == expected and digest == sha(expected), 'publication readback differs:' + name)
    return digest


def complete_source_observation(bundle,expected_protocol):
    # Include every prepared input, not only the three manifest/dependency files.
    result = dict(source_observation(bundle,expected_protocol))
    for name, digest in file_map(Path(bundle)).items():
        path = str(Path(bundle) / name)
        require(path not in result or result[path] == digest, 'overlapping source observation differs')
        result[path] = digest
    return dict(sorted(result.items()))


def error_row(scope, error):
    row = {'scope': scope, 'exception_class': type(error).__name__}
    if isinstance(error, ValueError):
        row['code'] = str(error)[:240]
    return row


def publish_final(out, maps, errors, report, digests):
    """Preserve the first error and every observed map, including publisher faults.

    A write-then-raise never licenses rewriting uncertain report/seal bytes. The
    separate immutable failure tail and external exit disqualify those bytes.
    """
    success = False
    try:
        for scope in ('source', 'raw', 'owner'):
            for suffix in ('before', 'after'):
                name = scope + '.' + suffix + '.json'
                digests[name] = publish(out, name, maps.get(scope + '_' + suffix, {'status': 'NOT_CAPTURED'}))
        report.update(status='FAILED' if errors else 'RAW_PASS', first_error=errors[0] if errors else None,
            findings=copy.deepcopy(errors))
        digests['first-audit.json'] = publish(out, 'first-audit.json', report)
        for name in REQUIRED_ARTIFACTS:
            require(name in digests and sha(regular_bytes(Path(out) / name)) == digests[name],
                'missing/changed required artifact:' + name)
            if name.endswith(('.before.json', '.after.json')):
                scope, suffix, unused = name.split('.')
                require(regular_bytes(Path(out) / name) == canonical(maps[scope + '_' + suffix]) + b'\n',
                    'captured map changed:' + name)
        seal = {'schema': 'primary-first-raw-audit-seal-v1', 'status': 'FAILED' if errors else 'RAW_PASS',
            'first_raw_audit_sha256': digests['first-audit.json'],
            'required_artifacts': {name: digests[name] for name in REQUIRED_ARTIFACTS},
            'first_error': errors[0] if errors else None,
            'success_consumption': 'external exit0 + confirmed success seal + no failure-tail; uncertain bytes never rewritten'}
        digests['audit.seal.json'] = publish(out, 'audit.seal.json', seal)
        for name in REQUIRED:
            require(sha(regular_bytes(Path(out) / name)) == digests[name], 'final required readback:' + name)
        require(set(path.name for path in Path(out).iterdir()) == set(REQUIRED), 'unexpected publication or failure tail')
        success = not errors
    except BaseException as error:
        errors.append(error_row('final-publication', error))
    if errors:
        safe_tail(out, {'schema': 'primary-first-raw-audit-failure-tail-v1', 'status': 'FAILED',
            'first_error': errors[0], 'findings': errors, 'observed_maps': maps,
            'confirmed_publications': digests, 'never_repair_or_reaudit': True})
    return success


def actor_trace_present(actor, budget, raw_map, ledger, terminal):
    """Absence is proved from the entire namespace and original ledger, not a result claim."""
    workflow, role = budget['workflow_id'], budget['role']
    prefixes = ('actors/' + actor + '/', 'git-baselines/' + workflow + '/' + role + '.')
    exact = {'actor-records/' + actor + '.json', 'planner-receipts/' + actor + '.json'}
    if any(name in exact or name.startswith(prefixes) for name in raw_map):
        return True
    if role == 'source' and any(name.startswith('workspaces/' + workflow + '/') for name in raw_map):
        return True
    if actor in ledger['actor_clocks'] or any(row['actor_id'] == actor for row in ledger['requests']):
        return True
    unfinished = terminal['unfinished_actor']
    return type(unfinished) is dict and unfinished.get('actor_id') == actor


def uninvoked_proofs(registry, record_ids, raw_map, ledger, terminal):
    proofs = {}
    for actor, budget in registry.items():
        if actor in record_ids or actor_trace_present(actor, budget, raw_map, ledger, terminal):
            proofs[actor] = {'status': 'UNVERIFIED', 'raw_integrity': False, 'accounting_complete': False}
        else:
            proofs[actor] = {'status': 'UNINVOKED'}
    return proofs


def actor_proof(actor, record_raw, verified, *, controlled_source=False):
    require(verified.get('raw_integrity') is True and verified.get('accounting_complete') is True,
        'actor independent raw/accounting proof')
    require(verified.get('owned_request_workers_closed') is True, 'owned request worker closure')
    require(common.valid_sha(verified.get('verified_final_state_sha256')), 'verified actor final snapshot SHA')
    require(type(verified.get('phase_cut_verified')) is bool, 'independent phase proof is typed')
    passed = False if controlled_source else verified.get('independent_task_pass')
    require(type(passed) is bool, 'independent task pass is typed')
    return {'status': 'RAW_PASS', 'raw_integrity': True, 'accounting_complete': True,
        'actor_record_ref': 'actor-records/' + actor + '.json', 'actor_record_sha256': sha(record_raw),
        'verified_final_state_sha256': verified['verified_final_state_sha256'],
        'independent_task_pass': passed, 'phase_cut_verified': verified['phase_cut_verified']}


def known_task_success(record, proof):
    result = record['result']
    return (proof.get('independent_task_pass') is True and result.get('status') == 'completed'
        and all(result.get(key) is False for key in ('unknown_usage', 'execution_state_unknown',
            'execution_infrastructure_failed', 'work_deadline_reached')))


def controlled_source_eligible(record, proof, policy):
    result = record['result']
    return (proof.get('phase_cut_verified') is True and policy is not None
        and result.get('status') == 'controlled-phase-stop-unfinished'
        and all(result.get(key) is False for key in ('unknown_usage', 'execution_state_unknown',
            'execution_infrastructure_failed', 'work_deadline_reached'))
        and result.get('quality', {}).get('task_success') is None
        and result.get('quality', {}).get('source_completed') is False
        and result.get('quality', {}).get('source_graded') is False
        and proof['verified_final_state_sha256'] == result.get('final_state_sha256'))


def verify_original_tail_maps(supervisor, bundle, maps, expected_protocol):
    expected_owner = {name[len('owner/'):]: digest for name, digest in maps['owner_before']['files'].items()
        if name.startswith('owner/')}
    require(strict_json(regular_bytes(supervisor / 'raw-tail-map.json')) == maps['raw_before']['files'],
        'original supervisor raw-tail map differs')
    require(strict_json(regular_bytes(supervisor / 'parent-tail-map.json')) == expected_owner,
        'original supervisor owned-parent tail map differs')
    expected_sources = source_observation(bundle,expected_protocol)
    require(strict_json(regular_bytes(supervisor / 'source.before.json')) == expected_sources
        and strict_json(regular_bytes(supervisor / 'source.after.json')) == expected_sources,
        'original supervisor source guard differs')


def verify_workflows(run, p, order, specs, ledger, terminal, raw_map, reader):
    registry = p['actor_registry']
    workflow_ids = {row['workflow_id'] for row in order}
    require(all(not name.startswith('actors/') or (len(name.split('/')) >= 3 and name.split('/')[1] in registry)
        for name in raw_map), 'unregistered actor raw namespace')
    require(all(not name.startswith('workspaces/') or (len(name.split('/')) >= 3 and name.split('/')[1] in workflow_ids)
        for name in raw_map), 'unregistered project namespace')
    require(all(not name.startswith('planner-receipts/') or name in {'planner-receipts/' + actor + '.json' for actor in registry}
        for name in raw_map), 'unregistered planner receipt namespace')
    record_refs = {name for name in raw_map if name.startswith('actor-records/')}
    allowed = {'actor-records/' + actor + '.json' for actor in registry}
    require(record_refs <= allowed, 'unregistered or nested actor record')
    record_raw = {name[len('actor-records/'):-5]: regular_bytes(run / name) for name in sorted(record_refs)}
    records = {actor: strict_json(raw) for actor, raw in record_raw.items()}
    require(all(row['actor_id'] == actor for actor, row in records.items()), 'original actor record identity')
    require(terminal['completed_actor_records'] == len(records), 'terminal original actor count')
    proofs = uninvoked_proofs(registry, records, raw_map, ledger, terminal)
    chains = {name for name in raw_map if name.startswith('chains/')}
    require(chains <= {'chains/' + row['workflow_id'] + '.json' for row in order}, 'unregistered chain namespace')
    require(terminal['completed_workflow_records'] == len(chains), 'terminal original chain count')
    verified_chains = []
    for workflow in order:
        source_id, receiver_id = workflow['source_actor_id'], workflow['receiver_actor_id']
        source, receiver = records.get(source_id), records.get(receiver_id)
        chain_ref = 'chains/' + workflow['workflow_id'] + '.json'
        if source is None:
            require(receiver is None and chain_ref not in chains, 'receiver/chain without original source record')
            continue
        require(chain_ref in chains, 'completed actor lacks original workflow chain')
        spec = specs[workflow['case_id']]
        proof = reader.verify_workflow(run_root=run, protocol=p, workflow_spec=spec, source_record=source,
            receiver_record=receiver, actor_registry=registry)
        if receiver is None:
            source_verified = proof['source']
        else:
            require(spec['cut_policy'] is not None and proof['source']['phase_cut_verified'] is True,
                'receiver source independently controlled and unfinished')
            source_verified = dict(proof['source'], raw_integrity=True, accounting_complete=True,
                owned_request_workers_closed=proof['receiver']['owned_request_workers_closed'], independent_task_pass=False)
        proofs[source_id] = actor_proof(source_id, record_raw[source_id], source_verified,
            controlled_source=spec['cut_policy'] is not None)
        if receiver is not None:
            proofs[receiver_id] = actor_proof(receiver_id, record_raw[receiver_id], proof['receiver'])
        chain = strict_json(regular_bytes(run / chain_ref))
        require(all(chain[key] == value for key, value in workflow.items()), 'original chain registered workflow')
        expected_refs = ['actor-records/' + source_id + '.json']
        if receiver is not None:
            expected_refs.append('actor-records/' + receiver_id + '.json')
        require(chain['actor_record_refs'] == expected_refs, 'chain actor order and original record references')
        eligible = controlled_source_eligible(source, proofs[source_id], spec['cut_policy'])
        success = known_task_success(receiver, proofs[receiver_id]) if receiver is not None else (
            known_task_success(source, proofs[source_id]) if spec['cut_policy'] is None else False)
        require(chain['source_eligible'] is eligible and chain['workflow_success'] is success
            and proof['workflow_success'] is success, 'chain success/cut claim independently reconstructed')
        verified_chains.append(workflow['workflow_id'])
    require(all(row['status'] != 'UNVERIFIED' for row in proofs.values()), 'attempted prefix has no complete raw-verifiable actor record')
    return proofs, verified_chains


def verify_owner(bundle, p, expected_protocol, expected_terminal, expected_owner, audit_started):
    run, owner, supervisor = roots(p)
    def owner_json(name):
        return strict_json(regular_bytes(owner / name))
    exit_raw = regular_bytes(supervisor / 'owner-exit.json')
    require(sha(exit_raw) == expected_owner, 'explicit original owner process-exit SHA')
    exit_record = strict_json(exit_raw)
    require(exit_record['schema'] == 'primary-owner-exit-v1' and exit_record['run_root'] == str(run)
        and exit_record['process_exited'] is True and exit_record['worker_alive'] is False
        and exit_record['confirmed'] is True and exit_record['job_and_direct_child_cleanup_confirmed'] is True
        and exit_record['first_exception_class'] is None
        and type(exit_record['exit_code']) is int and exit_record['exit_code'] == 0
        and type(exit_record['observed_exit_monotonic']) in (int, float)
        and exit_record['observed_exit_monotonic'] <= audit_started, 'closed original owner before first audit')
    closed_raw = regular_bytes(owner / 'CLOSED.json')
    require(sha(closed_raw) == exit_record['owner_closed_sha256'], 'external exit binds original owner CLOSED')
    closed = strict_json(closed_raw)
    started, ready, go = (owner_json(name) for name in ('STARTED.json', 'JOB_READY.json', 'GO.json'))
    spawned, returned, child = (owner_json(name) for name in ('SPAWN.before.json', 'SPAWN.returned.json', 'launch-CLOSED.json'))
    command_raw, plan_raw = (regular_bytes(Path(bundle) / name) for name in ('commands.json', 'execution-plan.json'))
    command, plan = strict_json(command_raw), strict_json(plan_raw)
    require(plan['protocol_sha256'] == expected_protocol and plan['command_sha256'] == sha(command_raw), 'registered owner command/plan')
    require(started['execution_plan_sha256'] == closed['execution_plan_sha256'] == sha(plan_raw), 'same owner execution plan')
    require(started['protocol_sha256'] == closed['protocol_sha256'] == ready['protocol_sha256'] == expected_protocol,
        'owner protocol identity')
    require(started['source_manifest_sha256'] == closed['source_manifest_sha256'] == p['source_manifest_sha256'], 'owner source identity')
    require(started['replay_or_resume_authorized'] is False and started['explicit_root_single_launch_grant'] is True, 'one owner fence')
    require(started['observed_parent_argv'] == [sha(plan_raw) if item == 'EXTERNAL_EXECUTION_PLAN_SHA256' else item
        for item in command['parent_argv_template']] and started['observed_parent_cwd'] == command['cwd'] == str(HERE), 'actual parent argv/cwd')
    require(spawned['child_argv'] == [*command['child_argv_prefix'][:-1], sha(plan_raw), '--job-name', ready['job_name']]
        and spawned['cwd'] == str(HERE) and spawned['shell'] is False and spawned['all_inputs_verified_before_spawn'] is True, 'exact child spawn')
    require(ready['observed_child_argv'] == spawned['child_argv'] and ready['observed_child_cwd'] == str(HERE)
        and returned['pid'] == ready['pid'] == closed['child_pid'] and returned['spawn_returned'] is True
        and ready['job_membership_confirmed'] is True and returned['job_membership_not_yet_asserted'] is True, 'owned Job/child identity')
    require(go['job_ready_sha256'] == sha(regular_bytes(owner / 'JOB_READY.json'))
        and go['source_reverified_before_go'] is True and go['command_sha256'] == sha(command_raw), 'Job READY before GO')
    require(closed['status'] == 'CLOSED_KNOWN_CHILD' and closed['exception_class'] is None
        and closed['child_returncode'] == 0 and closed['child_observed_exited'] is True
        and closed['child_reap']['status'] == 'EXITED_CONFIRMED' and closed['child_reap']['errors'] == []
        and closed['job_cleanup']['active_after'] == 0 and closed['job_cleanup']['query_after_confirmed'] is True
        and all(closed['job_cleanup'][name] is None for name in ('terminate_error', 'query_error', 'close_error')), 'owned process/Job closure')
    require(closed['terminal_sha256'] == child['terminal_sha256'] == expected_terminal
        and child['exception_class'] is None and child['collector_restored_disabled'] is True
        and child['auditor_authorization'] == 'UNBOUND', 'terminal and child finally')
    require(closed['round_seconds_soft'] == p['round_caps']['round_seconds_soft'] and closed['overrun'] is False
        and closed['inclusive_owner_wall_seconds'] < closed['round_seconds_soft'] and child['overrun'] is False,
        'complete parent publication/cleanup wall fits registered round')
    require(closed['external_daemon_cleanup'] == 'NOT_PROVEN_BY_WINDOWS_JOB', 'Job does not attest daemon cleanup')
    for directory, names in ((owner, ('stdout.raw', 'stderr.raw')),
            (supervisor, ('parent.stdout.raw', 'parent.stderr.raw'))):
        require(all(len(regular_bytes(directory / name)) <= p['owner_limits']['stdout_stderr_bytes_each_soft'] for name in names),
            'original bounded owner streams required')
    outer = strict_json(regular_bytes(supervisor / 'STARTED.json'))
    parent_spawn = strict_json(regular_bytes(supervisor / 'parent-SPAWN.returned.json'))
    parent_reap = strict_json(regular_bytes(supervisor / 'parent-reap.json'))
    require(outer['schema'] == 'primary-outer-first-setup-v1' and outer['protocol_sha256'] == expected_protocol
        and outer['execution_plan_sha256'] == sha(plan_raw) and outer['no_replay_or_resume'] is True
        and outer['deadline_monotonic'] - outer['started_monotonic'] == p['round_caps']['round_seconds_soft']
        and outer['started_monotonic'] <= started['started_monotonic'] <= exit_record['observed_exit_monotonic'],
        'outer first setup owns strict whole-round clock')
    require(parent_spawn['pid'] == parent_reap['pid'] == exit_record['owner_parent_pid']
        and parent_spawn['argv'] == outer['parent_argv'] == started['observed_parent_argv']
        and parent_spawn['cwd'] == str(HERE) and parent_spawn['shell'] is False
        and parent_reap['first_exception_class'] is None
        and parent_reap['reap']['observed_exited'] is True and parent_reap['reap']['returncode'] == 0
        and parent_reap['reap']['errors'] == [], 'external owned parent handle exit proof')
    return exit_record, closed


def audit(bundle, expected_protocol, expected_terminal, expected_owner, expected_source, out):
    require(READINESS_BINDINGS == {'actual_entry_authorization': AUTHORIZATION}, 'actual first auditor UNBOUND')
    require(sha(regular_bytes(Path(__file__))) == expected_source, 'explicit auditor source SHA')
    p, unused = protocol(bundle, expected_protocol)
    require(p['first_auditor_source_sha256'] == expected_source, 'protocol exact first auditor source')
    require(p['first_audit_required_artifacts'] == list(REQUIRED_ARTIFACTS), 'registered complete first audit artifact list')
    run, owner, supervisor = roots(p)
    out = Path(out).resolve()
    require(str(out) == p['first_audit_root'] and out.is_absolute()
        and all(root != out and root not in out.parents and out not in root.parents
            for root in (HERE, run, owner, supervisor)), 'exclusive disjoint registered first output')
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    maps, errors, digests = {}, [], {}
    ledger_result, actor_proofs, workflows, terminal, owner_exit = None, {}, [], {}, {}
    def observe(scope, callback):
        try:
            return {'status': 'READABLE', 'files': callback()}
        except BaseException as error:
            errors.append(error_row(scope, error))
            return {'status': 'UNREADABLE', 'exception_class': type(error).__name__}
    def fence(event, args):
        if event.startswith(('socket.', 'subprocess.')) or event in {'os.system', 'os.exec', 'os.posix_spawn', 'os.startfile'}:
            raise RuntimeError('first raw auditor cannot execute or dispatch')
    sys.addaudithook(fence)
    try:
        digests['entry.STARTED.json'] = publish(out, 'entry.STARTED.json', {'authorization': AUTHORIZATION,
            'started_monotonic': started, 'protocol_sha256': expected_protocol, 'terminal_sha256': expected_terminal,
            'owner_exit_sha256': expected_owner, 'auditor_sha256': expected_source, 'no_reaudit': True})
        # No raw/owner body is interpreted before all original namespaces are mapped.
        maps['source_before'] = observe('source-before', lambda: complete_source_observation(bundle,expected_protocol))
        maps['raw_before'] = observe('raw-before', lambda: file_map(run))
        maps['owner_before'] = observe('owner-before', lambda: common.owner_observation(p))
        require(not errors, 'before evidence unreadable; first error retained')
        terminal_raw = regular_bytes(run / 'terminal.json')
        require(sha(terminal_raw) == expected_terminal, 'explicit original terminal SHA')
        terminal = strict_json(terminal_raw)
        owner_exit, closed = verify_owner(bundle, p, expected_protocol, expected_terminal, expected_owner, started)
        verify_original_tail_maps(supervisor, bundle, maps, expected_protocol)
        require(terminal['schema_version'] == 'primary-managed-terminal-v1' and terminal['planned_counts'] == COUNTS
            and terminal['source_final_exact'] is True, 'terminal identity/denominator/source')
        original_start = strict_json(regular_bytes(run / 'STARTED.json'))
        require(original_start['protocol_sha256'] == expected_protocol and original_start['counts'] == COUNTS
            and original_start['replay_or_resume_authorized'] is False, 'original one-use round start')
        require(terminal['round_first_start_monotonic'] == original_start['round_first_start'], 'same original round origin')
        api, broker, contract, ledger_module, shared, reader, native = runtime(bundle,expected_protocol)
        api.run_actor = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('read-only auditor no actor execution'))
        configuration_raw, configuration = common.pinned_json(Path(bundle) / 'profile-configuration.json', p['configuration_sha256'], canonical_digest=True, with_raw=True)
        require(regular_bytes(run / 'profile-configuration.json') == configuration_raw
            and strict_json(regular_bytes(run / 'host-identity.json')) == p['host'], 'original runtime host/profile bytes')
        ledger = strict_json(regular_bytes(run / 'accounting.json'))
        ledger_result = native.verify_ledger(run, ledger, actor_registry=p['actor_registry'], configuration=configuration,
            registry_identity=p['ledger_registry_identity'], finalization_policy=p['finalization_policy'])
        require(ledger_result['raw_integrity'] is True and ledger_result['accounting_complete'] is True
            and not ledger['pending'], 'whole finite prefix accounting incomplete; retain reserves')
        require(terminal['ledger_pending'] is False and terminal['ledger_persistence_fault'] is None
            and terminal['unknown'] is False and terminal['first_error_class'] is None and terminal['unfinished_actor'] is None,
            'unknown/unfinished/error prefix cannot authorize manual extraction')
        order = common.pinned_json(Path(bundle) / 'workflow-order.json', p['order_sha256'])['workflows']
        specs = {row['case_id']: row for row in common.pinned_json(Path(bundle) / 'workflow-specs.json', p['workflow_specs_sha256'])['workflows']}
        actor_proofs, workflows = verify_workflows(run, p, order, specs, ledger, terminal, maps['raw_before']['files'], reader)
        publication = common.shared_module(bundle, 'publication_primary', expected_protocol)
        round_raw = regular_bytes(supervisor / 'round-observation.json')
        round_observation = strict_json(round_raw)
        outer_start = strict_json(regular_bytes(supervisor / 'STARTED.json'))['started_monotonic']
        observed_end = round_observation['owner_completed_monotonic']
        expected_round = publication.owner_observation(run, terminal,
            round_started_monotonic=outer_start, owner_completed_monotonic=observed_end,
            actor_registry=p['actor_registry'], configuration=configuration,
            registry_identity=p['ledger_registry_identity'], finalization_policy=p['finalization_policy'])
        expected_round.update(owner_exit_sha256=expected_owner, parent_cleanup_confirmed=True,
            measurement_metadata_publication_seconds=None)
        require(round_observation == expected_round and round_observation['round_overrun'] is False
            and owner_exit['observed_exit_monotonic'] <= observed_end <= started,
            'independent inclusive owner publication reconstruction')
        require(set(round_observation['observed_workflow_seconds']) == set(workflows)
            and all(row['overrun'] is False for row in terminal['workflow_finalization_observations']),
            'all and only original completed workflows have inclusive publication evidence')
    except BaseException as error:
        errors.append(error_row('audit-body', error))
    finally:
        maps['source_after'] = observe('source-after', lambda: complete_source_observation(bundle,expected_protocol))
        maps['raw_after'] = observe('raw-after', lambda: file_map(run))
        maps['owner_after'] = observe('owner-after', lambda: common.owner_observation(p))
        for scope in ('source', 'raw', 'owner'):
            before, after = maps.get(scope + '_before'), maps[scope + '_after']
            if not before or before['status'] != 'READABLE' or after['status'] != 'READABLE' or before['files'] != after['files']:
                errors.append(error_row(scope + '-comparison', ValueError(scope + ' unreadable or changed')))
        for actor in p['actor_registry']:
            actor_proofs.setdefault(actor, {'status': 'UNVERIFIED', 'raw_integrity': False, 'accounting_complete': False})
        raw_map = maps.get('raw_before', {}).get('files', {})
        report = {'schema': 'primary-first-raw-audit-v1', 'first_audit': True, 'identity': IDENTITY, 'study_kind': STUDY_KIND,
            'protocol_sha256': expected_protocol, 'terminal_sha256': expected_terminal, 'owner_exit_sha256': expected_owner,
            'first_auditor_source_sha256': expected_source, 'started_monotonic': started,
            'source_manifest_sha256': p['source_manifest_sha256'], 'assembly_source_manifest_sha256': p['assembly_source_manifest_sha256'],
            'input_raw_map_sha256': sha(canonical(raw_map)), 'raw_file_count': len(raw_map),
            'source_file_count': len(maps.get('source_before', {}).get('files', {})),
            'raw_integrity': not errors, 'accounting_complete': bool(ledger_result and ledger_result['accounting_complete']),
            'complete66': len(actor_proofs) == 66 and all(row['status'] == 'RAW_PASS' for row in actor_proofs.values()),
            'actor_proofs': actor_proofs, 'verified_workflow_ids': workflows, 'ledger': ledger_result,
            'primary_benefit_assessment': 'NOT_ASSESSED',
            'scope': 'Independent raw coherence only. Known task failure is not task success; missing/unknown remains unqualified. No manual quality or favorable cost inference.'}
        success = publish_final(out, maps, errors, report, digests)
    return 0 if success else 1


def main():
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        for field in ('protocol-sha256', 'terminal-sha256', 'owner-exit-sha256', 'auditor-sha256', 'bundle', 'out'):
            parser.add_argument('--' + field, required=True)
        parser.add_argument('--terminal-confirmed', action='store_true')
        parser.add_argument('--process-exit-confirmed', action='store_true')
        parser.add_argument('--owner-exit-code', type=int, required=True)
        args = parser.parse_args()
        require(args.terminal_confirmed and args.process_exit_confirmed and args.owner_exit_code == 0,
            'separate post-terminal successful owner process-exit grant required')
        return audit(args.bundle, args.protocol_sha256, args.terminal_sha256, args.owner_exit_sha256, args.auditor_sha256, args.out)
    finally:
        READINESS_BINDINGS['actual_entry_authorization'] = 'UNBOUND'


if __name__ == '__main__':
    raise SystemExit(main())
