"""Finite-registry native transport and original ledger reconciliation.

Joined by raw_auditor_primary to the independent project/phase consumers.
No actual-run main or launch grant exists in this reader module. Producer
quality, prospective fee caps and synthetic proofs are not efficacy evidence.
"""
import copy,json
from decimal import Decimal
from pathlib import Path,PurePosixPath
from reader_binding_primary import strict_json
from managed_contract_primary import ADAPTER,POLICY,canonical,sha,valid_sha,managed_deadline_valid,derive_caps,number
BEFORE_KEYS=set('request_id request_index provider model_requested input_utf8_bytes request_payload_sha256 output_cap input_task_sha256 adapter broker_profile_id settlement_policy settlement_max_seconds work_deadline_monotonic settlement_deadline_monotonic profile_id thinking reasoning_effort_requested profile_configuration_sha256 execution_backend connect_retry_policy retry_of_request_id'.split())
OUTCOME_KEYS=BEFORE_KEYS|set('reservation_receipt_sha256 dispatched not_invoked transport usage unknown unexpected_overrun response_sha256 model_reported api_response_id elapsed_seconds error_type settlement'.split())
READINESS_BINDINGS={'actual_entry_authorization':'UNBOUND'}
def require(v,code):
    if not v:raise ValueError(code)
def read_json(path,expected=None,maximum=8_388_608):
    from reader_binding_primary import owned_raw
    raw=owned_raw(path,maximum=maximum)
    if expected is not None:require(sha(raw)==expected,'raw-hash-differs')
    value=strict_json(raw);require(raw==canonical(value)+b'\n','raw-canonical-differs')
    return value,sha(raw)
def basic_usage(raw):
    if type(raw)is not dict:return None
    names=('prompt_tokens','completion_tokens','total_tokens')
    if not all(type(raw.get(k))is int and raw[k]>=0 for k in names):return None
    require(raw['total_tokens']==raw['prompt_tokens']+raw['completion_tokens'],'usage-arithmetic')
    return dict(input_tokens=raw['prompt_tokens'],output_tokens=raw['completion_tokens'],total_tokens=raw['total_tokens'])
def optional_usage_projection(raw):
    from project_receipt_kernels_primary import P
    normalized=P.raw_usage(raw)
    if normalized is not None and 'prompt_cache_hit_tokens'in raw and normalized['cached_tokens']!=raw['prompt_cache_hit_tokens']:
        return None
    return normalized
def capture_evidence(artifacts,outcome):
    s=outcome['settlement'];bound={k:outcome[k]for k in BEFORE_KEYS|{'reservation_receipt_sha256'}}
    capture_map={};complete_body=None
    for ref in s['capture_receipts']:
        record,_=read_json(Path(artifacts)/ref['receipt_ref'],ref['receipt_sha256'])
        require(set(record)==set(bound)|{'capture_kind','capture'},'capture-envelope')
        require(canonical({k:record[k]for k in bound})==canonical(bound),'capture-request-binding')
        require(record['capture_kind']==ref['kind'],'capture-kind')
        c=record['capture'];capture_map[ref['kind']]=c
        if ref['kind']=='headers':
            require(type(c)is dict and set(c)=={'http_status','headers','headers_sha256','headers_bytes','observed_monotonic'},'headers-schema')
            rows=c['headers'];require(type(rows)is list and len(rows)<=100 and all(type(x)is list and len(x)==2 and all(type(y)is str for y in x)for x in rows),'headers-rows')
            encoded=canonical(rows)
            require(type(c['headers_bytes'])is int and c['headers_bytes']==len(encoded)<=32768 and c['headers_sha256']==sha(encoded),'headers-bytes')
            require(type(c['http_status'])is int and 100<=c['http_status']<=599,'http-status')
            require(c['observed_monotonic']==s['headers_observed_monotonic'],'headers-time')
        else:
            require(type(c)is dict and set(c)=={'body_sha256','body_bytes','body_utf8','body_complete','last_observed_monotonic','response_completed_monotonic'},'body-schema')
            require(type(c['body_utf8'])is str and type(c['body_bytes'])is int and type(c['body_complete'])is bool,'body-types')
            encoded=c['body_utf8'].encode('utf-8')
            # Redaction or UTF-8 replacement cannot be verified as original raw.
            # Retain the accounting reserve rather than claiming reconstructed bytes.
            require(c['body_bytes']==len(encoded)<=2097153 and c['body_sha256']==sha(encoded),'body-original-projection-unverifiable')
            require(c['body_bytes']==s['body_bytes_observed']and c['body_sha256']==s['body_sha256']and c['body_complete']is s['body_complete'],'body-summary-binding')
            require(c['last_observed_monotonic']==s['body_last_observed_monotonic']and c['response_completed_monotonic']==s['response_completed_monotonic'],'body-times')
            if c['body_complete']:complete_body=encoded
    return capture_map,complete_body
def audit_request(run_root,actor_id,index,*,actor_registry):
    require(actor_id in actor_registry,'registered-actor');budget=actor_registry[actor_id]
    artifacts=Path(run_root)/'actors'/actor_id/'artifacts'
    outcome,outcome_sha=read_json(artifacts/'requests'/('%02d.receipt.json'%index))
    require(set(outcome)==OUTCOME_KEYS,'native-exact-schema')
    require(type(index)is int and type(outcome['request_index'])is int and index==outcome['request_index']and 1<=index<=budget['max_requests'],'native-index')
    require(outcome['provider']==budget['provider']and outcome['model_requested']==budget['model'],'registered-provider-model')
    require(managed_deadline_valid(outcome,actor_id=actor_id,actor_registry=actor_registry),'managed-typed-deadline')
    require(type(outcome['unknown'])is bool and type(outcome['dispatched'])is bool and type(outcome['not_invoked'])is bool,'outcome-flags')
    captures,body=capture_evidence(artifacts,outcome)
    response=None;known=None;normalized=None
    if outcome['response_sha256']is not None:
        response,_=read_json(artifacts/'requests'/('%02d.response.json'%index),outcome['response_sha256'])
        require(set(response)=={'http_status','body_sha256','body_bytes','response','request_id_header','adapter','broker_profile_id','execution_backend','request_id'},'response-envelope')
        require(body is not None and response['body_sha256']==sha(body)and type(response['body_bytes'])is int and response['body_bytes']==len(body),'response-body-binding')
        require(canonical(response['response'])==canonical(strict_json(body)),'response-raw-json-binding')
        require(type(response['response'].get('id'))is str and response['response']['id']and type(response['response'].get('model'))is str and response['response']['model']
            and outcome['api_response_id']==response['response']['id']and outcome['model_reported']==response['response']['model'],'original-native-response-id-and-model-binding')
        require(all(response[k]==outcome[k]for k in('adapter','broker_profile_id','execution_backend','request_id')),'response-identity')
        require(response['http_status']==captures['headers']['http_status'],'response-status-binding')
        known=basic_usage(response['response'].get('usage'))
        normalized=optional_usage_projection(response['response'].get('usage'))
        if known is not None:
            require(type(outcome['usage'])is dict and canonical({k:outcome['usage'].get(k)for k in known})==canonical(known),'normalized-basic-usage')
            if outcome['unknown']is False:
                require(normalized is not None and all(canonical(outcome['usage'].get(k))==canonical(normalized[k])
                    for k in('cached_tokens','reasoning_tokens')),'original-optional-usage-projection')
    elif outcome['usage']is not None:
        # API may already know components when response persistence fails. They
        # remain reported components, not independently verified raw or zero.
        require(outcome['unknown']is True,'unpersisted-usage-must-remain-unknown')
    if outcome['unknown']is False and outcome['dispatched']is True:
        require(known is not None and outcome['not_invoked']is False and outcome['unexpected_overrun']=={} and response['http_status']==200,'known-complete-response')
        # A published done result can coexist with a still-live thread. It does
        # not attest thread termination. An earlier not-done snapshot, however,
        # cannot be promoted from the producer's unknown close/wait outcome.
        require(outcome['settlement']['worker_done']is True and outcome['settlement']['body_complete']is True
            and outcome['settlement']['dispatch_started']is True
            and outcome['settlement']['capture_failure']is None and outcome['settlement']['transport_failure']is None,'known-complete-managed-state')
    return {'outcome':outcome,'receipt_sha256':outcome_sha,'verified_basic_usage':known,
        'accounting_complete':outcome['unknown']is False,
        'late':outcome['settlement']['accounting_only']or outcome['settlement']['actor_elapsed_before_account_seconds']>=budget['work_seconds']}
def verify_actor_transport(run_root,actor_id,result,*,actor_registry):
    """Pure reader for synthetic/authorized future inputs; no actual entrypoint."""
    artifacts=Path(run_root)/'actors'/actor_id/'artifacts';budget=actor_registry[actor_id]
    require(type(result['requests'])is int and 0<=result['requests']<=budget['max_requests'],'actor-request-cap')
    rows=[audit_request(run_root,actor_id,i,actor_registry=actor_registry)for i in range(1,result['requests']+1)]
    guards=list((artifacts/'guards').glob('*.json'))
    require(len(guards)<=1,'orphan-window-refusal')
    if guards:
        g,_=read_json(guards[0]);require(set(g)=={'kind','actor_id','request_metadata','actor_budget','remaining_seconds','ledger_before_sha256','ledger_before_raw_utf8','ledger_after_sha256','request_slot_delta','key_loader_invoked','http_dispatch_started'},'window-refusal-schema')
        require(g['kind']=='registered-primary-window-refusal-v1'and g['actor_id']==actor_id and canonical(g['actor_budget'])==canonical(budget),'window-refusal-registration')
        require(number(g['remaining_seconds'])and g['remaining_seconds']<budget['minimum_dispatch_window_seconds'],'window-refusal-condition')
        require(type(g['request_slot_delta'])is int and g['request_slot_delta']==0 and g['key_loader_invoked']is False and g['http_dispatch_started']is False,'window-refusal-zero-dispatch')
        require(valid_sha(g['ledger_before_sha256'])and g['ledger_before_sha256']==g['ledger_after_sha256'],'window-refusal-ledger-unchanged')
        require(type(g['ledger_before_raw_utf8'])is str and sha(g['ledger_before_raw_utf8'].encode())==g['ledger_before_sha256'],'window-refusal-durable-snapshot')
        strict_json(g['ledger_before_raw_utf8']) # Original controller output may be pretty JSON.
        require(set(g['request_metadata'])==BEFORE_KEYS and g['request_metadata']['request_index']==len(rows)+1 and guards[0].name=='%02d.json'%(len(rows)+1),'window-refusal-next-request')
    if not rows:require(len(guards)==1,'no-native-evidence-requires-explicit-guard')
    bound_names={p.name for p in(artifacts/'requests').glob('*.receipt.json')}
    require(bound_names=={'%02d.receipt.json'%i for i in range(1,len(rows)+1)},'orphan-native-outcome')
    expected_responses={'%02d.response.json'%i for i,r in enumerate(rows,1)if r['outcome']['response_sha256']is not None}
    require({p.name for p in(artifacts/'requests').glob('*.response.json')}==expected_responses,'orphan-native-response')
    expected_captures={Path(ref['receipt_ref']).name for r in rows for ref in r['outcome']['settlement']['capture_receipts']}
    require({p.name for p in(artifacts/'requests').glob('*.transport-*.json')}==expected_captures,'orphan-native-capture')
    complete=all(r['accounting_complete']for r in rows)and result['unknown_usage']is False
    late=next((i for i,r in enumerate(rows,1)if r['late']),None)
    if late is not None:
        require(late==len(rows),'new-request-after-accounting-only')
        require(result['work_deadline_reached']is True,'observed-account-deadline-requires-final-work-close')
    if result['work_deadline_reached']is True:
        require(result['quality']['hard_pass']is False and result['quality']['task_success']is False,'late-task-must-be-false')
        if complete:require(result['status']=='work-deadline-settled-unfinished','settled-unfinished-status')
        if late is not None:
            late_id=rows[late-1]['outcome']['api_response_id']
            require(not any(x.get('api_response_id')==late_id for x in result['api_tool_trace']),'late-native-tools-consumed')
            require(result['final_report']is None or result['final_report'].get('api_response_id')!=late_id,'late-finish-consumed')
        if rows:require((artifacts/'actor.pending.json').is_file(),'unfinished-actor-pending-required')
    if not complete:
        # A callback may durably account known native usage and then raise.
        # Native unknown=False does not clear the actor's callback fence.
        require(any((artifacts/'requests'/('%02d.pending.json'%i)).is_file()for i in range(1,len(rows)+1)),'unknown-request-pending-required')
    return {'raw_integrity':True,'accounting_complete':complete,'known_reported_tokens':sum(r['verified_basic_usage']['total_tokens']for r in rows if r['verified_basic_usage'])if rows else None,
        'work_deadline_reached':result['work_deadline_reached'],'behavior_assessment':'NOT_ASSESSED_BY_TRANSPORT_PROTOTYPE',
        'request_count':len(rows),'dispatch_assessment':'NATIVE_ATTEMPT_RECORDED'if rows else'UNDISPATCHED_REGISTERED_GUARD',
        'settled_unfinished':bool(rows)and result['status']=='work-deadline-settled-unfinished',
        'work_closed_before_dispatch':not rows and result['work_deadline_reached']is True,
        'owned_request_workers_closed':all(r['outcome']['settlement']['worker_done']is True and r['outcome']['settlement']['worker_alive_at_return']is False and r['outcome']['settlement']['attempt_dispatch_gate_closed']is True for r in rows)}
def verify_ledger(run_root,ledger_state,*,actor_registry,configuration,registry_identity,finalization_policy):
    """Independent reconstruction of native bindings and Decimal sums."""
    seen=set();tokens=0;committed={};reserved={};unknown=False;previous_by_actor={};pending=set();dispatched=0;response_ids=[];known_global_stop=False
    require(sha(canonical(configuration))=='db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6','fixed-reviewed-profile-configuration')
    caps=derive_caps(actor_registry,configuration,registry_identity=registry_identity,finalization_policy=finalization_policy)
    require(ledger_state['actor_registry']==actor_registry and ledger_state['registry_identity']==registry_identity,'entire-immutable-ledger-map')
    require(ledger_state['prices']==configuration['prices'],'registered-original-price-schedule')
    require(type(ledger_state['request_slots'])is int and len(ledger_state['requests'])==ledger_state['request_slots']<=caps['request_slots'],'actual-theoretical-slot-cap')
    expected_native={'actors/'+row['actor_id']+'/artifacts/requests/%02d.receipt.json'%row['request_index']for row in ledger_state['requests']}
    actual_native={p.relative_to(Path(run_root)).as_posix()for p in(Path(run_root)/'actors').glob('*/artifacts/requests/*.receipt.json')}
    require(actual_native==expected_native,'all-original-native-outcomes-accounted-once')
    for row in ledger_state['requests']:
        request=row['request_id'];require(request not in seen,'duplicate-request-id');seen.add(request)
        require(not unknown,'request-after-unknown-global-fence')
        require(not known_global_stop,'request-after-known-not-invoked-global-stop')
        native=audit_request(run_root,row['actor_id'],row['request_index'],actor_registry=actor_registry);out=native['outcome']
        require(all(canonical(row.get(k))==canonical(out.get(k))for k in BEFORE_KEYS)
            and out['reservation_receipt_sha256']==row['reservation_receipt_sha256'], 'durable-reserve-exact-native-request-binding')
        timing=ledger_state['actor_clocks'].get(row['actor_id'])
        require(type(timing)is dict and set(timing)=={'schema','started_monotonic','work_deadline_monotonic'}
            and timing['schema']=='collector-first-setup-absolute-work-deadline-v1'
            and number(timing['started_monotonic'])and number(timing['work_deadline_monotonic'])
            and timing['work_deadline_monotonic']-timing['started_monotonic']==180
            and row['work_deadline_monotonic']==timing['work_deadline_monotonic']
            and row['settlement_deadline_monotonic']==timing['work_deadline_monotonic']+600,
            'native-reserve-same-original-ledger-actor-clock')
        require(canonical(row.get('receipt'))==canonical(dict(out,receipt_sha256=native['receipt_sha256'])),'callback-exact-native-outcome')
        require(row['reservation_receipt_path']=='reservations/'+sha(request.encode('utf-8'))+'.json','fixed-owned-reservation-reference')
        receipt,_=read_json(Path(run_root)/row['reservation_receipt_path'],row['reservation_receipt_sha256'])
        require(receipt['request_id']==request and receipt['status']=='reserved-before-send','immutable-reserve')
        require(all(canonical(receipt.get(k))==canonical(row.get(k))for k in BEFORE_KEYS|{'actor_id'}),'immutable-reserve-bindings')
        previous=previous_by_actor.get(row['actor_id'])
        require(not(previous is not None and previous.get('connect_retry_authorization')is not None)
            or row['retry_of_request_id']==previous['request_id'],'outstanding-connect-retry-must-be-consumed')
        require(row['request_index']==(previous['request_index']+1 if previous else 1)
            and row['request_index']<=actor_registry[row['actor_id']]['max_requests'],'actor-contiguous-bounded-slots')
        if row['retry_of_request_id']is not None:
            require(previous is not None and row['retry_of_request_id']==previous['request_id'],'retry-immediate-same-actor-parent')
            parent=previous['receipt'];transport=parent['transport']
            require(parent['not_invoked']is True and parent['dispatched']is False and parent['unknown']is False and parent['usage']is None
                and parent['unexpected_overrun']=={} and parent['error_type']=='ResponseUnknown'
                and transport=={'phase':'connect','exception_class':transport.get('exception_class'),'connection_attempted':True,'http_dispatch':'not_started'}
                and transport['exception_class']in{'TimeoutError','gaierror','ConnectionRefusedError','ConnectionResetError'},'retry-parent-confirmed-before-http')
            expected={'policy':'confirmed-pre-http-connect-once-v1','connect_retry_authorized':True,'prior_request_id':previous['request_id'],
                'prior_request_index':previous['request_index'],'request_payload_sha256':previous['request_payload_sha256'],
                'input_task_sha256':previous['input_task_sha256'],'prior_receipt_sha256':previous['receipt']['receipt_sha256']}
            require(canonical(previous.get('connect_retry_authorization'))==canonical(expected)and previous.get('retry_consumed_by')==request,'retry-exact-authority')
            require(row['request_payload_sha256']==previous['request_payload_sha256']and row['input_task_sha256']==previous['input_task_sha256'],'retry-identical-payload-task')
            require(previous.get('retry_of_request_id')is None,'retry-only-once')
        previous_by_actor[row['actor_id']]=row
        if row.get('connect_retry_authorization')is not None:
            transport=out['transport']
            require(row['status']=='confirmed-not-invoked-before-send'and out['not_invoked']is True
                and out['dispatched']is False and out['unknown']is False and out['usage']is None
                and out['unexpected_overrun']=={}and out['error_type']=='ResponseUnknown'
                and transport=={'phase':'connect','exception_class':transport.get('exception_class'),'connection_attempted':True,'http_dispatch':'not_started'}
                and transport['exception_class']in{'TimeoutError','gaierror','ConnectionRefusedError','ConnectionResetError'},'retry-authority-only-confirmed-pre-http-parent')
            expected={'policy':'confirmed-pre-http-connect-once-v1','connect_retry_authorized':True,
                'prior_request_id':row['request_id'],'prior_request_index':row['request_index'],
                'request_payload_sha256':row['request_payload_sha256'],'input_task_sha256':row['input_task_sha256'],
                'prior_receipt_sha256':native['receipt_sha256']}
            require(row['connect_retry_authorization']==expected and row['retry_of_request_id']is None,'original-single-connect-retry-authority')
        provider=row['provider'];usage=out['usage'];basic=type(usage)is dict and all(type(usage.get(k))is int and usage[k]>=0 for k in('input_tokens','output_tokens','total_tokens'))and usage['total_tokens']==usage['input_tokens']+usage['output_tokens']
        dispatched+=int(out['dispatched'])
        expected_reservation={currency:str((Decimal(row['input_utf8_bytes'])*Decimal(price['input_miss'])+Decimal(8192)*Decimal(price['output']))/1_000_000)
            for currency,price in configuration['prices'][provider].items()}
        require(canonical(row['reservation'])==canonical(expected_reservation)and receipt['reservation']==row['reservation'],'original-conservative-reserve-arithmetic')
        if basic:
            tokens+=usage['total_tokens'];require(row.get('known_usage_accounted')is True,'known-basic-accounted-once')
            for currency,price in ledger_state['prices'][provider].items():
                amount=(Decimal(usage['input_tokens'])*Decimal(price['input_miss'])+Decimal(usage['output_tokens'])*Decimal(price['output']))/1_000_000
                key=(provider,currency);committed[key]=committed.get(key,Decimal(0))+amount
        if row['status']=='unknown-reservation-retained':
            pending.add(request)
            unknown=True;require(request in ledger_state['pending'],'unknown-pending-retained')
            for currency,amount in row['reservation'].items():
                key=(provider,currency);reserved[key]=reserved.get(key,Decimal(0))+Decimal(amount)
        else:
            require(row['status']in('reported-usage-estimate-committed','confirmed-not-invoked-before-send')and out['unknown']is False,'known-row-closed-status')
            if row['status']=='reported-usage-estimate-committed':
                require(out['dispatched']is True and out['not_invoked']is False and native['verified_basic_usage']is not None
                    and type(out['api_response_id'])is str and out['api_response_id']and out['api_response_id']not in response_ids
                    and valid_sha(out['response_sha256'])and all(out['usage'].get(k)is None or type(out['usage'][k])is int
                        and 0<=out['usage'][k]<=out['usage'][cap]for k,cap in(('cached_tokens','input_tokens'),('reasoning_tokens','output_tokens'))),
                    'reported-status-requires-original-dispatched-usage')
                response_ids.append(out['api_response_id'])
            else:
                transport=out['transport']
                require(out['dispatched']is False and out['not_invoked']is True and out['usage']is None
                    and all(out.get(n)is None for n in('api_response_id','response_sha256','model_reported'))
                    and type(transport.get('connection_attempted'))is bool and transport.get('http_dispatch')=='not_started'
                    and transport.get('phase')in{'preparation','worker-before-request','payload-serialize','connection-create','connect'},
                    'not-invoked-status-requires-original-no-http-proof')
                if row.get('connect_retry_authorization')is None:known_global_stop=True
            require(request not in ledger_state['pending'],'known-request-pending-removed')
    require(set(ledger_state['pending'])==pending,'all-and-only-pending-reservations')
    require(type(ledger_state['known_reported_tokens'])is int and tokens==ledger_state['known_reported_tokens'],'known-token-total')
    require(type(ledger_state['dispatched_requests'])is int and ledger_state['dispatched_requests']==dispatched,'all-dispatches-once')
    require(ledger_state['api_response_ids']==response_ids,'all-original-committed-response-identities-once')
    require(type(ledger_state['accounts'])is dict and set(ledger_state['accounts'])==set(configuration['prices']),'complete-account-provider-projection')
    for provider,currencies in ledger_state['accounts'].items():
        require(type(currencies)is dict and set(currencies)==set(configuration['prices'][provider]),'complete-account-currency-projection')
        for currency,value in currencies.items():
            require(type(value)is dict and set(value)=={'committed_estimate','reserved_estimate','cap'},'closed-account-estimate-schema')
            require(Decimal(value['committed_estimate'])==committed.get((provider,currency),Decimal(0)),'committed-estimate')
            require(Decimal(value['reserved_estimate'])==reserved.get((provider,currency),Decimal(0)),'retained-estimate')
            require(value['cap']==caps[provider+'_'+currency],'whole-finite-map-reservation-cap')
    durable_actor_pending=any((Path(run_root)/'actors').glob('*/artifacts/requests/*.pending.json'))
    fault=(Path(run_root)/'ledger.failure.json').exists()
    return {'raw_integrity':True,'accounting_complete':not unknown and not durable_actor_pending and not fault,'known_reported_tokens':tokens,'request_slots':len(seen),'persistence_fault_observed':fault}
