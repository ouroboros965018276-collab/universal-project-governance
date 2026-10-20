"""Independent reconstruction of both API7 cuts from original raw records."""
from managed_contract_primary import canonical, sha, CUT_POLICIES
from native_auditor_primary import BEFORE_KEYS
from reader_binding_primary import require

PHASES = dict(zip(CUT_POLICIES, ('validated-batch-before-tool-delivery', 'complete-request-tool-tail')))

def phase_header(view, record, policy):
    folder = record['artifact_ref']
    refs = ('control/phase-stop-observed.json', 'control/phase-stop-authorization.json', 'control/phase-stop.accepted.json')
    found = [view.exists(folder+'/'+name) for name in refs]
    value = record['result'].get('controlled_phase_stop')
    if value is None:
        require(not any(found), 'unaccepted-or-orphan-phase-evidence')
        return None
    require(policy in PHASES and all(found), 'registered-complete-phase-envelope-required')
    observed, authorization, accepted = (view.json(folder+'/'+name) for name in refs)
    observed_sha, authorization_sha, accepted_sha = (sha(view.raw(folder+'/'+name)) for name in refs)
    require(authorization == dict(observed, kind='controlled-phase-stop-authorization',
        observed_receipt_ref=refs[0], observed_receipt_sha256=observed_sha), 'phase-original-authorization')
    require(accepted == dict(authorization, kind='controlled-phase-stop-accepted',
        authorization_receipt_ref=refs[1], authorization_receipt_sha256=authorization_sha), 'phase-original-acceptance')
    require(value == dict(accepted, accepted_receipt_ref=refs[2], accepted_receipt_sha256=accepted_sha), 'phase-original-result-binding')
    require(record['result']['receipt'].get('controlled_phase_stop_accepted_sha256') == accepted_sha, 'phase-result-receipt-binding')
    require(observed.get('phase') == PHASES[policy] and observed.get('policy_id') == policy, 'phase-registered-trigger')
    return observed

def verify_phase(view, record, task, phase, *, files, events, traces, transport):
    """Never treats an accepted producer claim alone as phase proof."""
    require(phase is not None, 'phase-evidence-required')
    from project_receipt_kernels_primary import batch_shape, required_initial_reads, state
    result = record['result']; folder = record['artifact_ref']
    count = phase.get('api_requests_observed')
    require(type(count) is int and 1 <= count <= 12 and count == result['requests'], 'phase-exact-last-request')
    require(result['status'] == 'controlled-phase-stop-unfinished' and result['work_deadline_reached'] is False
        and all(result.get(n) is False for n in ('unknown_usage','execution_state_unknown','execution_infrastructure_failed'))
        and transport['accounting_complete'] is True and transport['owned_request_workers_closed'] is True, 'phase-known-unfinished-not-late')
    request_ref = 'requests/%02d.receipt.json'%count; response_ref = 'requests/%02d.response.json'%count
    request_raw = view.raw(folder+'/'+request_ref); response_raw = view.raw(folder+'/'+response_ref)
    outcome = view.json(folder+'/'+request_ref); response = view.json(folder+'/'+response_ref)
    require(outcome['unknown'] is False and outcome['dispatched'] is True and outcome['not_invoked'] is False
        and outcome['unexpected_overrun'] == {} and outcome['response_sha256'] == sha(response_raw)
        and response['request_id'] == outcome['request_id'] and response['response']['id'] == outcome['api_response_id'], 'phase-known-exact-transport')
    s = outcome['settlement']
    require(s['accounting_only'] is False and s['work_closed'] is False and s['worker_done'] is True
        and s['worker_alive_at_return'] is False and s['attempt_dispatch_gate_closed'] is True and s['dispatch_started'] is True
        and s['policy'] == 'work-deadline-accounting-only-settlement-600s-v1' and s['max_seconds'] == 600
        and s['body_complete'] is True and s['capture_failure'] is None and s['transport_failure'] is None, 'phase-owned-worker-tail-closed')
    choice = response['response']['choices'][0]; calls = choice['message'].get('tool_calls')
    require(choice['finish_reason'] == 'tool_calls' and type(calls) is list and calls
        and all(c.get('function',{}).get('name') != 'repo_finish' for c in calls), 'phase-complete-nonterminal-batch')
    used = {t['tool_call_id'] for t in traces if t['request_index'] < count}
    for item in result['schema_rejection_receipts']:
        if item['request_index'] < count:
            rejected = view.json(folder+'/schema-rejections/%02d.json'%item['request_index'])
            used.update(c['call_id'] for c in rejected['calls'])
    batch, rejected = batch_shape(calls, used, task)
    require(not rejected, 'phase-whole-batch-schema-before-any-cut')
    require(len(events) == len(traces) and result['tool_events'] == events and result['api_tool_trace'] == traces, 'phase-all-original-event-tail')
    previous = None
    for index, (event, trace) in enumerate(zip(events,traces),1):
        require(event['sequence'] == index and view.raw(folder+'/tool-receipts/%02d.json'%index) == canonical(trace)+b'\n'
            and trace['previous_chain_sha256'] == previous
            and trace['chain_sha256'] == sha(canonical({k:v for k,v in trace.items() if k != 'chain_sha256'}))
            and trace['broker_event_sha256'] == sha(canonical(event))
            and trace['broker_sequence'] == index
            and all(trace.get(k) == event.get(k) for k in ('tool','arguments_sha256','result_sha256','state_sha256')), 'phase-durable-complete-trace-chain')
        previous = trace['chain_sha256']
    audit_present = view.exists(folder+'/broker.jsonl')
    audit = view.raw(folder+'/broker.jsonl') if audit_present else b''
    require(audit == b''.join(canonical(e)+b'\n' for e in events), 'phase-original-journal-bytes')
    tail = [t for t in traces if t['request_index'] == count]
    successful = [(e,t) for e,t in zip(events,traces) if e['tool'] == 'repo_patch' and e['result'].get('ok') is True]
    received = state(task['initial_files']); current = state(files)
    if phase['phase'] == 'validated-batch-before-tool-delivery':
        require(not events and not traces and not audit_present and current == received, 'phase-zero-tools-no-partial-batch')
    else:
        require(successful and all(t['request_index'] == count for _,t in successful)
            and [t['tool_call_id'] for t in tail] == [c['call_id'] for c in batch]
            and all(t['api_response_id'] == outcome['api_response_id'] for t in tail)
            and any(e['tool'] == 'repo_patch' and e['result'].get('ok') is True for e in events[-len(tail):])
            and required_initial_reads(events,task), 'phase-first-successful-patch-request-complete-tail')
    metadata = {k:outcome[k] for k in BEFORE_KEYS|{'reservation_receipt_sha256'}}
    expected = {'schema_version':'registered-repository-phase-cut-evidence-v1','policy_id':phase['policy_id'],
        'phase':phase['phase'],'trigger_ordinal':1,'kind':'controlled-phase-stop-observed','request_metadata':metadata,
        'request_receipt_ref':request_ref,'request_receipt_sha256':sha(request_raw),
        'response_artifact_ref':response_ref,'response_artifact_sha256':sha(response_raw),'api_response_id':outcome['api_response_id'],
        'api_requests_observed':count,'batch':batch,'batch_sha256':sha(canonical(batch)),
        'broker_event_count':len(events),'request_tail_event_count':len(tail),'successful_patch_count':len(successful),
        'broker_audit_present':audit_present,'broker_audit_sha256':sha(audit),'last_trace_chain_sha256':previous,
        'received_state_sha256':sha(canonical(received)),'state_sha256':sha(canonical(current)),
        'source_completion_required':False,'source_completed':False,'source_graded':False,
        'next_request_reserved':False,'next_request_dispatched':False}
    require(phase == expected and result['final_state_snapshot'] == current
        and result['final_state_sha256'] == expected['state_sha256'], 'phase-independent-original-reconstruction')
    require(view.exists(folder+'/actor.pending.json') and not view.exists(folder+'/report-receipt.json')
        and result['final_report'] is None and result['quality']['task_success'] is None, 'phase-unfinished-pending-without-finish')
    return {'phase_cut_verified':True,'controlled_policy':phase['policy_id'],'verified_final_state_sha256':expected['state_sha256']}
