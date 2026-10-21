"""Read-only admission of one explicitly attested unfinished-actor recovery.

The external proof is a trusted ROOT-observed independent audit, never a saved
producer result or a persisted process cache. No model or project is executed.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re
import stat

from evolution.tool_broker import canonical, sha, relative, MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES

POLICY_ID = 'known-before-dispatch-connect-timeout-checkpoint-once-v1'
SCHEMA = 'engineering-actor-resume-checkpoint-v1'
PROFILE = 'thinking-enabled-engineering-ultraspeed-strict-dslow32768-mimo65536-checkpoint-once-sse-v1'
_SEED_TOKEN = object()


class _ResumeSeed(dict):
    def __init__(self, value, *, task_sha256, root, token):
        _require(token is _SEED_TOKEN, 'resume seed is validator-owned process memory')
        super().__init__(value)
        self._digest = sha(canonical(value)); self._task_sha256 = task_sha256; self._root = str(Path(root).resolve())


def validate_seed(seed, *, task, root):
    """Broker admission accepts only this process's intact validated seed."""
    _require(type(seed) is _ResumeSeed and sha(canonical(seed)) == seed._digest
        and sha(canonical(task)) == seed._task_sha256 and str(Path(root).resolve()) == seed._root,
        'resume seed owner, memory digest and task/workspace scope')
    files = seed['current_files']; physical = Path(root).resolve(); found = {}
    for path in physical.rglob('*'):
        if '.git' in path.relative_to(physical).parts: continue
        info = path.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024, 'resume seed linked project')
        if path.is_file(): found[path.relative_to(physical).as_posix()] = sha(_raw(path))
    _require(found == _state(files), 'resume seed current workspace changed')
    return copy.deepcopy(dict(seed))


def _require(value, code):
    if not value:
        raise ValueError(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _raw(path):
    path = Path(path).absolute()
    for parent in (path, *path.parents):
        info = parent.lstat()
        _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024,
            'resume linked input')
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 16_777_216,
        'resume bounded owned input')
    value = path.read_bytes(); after = path.lstat()
    _require(len(value) == before.st_size and
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink) ==
        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink), 'resume input changed')
    return value


def _json(raw):
    def pairs(rows):
        result = {}
        for name, value in rows:
            _require(name not in result, 'resume duplicate JSON key'); result[name] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('resume nonfinite JSON')))
    _require(type(value) is dict, 'resume JSON object')
    return value


def _ref(item):
    _require(type(item) is dict and set(item) == {'path', 'sha256'} and type(item['path']) is str
        and Path(item['path']).is_absolute() and type(item['sha256']) is str
        and re.fullmatch('[0-9a-f]{64}', item['sha256']), 'resume exact owned reference')
    data = _raw(item['path']); _require(sha(data) == item['sha256'], 'resume reference hash differs')
    return _json(data)


def _state(files):
    return {name: sha(text.encode('utf-8')) for name, text in sorted(files.items())}


def _files(value):
    _require(type(value) is dict and 0 < len(value) <= MAX_FILES, 'resume bounded file namespace')
    for name, text in value.items():
        relative(name)
        _require(type(text) is str and len(text.encode('utf-8')) <= MAX_FILE_BYTES, 'resume bounded file text')
    _require(sum(len(t.encode('utf-8')) for t in value.values()) <= MAX_TOTAL_BYTES
        and len({n.casefold() for n in value}) == len(value), 'resume unambiguous total file bytes')
    return value


def _git_head(root):
    git = Path(root)/'.git'
    info = git.lstat()
    _require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
        and not getattr(info,'st_file_attributes',0)&1024, 'resume original ordinary Git directory')
    head = _raw(git/'HEAD').decode('ascii').strip()
    if head.startswith('ref: '):
        ref = head[5:]
        _require(ref.startswith('refs/heads/'), 'resume local original Git branch')
        relative(ref)
        target = git/ref
        if target.exists(): head = _raw(target).decode('ascii').strip()
        else:
            rows = _raw(git/'packed-refs').decode('ascii').splitlines()
            hits = [row.split(' ',1)[0] for row in rows if ' ' in row and row.split(' ',1)[1] == ref]
            _require(len(hits)==1, 'resume exact original packed Git branch'); head=hits[0]
    _require(re.fullmatch('[0-9a-f]{40}',head) is not None, 'resume Git HEAD identity')
    return head


def validate_resume(value, *, task, provider, model, system_context, configuration, root, require_current_disk=True, trusted_checkpoint_sha256=None):
    """Authenticate a frozen prefix and return a copy of its cumulative seed.

    Only a postexecution independent reader may pass require_current_disk=False;
    dispatch/broker admission must check the unchanged physical prefix first.
    """
    _require(type(trusted_checkpoint_sha256) is str
        and re.fullmatch('[0-9a-f]{64}', trusted_checkpoint_sha256) is not None
        and sha(canonical(value)) == trusted_checkpoint_sha256,
        'resume checkpoint requires an independent caller-owned trust anchor')
    _require(type(value) is dict and set(value) == {'schema','policy_id','actor_id','original_protocol',
        'original_record','verified_prefix','prefix_observed_exit','prefix_reader','snapshot','active_seconds_debit'}
        and value['schema'] == SCHEMA and value['policy_id'] == POLICY_ID, 'resume explicit policy/descriptor')
    _require(type(require_current_disk) is bool and configuration.get('profile_id') == PROFILE
        and sha(canonical(configuration))=='0d204c60bf968839d183954286e871aba0b168ed1b144a6cf1dae219e082af56',
        'resume engineering checkpoint profile only')
    p = _ref(value['original_protocol']); record = _ref(value['original_record'])
    proof = _ref(value['verified_prefix']); observed = _ref(value['prefix_observed_exit'])
    snapshot = _ref(value['snapshot'])
    reader = value['prefix_reader']
    _require(type(reader) is dict and set(reader) == {'path','sha256'} and sha(_raw(reader['path'])) == reader['sha256'],
        'resume independent reader source bytes')
    _require(observed['schema'] == 'root-observed-actor-resume-prefix-exit-v1' and observed['caller'] == 'ROOT'
        and type(observed['exit_code']) is int and observed['exit_code'] == 0
        and observed['reader_sha256'] == reader['sha256'] and observed['proof_sha256'] == value['verified_prefix']['sha256']
        and observed['source_before_after_exact'] is True and observed['model_calls'] == observed['project_executions'] == 0,
        'resume actual ROOT-observed independent audit exit')
    actor = value['actor_id']
    _require(type(actor) is str and re.fullmatch('[A-Za-z0-9_-]{1,96}', actor) is not None,
        'resume actor id must be one bounded path component')
    budget = p['actor_registry'][actor]
    original_root = Path(p['run_root']).resolve()
    _require(record['actor_id'] == actor and budget['surface'] == 'API' and budget['provider'] == provider
        and budget['model'] == model and record['provider'] == provider and record['model'] == model,
        'resume exact registered actor/provider/model')
    for key in ('task_ref','result_ref','artifact_ref','workspace_ref'):
        relative(record[key])
    artifact_root = original_root / record['artifact_ref']
    _require(Path(value['original_record']['path']).resolve() == original_root/'actor-records'/(actor+'.json'), 'resume original record path')
    task_raw = _raw(original_root/record['task_ref']); old_task = _json(task_raw)
    result_raw = _raw(original_root/record['result_ref']); result = _json(result_raw)
    returned = copy.deepcopy(record['result']); result_file_sha = returned.get('receipt', {}).pop('result_file_sha256', None)
    _require(result_file_sha == sha(result_raw) and canonical(returned) == canonical(result), 'resume original returned/saved result binding')
    _require(sha(result_raw) == record['result_sha256'] and canonical(old_task) == canonical(task)
        and sha(task_raw) == record['task_sha256']
        and record['system_context'] == system_context and result['input_task_sha256'] == sha(canonical(task))
        and result['system_context_sha256'] == sha(system_context.encode('utf-8'))
        and result['profile_configuration_sha256'] == p['configuration_sha256'] == sha(canonical(configuration)),
        'resume original task/system/configuration, never a new baseline')
    _require(proof['schema'] == 'engineering-actor-resume-prefix-proof-v1' and proof['status'] == 'VERIFIED_UNFINISHED'
        and proof['actor_id'] == actor and proof['original_protocol'] == value['original_protocol']
        and proof['original_record'] == value['original_record'] and proof['snapshot'] == value['snapshot']
        and proof['reader_sha256'] == reader['sha256']
        and all(proof[k] is True for k in ('raw_integrity','accounting_complete','owned_workers_closed','inputs_before_after_exact','eligible_before_dispatch_timeout'))
        and proof['independent_task_pass'] is False, 'resume explicitly verified unfinished prefix, not producer JSON')
    _require(result['status'] == 'transport-failed-not-invoked' and result['final_report'] is None
        and result['quality']['hard_pass'] is False
        and all(result[k] is False for k in ('unknown_usage','execution_state_unknown','execution_infrastructure_failed','work_deadline_reached'))
        and result['profile_id'] == PROFILE and type(result['conversation_index']) is int and result['conversation_index'] == 0
        and result['context_checkpoint_receipts'] == []
        and type(result['schema_rejections']) is int and result['schema_rejections'] == 0
        and type(result['reasoning_continuations']) is int and result['reasoning_continuations'] == 0,
        'resume known unfinished once-only boundary')
    events = result['tool_events']; traces = result['api_tool_trace']
    requests = result['requests']; tools = result['tool_attempts']
    _require(type(requests) is int and 1 <= requests < 24 and type(tools) is int and 0 <= tools < 32
        and len(events) == len(traces) == tools and type(result['max_requests']) is int and result['max_requests'] == 24
        and type(result['max_tools']) is int and result['max_tools'] == 32,
        'resume cumulative request/tool counters')
    journal = b''.join(canonical(event)+b'\n' for event in events)
    _require(_raw(artifact_root/'broker.jsonl') == journal and proof['broker_journal_sha256'] == sha(journal),
        'resume original complete broker journal')
    files = copy.deepcopy(_files(task['initial_files'])); received = _state(files); previous = None
    for index, (event, trace) in enumerate(zip(events, traces), 1):
        arguments = event['arguments']; outcome = event['result']
        _require(type(event['sequence']) is int and event['sequence'] == index
            and type(trace['broker_sequence']) is int and trace['broker_sequence'] == index
            and event['arguments_sha256'] == sha(canonical(arguments)) and event['result_sha256'] == sha(canonical(outcome))
            and trace['broker_event_sha256'] == sha(canonical(event)) and trace['previous_chain_sha256'] == previous
            and trace['chain_sha256'] == sha(canonical({k:v for k,v in trace.items() if k != 'chain_sha256'}))
            and all(canonical(trace.get(k)) == canonical(event.get(k)) for k in ('tool','arguments_sha256','result_sha256','state_sha256'))
            and type(trace['request_index']) is int and 1 <= trace['request_index'] < requests
            and outcome.get('write_state') != 'partial-or-unverified', 'resume complete journal and prior chain')
        if event['tool'] == 'repo_patch' and outcome.get('ok') is True:
            seen = set()
            for op in arguments['operations']:
                name = op['path']; relative(name); old = files.get(name)
                _require(name in task['writable_files'] and name not in seen
                    and op['old_sha256'] == (sha(old.encode('utf-8')) if old is not None else None), 'resume patch scope/precondition')
                seen.add(name)
                if op['new_text'] is None:
                    _require(old is not None, 'resume delete existing'); files.pop(name)
                else: files[name] = op['new_text']
        _files(files)
        _require(event['state_sha256'] == sha(canonical(_state(files))), 'resume independently replayed project state')
        previous = trace['chain_sha256']
    _require(snapshot['actor_id'] == actor and snapshot['files'] == files
        and snapshot['state_sha256'] == result['final_state_sha256'] == sha(canonical(_state(files)))
        and result['received_state_sha256'] == sha(canonical(received))
        and proof['events_sha256'] == sha(canonical(events)) and proof['traces_sha256'] == sha(canonical(traces)),
        'resume original received state and independently verified current snapshot')
    git_entry=record['git_entry']; relative(git_entry['ref'])
    git_raw=_raw(original_root/git_entry['ref']);original_git=_json(git_raw)
    _require(sha(git_raw)==git_entry['sha256']
        and proof['git_entry']==git_entry and original_git['baseline_commit']==git_entry['baseline_commit'], 'resume original Git receipt lineage')
    publication=_json(_raw(original_root/'actors'/actor/'record-publication.json'))
    inline_path=original_root/'actors'/actor/'raw-verification.json';inline_raw=_raw(inline_path);inline=_json(inline_raw)
    _require(publication['actor_id']==actor and publication['actor_record_sha256']==value['original_record']['sha256']
        and publication['raw_verification_receipt']['sha256']==sha(inline_raw)
        and inline['verified_final_state_sha256']==snapshot['state_sha256']
        and inline['independent_task_pass'] is False, 'resume snapshot bound to original publication and independent prefix')
    receipts = proof['request_receipts']; outcomes = []
    _require(type(receipts) is list and len(receipts) == requests, 'resume every original request receipt')
    for index, item in enumerate(receipts, 1):
        _require(Path(item['path']).resolve() == artifact_root/'requests'/('%02d.receipt.json' % index), 'resume exact contiguous request path')
        out = _ref(item); outcomes.append(out)
        _require(type(out['request_index']) is int and out['request_index'] == index and out['provider'] == provider and out['model_requested'] == model
            and out['input_task_sha256'] == sha(canonical(task)) and out['profile_configuration_sha256'] == sha(canonical(configuration))
            and out['unknown'] is False and out.get('retry_of_request_id') is None,
            'resume known original request configuration/no retry')
    last = outcomes[-1]; settlement = last['settlement']; transport = last['transport']
    _require(last['not_invoked'] is True and last['dispatched'] is False and last['usage'] is None
        and transport['phase'] == 'connect' and transport['http_dispatch'] == 'not_started'
        and transport['exception_class'] == 'TimeoutError' and last['response_sha256'] is None
        and settlement['worker_done'] is True and settlement['worker_alive_at_return'] is False
        and settlement['attempt_dispatch_gate_closed'] is True and settlement['body_bytes_observed'] == 0,
        'resume last request proven before-dispatch timeout, never unknown/late')
    _require(all(o['dispatched'] is True and o['not_invoked'] is False and type(o['usage']) is dict for o in outcomes[:-1]),
        'resume all earlier responses settled once')
    closure = _ref(proof['original_owner_exit']); old_clock = record['actor_timing']
    elapsed = value['active_seconds_debit']
    _require(closure['process_exited'] is True and closure['worker_alive'] is False
        and _number(elapsed) and _number(proof['active_seconds_debit'])
        and elapsed >= proof['active_seconds_debit'] == closure['observed_exit_monotonic'] - old_clock['started_monotonic']
        and elapsed >= result['wall_seconds'] and 0 < elapsed < 600, 'resume cumulative active work including old teardown')
    input_map = _ref(proof['input_map'])['raw']
    prefix = record['artifact_ref']+'/'
    for name, digest in input_map.items():
        if name.startswith(prefix):
            relative(name)
            _require(sha(_raw(original_root/name)) == digest, 'resume original request/capture/response artifacts changed')
    physical = Path(p.get('workspace_bindings', {}).get(record['workspace_ref'], original_root/record['workspace_ref'])).resolve()
    _require(Path(root).resolve() == physical, 'resume same original physical workspace')
    _require(_git_head(physical)==git_entry['baseline_commit'], 'resume current Git HEAD must retain original baseline')
    if require_current_disk:
        found = {}
        for path in physical.rglob('*'):
            if '.git' in path.relative_to(physical).parts: continue
            info = path.lstat()
            _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024, 'resume no linked project namespace')
            if path.is_file(): found[path.relative_to(physical).as_posix()] = sha(_raw(path))
        _require(found == _state(files), 'resume current disk unchanged before dispatch')
    return _ResumeSeed(copy.deepcopy({'policy_id':POLICY_ID,'checkpoint_sha256':sha(canonical(value)),'source_actor_id':actor,
        'original_artifact_root':str(artifact_root),'original_task_sha256':sha(canonical(task)),
        'original_received_state':received,'current_files':files,'current_state_sha256':snapshot['state_sha256'],
        'events':events,'traces':traces,'requests_used':requests,'tools_used':tools,'elapsed_seconds_used':elapsed,
        'schema_rejections_used':0,'reasoning_continuations_used':0,'connect_retries_used':0,
        'conversation_index':1,'checkpoint_count':1,'previous_broker_chain_sha256':previous,
        'previous_request_receipt_sha256':receipts[-1]['sha256'],'prior_request_receipts':receipts,
        'prior_outcomes':outcomes,'independently_verified_prefix':value['verified_prefix']}),
        task_sha256=sha(canonical(task)),root=root,token=_SEED_TOKEN)
