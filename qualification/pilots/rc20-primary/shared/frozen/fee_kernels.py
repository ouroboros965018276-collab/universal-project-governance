"""UNBOUND future-only 24-role independent raw-audit prototype.

Pure kernels below consume synthetic/in-memory evidence, never a producer grade.
Actual file ingestion is deliberately CLOSED until ROOT freezes backend/adoption,
collector/ledger and task/runtime identities. This is not an actual-study auditor
approval, executor, quality release, efficacy study or recovery proof.
"""
from __future__ import annotations
import argparse
import copy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import random

PROFILE_ID = 'thinking-enabled-flash-8192-v1'
CONFIG_SHA = 'f5ae975f21072974c9da04da33e8081a2e2fc44be6769c2cbe8c36e82d58081b'
MODELS = {'deepseek':'deepseek-flash','mimo':'mimo-v2.6-flash'}
PRICES = {'deepseek':{'USD':{'input_hit':'.006','input_miss':'.30','output':'1.20'}},
    'mimo':{'CNY':{'input_hit':'.02','input_miss':'1','output':'2'},
            'USD':{'input_hit':'.0028','input_miss':'.14','output':'.28'}}}
CAPS = {'actors':24,'request_slots':288,'known_reported_tokens_soft':3000000,
    'round_seconds_soft':7200,'deepseek_USD':'4','mimo_CNY':'12','mimo_USD':'2',
    'ordinary_strict_failures':None}
ARMS = ('rc19','attention','full')
MINIMUM_DISPATCH_SECONDS = 15
PLANNED_BACKEND = 'docker-cpython-finite-v1'  # Name only; schema/adoption remain UNBOUND.
READINESS_BINDINGS = {'backend_source_sha256':'UNBOUND','backend_schema_sha256':'UNBOUND',
    'backend_adoption_sha256':'UNBOUND','real_container_validation_sha256':'UNBOUND',
    'collector_sha256':'UNBOUND','ledger_sha256':'UNBOUND','task_seed':'UNBOUND',
    'namespace':'UNBOUND','schedule_seed':'UNBOUND','baseline18_map_sha256':'UNBOUND',
    'full18_map_sha256':'UNBOUND','manual_helper_sha256':'UNBOUND','manual_rubric_sha256':'UNBOUND'}


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def raw_sha(raw):return hashlib.sha256(raw).hexdigest()
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def is_sha(value):return type(value) is str and len(value)==64 and all(x in '0123456789abcdef' for x in value)


class EvidenceError(ValueError):pass
class NotReady(EvidenceError):pass


def require(value,code):
    if not value:raise EvidenceError(code)


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate-json-key');result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(EvidenceError('nonfinite-json')))


def require_actual_ready():
    # No caller flag or synthetic fixture can bind these frozen-source identities.
    missing=[k for k,v in READINESS_BINDINGS.items() if v in (None,'UNBOUND')]
    if missing:raise NotReady('actual-audit-blocked-unbound:'+','.join(missing))
    raise NotReady('actual-file-ingestion-not-implemented-before-final-backend-schema')


def audit_study(study,*,terminal_confirmed=False):
    if terminal_confirmed is not True:raise NotReady('terminal-confirmation-required-before-any-study-read')
    require_actual_ready()  # Deliberately before Path/read/glob or any actor grading.


def check_configuration(configuration):
    require(digest(configuration)==CONFIG_SHA and configuration.get('profile_id')==PROFILE_ID,'explicit-flash-configuration-identity')
    require(configuration.get('prices')==PRICES,'exact-independent-price-table')
    settings=configuration['providers']
    for provider,model in MODELS.items():
        require(settings.get(provider)=={'model':model,'thinking':'enabled','output_cap':8192,
            'reasoning_effort':'low' if provider=='deepseek' else None},'exact-explicit-provider-mode')
    return True


def conservative_estimate(provider,inputs,outputs):
    require(provider in PRICES and type(inputs) is int and inputs>=0 and type(outputs) is int and outputs>=0,'fee-input-types')
    return {currency:(Decimal(inputs)*Decimal(rate['input_miss'])+Decimal(outputs)*Decimal(rate['output']))/Decimal(1000000)
        for currency,rate in PRICES[provider].items()}


def raw_usage(value):
    if type(value) is not dict:return None
    keys=('prompt_tokens','completion_tokens','total_tokens')
    if any(type(value.get(k)) is not int or value[k]<0 for k in keys):return None
    inputs,outputs,total=[value[k] for k in keys]
    if inputs+outputs!=total:return None
    details=[]
    for field in ('prompt_tokens_details','completion_tokens_details'):
        item=value.get(field)
        if item is None:item={}
        if type(item) is not dict:return None
        details.append(item)
    cached=details[0].get('cached_tokens');alias=value.get('prompt_cache_hit_tokens')
    if alias is not None:
        if type(alias) is not int or alias<0:return None
        if cached is not None and (type(cached) is not int or cached!=alias):return None
        cached=alias
    reasoning=details[1].get('reasoning_tokens')
    for item,cap in ((cached,inputs),(reasoning,outputs)):
        if item is not None and (type(item) is not int or not 0<=item<=cap):return None
    return {'input_tokens':inputs,'output_tokens':outputs,'total_tokens':total,
        'cached_tokens':cached,'reasoning_tokens':reasoning}


def check_deadline(value):
    fields={'schema_version','actor_timeout_seconds','actor_elapsed_before_bounded_post_seconds',
        'bounded_post_timeout_seconds','actor_elapsed_after_bounded_post_seconds'}
    require(type(value) is dict and set(value)==fields and value['schema_version']=='bounded-post-wait-v1','deadline-shape')
    nums=[value[k] for k in fields if k!='schema_version'];require(all(finite(x) for x in nums),'deadline-finite-types')
    before=value['actor_elapsed_before_bounded_post_seconds'];wait=value['bounded_post_timeout_seconds'];after=value['actor_elapsed_after_bounded_post_seconds']
    require(value['actor_timeout_seconds']==180 and wait>0 and abs(before+wait-180)<=1e-6 and after>=before,'actual-bounded-wait-arithmetic')
    return {'wait_seconds':wait,'before_seconds':before,'after_seconds':after,
        'boundary':'Local bounded-post argument/actor samples only; not socket timeout, remote compute or HTTP dispatch proof.'}


def check_dispatch_guard(value,*,has_reservation,has_dispatch):
    fields={'schema_version','actor_id','provider','model_requested','profile_id','profile_configuration_sha256',
        'input_task_sha256','request_payload_sha256','request_id','request_index','outer_started_monotonic_seconds',
        'guard_sample_monotonic_seconds','outer_elapsed_seconds','outer_remaining_seconds','actor_budget_seconds',
        'minimum_dispatch_window_seconds','decision','reason','clock_scope'}
    require(type(value) is dict and set(value)==fields and value['schema_version']=='actor-outer-dispatch-guard-v1','guard-shape')
    require(value['provider'] in MODELS and value['model_requested']==MODELS[value['provider']] and value['profile_id']==PROFILE_ID
        and value['profile_configuration_sha256']==CONFIG_SHA and is_sha(value['input_task_sha256']) and is_sha(value['request_payload_sha256']),
        'guard-profile-task-payload-identity')
    require(type(value['actor_id']) is str and value['actor_id'] and type(value['request_id']) is str and value['request_id']
        and type(value['request_index']) is int and 1<=value['request_index']<=12,'guard-role-request-identity')
    require(all(finite(value[k]) for k in ('outer_started_monotonic_seconds','guard_sample_monotonic_seconds','outer_elapsed_seconds',
        'minimum_dispatch_window_seconds','actor_budget_seconds')) and type(value['outer_remaining_seconds']) in (int,float)
        and math.isfinite(value['outer_remaining_seconds']),'guard-finite-types')
    # Remaining is raw180-elapsed, not clamped at0. Negative is a local refusal.
    require(value['minimum_dispatch_window_seconds']==15 and value['actor_budget_seconds']==180
        and abs(value['guard_sample_monotonic_seconds']-value['outer_started_monotonic_seconds']-value['outer_elapsed_seconds'])<=1e-6
        and abs(value['outer_remaining_seconds']+value['outer_elapsed_seconds']-180)<=1e-6,'guard-outer-window-arithmetic')
    allowed=value['outer_remaining_seconds']>=15
    require(value['decision']==('allowed' if allowed else 'refused') and value['reason']==(None if allowed else 'insufficient-outer-dispatch-window')
        and type(value['clock_scope']) is str and 1<=len(value['clock_scope'])<=1024,'guard-threshold')
    if not allowed:require(not has_reservation and not has_dispatch,'refusal-has-no-slot-reservation-or-dispatch')
    return allowed


def check_collection(manifest,observations,status):
    """Pure schedule kernel from independently audited role classifications.

    No raw producer grade is ingested by this prototype. Full native/backend
    classification is still gated UNBOUND at the actual ingestion boundary.
    """
    require('ordinary-strict-failure-stop' not in status,'no-two-ordinary-stop-in-new-study')
    ids=[r['actor_id'] for r in manifest];rows={r['actor_id']:r for r in observations}
    require(len(rows)==len(observations) and all(n in ids for n in rows),'unique-observed-registered-role')
    require([ids.index(r['actor_id']) for r in observations]==sorted(ids.index(r['actor_id']) for r in observations),'fixed-observed-order')
    severe=False;ordinary=0;public=[];gap=False
    for role in manifest:
        identifier=role['actor_id'];row=rows.get(identifier)
        predecessor=rows.get(role['depends_on']) if role['stage']=='receiver' else None
        eligible=role['stage']=='source' or predecessor is not None and predecessor['classification']=='strict-pass'
        if row is None:
            require(not eligible or status!='completed','completed-missing-eligible-role')
            if eligible:gap=True
            public.append({'actor_id':identifier,'observed':False,'known_usage':None,'runtime_seconds':None});continue
        require(not severe and not gap and eligible,'no-role-after-severe-gap-or-failed-own-source')
        classification=row['classification'];require(classification in {'strict-pass','ordinary-fail','local-refusal','unknown','unsafe'},'independent-classification-enum')
        if classification in {'ordinary-fail','local-refusal'}:ordinary+=1
        if classification in {'unknown','unsafe'}:severe=True;require(status!='completed','severe-is-global-terminal')
        public.append({'actor_id':identifier,'observed':True,'known_usage':row['known_usage'],'runtime_seconds':row['runtime_seconds']})
    return {'ordinary_failures':ordinary,'roles':public,'comparison':'BLOCKED if any complete pair/cost is missing; no dropping or zero imputation'}


def expected_blocks(seed):
    require(type(seed) is int,'fixed-schedule-seed')
    rng=random.Random(seed);blocks=[]
    for kind in ('document','core'):
        directions=[('deepseek','mimo'),('mimo','deepseek')];rng.shuffle(directions)
        blocks.extend((kind,*direction) for direction in directions)
    arms=list(ARMS);rng.shuffle(arms)
    orders=[arms[i:]+arms[:i] for i in range(3)]+[list(reversed(arms))]
    return list(zip(blocks,orders))


def check_manifest(rows,seed):
    require(type(rows) is list and len(rows)==24,'all24-predeclared-roles')
    identifiers=set();projects=set();pair_keys=set();index=0
    fields={'actor_id','chain_id','pair_key','block_index','kind','stage','provider','model','arm',
        'project_name','context_id','depends_on'}
    for block_index,((kind,source,receiver),arms) in enumerate(expected_blocks(seed)):
        pair_key=None
        for arm in arms:
            pair=rows[index:index+2];index+=2;s,v=pair
            for row,stage,provider in ((s,'source',source),(v,'receiver',receiver)):
                require(type(row) is dict and set(row)==fields,'manifest-exact-fields')
                require(row['actor_id'] not in identifiers and type(row['actor_id']) is str,'unique-role-id');identifiers.add(row['actor_id'])
                require(row['kind']==kind and row['stage']==stage and row['provider']==provider and row['model']==MODELS[provider]
                    and row['arm']==arm and row['block_index']==block_index and row['context_id']==kind+'-'+stage,'registered-role-provider-context-order')
            require(s['chain_id']==v['chain_id']==s['project_name']==v['project_name'] and s['project_name'] not in projects,'own-independent-arm-project')
            projects.add(s['project_name'])
            require(s['depends_on'] is None and v['depends_on']==s['actor_id'],'own-adjacent-source-receiver')
            require(s['pair_key']==v['pair_key'] and (pair_key is None or pair_key==s['pair_key']),'cross-arm-pair-key')
            pair_key=s['pair_key']
        require(pair_key not in pair_keys,'distinct-family-direction-block');pair_keys.add(pair_key)
    return True


def receiver_input(blueprint,source_files):
    task=copy.deepcopy(blueprint);task['initial_files']=dict(source_files)
    protected={n:raw_sha(text.encode()) for n,text in source_files.items() if n not in task['writable_files']}
    task['behavior_contract']['protected_files']=protected
    return task


def check_incoming(source_task,source_final,source_prefix,receiver_task,blueprint,receipt):
    hashes={n:raw_sha(t.encode()) for n,t in source_final.items()}
    require(source_prefix['state_sha256']==digest(hashes) and source_prefix['native_finish_present'],
        'own-source-prefix-state-and-native-report-required')
    require(all(hashes.get(n)==h for n,h in source_task['behavior_contract']['protected_files'].items()),
        'own-source-frozen-protected-scope')
    expected=receiver_input(blueprint,source_final)
    require(receiver_task==expected,'receiver-initial-from-own-actual-source-not-reference')
    require(receipt=={'source_snapshot_sha256':digest(hashes),'receiver_initial_files_sha256':digest(source_final),
        'receiver_protected_files_sha256':digest(expected['behavior_contract']['protected_files']),
        'conversation_history_transferred':False,'admission':'strict-native-current-disk-partial-stage'},'typed-source-raw-and-protection-hash-domains')
    return {'snapshot_binding_verified':True,
        'actual_source_admission':'BLOCKED until full independent native/positive/real-backend schema is bound'}


def replay_hash_prefix(task,events,traces,terminal_snapshot,report=None):
    state={n:raw_sha(t.encode()) for n,t in task['initial_files'].items()};protected=task['behavior_contract']['protected_files'];previous=None
    require(len(events)==len(traces),'every-executed-event-has-native-receipt')
    for index,(event,trace) in enumerate(zip(events,traces),1):
        require(event['sequence']==index and event['arguments_sha256']==digest(event['arguments'])
            and event['result_sha256']==digest(event['result']),'event-content-identity')
        if event['tool']=='repo_patch' and event['result'].get('ok') is True:
            for op in event['arguments']['operations']:
                require(set(op)=={'path','old_sha256','new_text'} and op['path'] in task['writable_files']
                    and state.get(op['path'])==op['old_sha256'],'writable-current-patch-precondition')
                state[op['path']]=raw_sha(op['new_text'].encode())
        require(digest(state)==event['state_sha256'],'every-prefix-current-state')
        require(trace['broker_sequence']==index and trace['tool']==event['tool'] and trace['broker_event_sha256']==digest(event)
            and trace['arguments_sha256']==event['arguments_sha256'] and trace['result_sha256']==event['result_sha256']
            and trace['state_sha256']==event['state_sha256'],'native-event-exact-binding')
        require(trace['previous_chain_sha256']==previous and trace['chain_sha256']==digest({k:v for k,v in trace.items() if k!='chain_sha256'}),'native-hashchain')
        previous=trace['chain_sha256']
    require(state==terminal_snapshot,'no-dirty-writable-empty-journal-or-unverified-tail')
    require(all(state.get(n)==h for n,h in protected.items()),'own-stage-protected-byte-integrity')
    if report is not None:
        require(report['state_sha256']==digest(state) and report['last_broker_chain_sha256']==previous
            and report['broker_event_count']==len(events),'accepted-report-current-prefix')
    return {'state_sha256':digest(state),'protected_unchanged':True,'journal_events':len(events),'native_finish_present':report is not None,
        'quality':'UNASSESSED; native API envelope, all positive checks and real backend still required'}


def request_payload(provider,messages,tools):
    require(provider in MODELS,'registered-provider')
    result={'model':MODELS[provider],'messages':messages,'tools':tools,'tool_choice':'auto','stream':False,'thinking':{'type':'enabled'},
        'max_tokens' if provider=='deepseek' else 'max_completion_tokens':8192}
    if provider=='deepseek':result['reasoning_effort']='low'
    return result


def check_payload(provider,messages,tools,metadata):
    require(len(tools)==6 and {x['function']['name'] for x in tools}=={'repo_read','repo_search','repo_patch','repo_validate','repo_status','repo_finish'},'five-broker-tools-plus-native-finish')
    payload=request_payload(provider,messages,tools);raw=canonical(payload)
    require(metadata['request_payload_sha256']==raw_sha(raw) and metadata['input_utf8_bytes']==len(raw)
        and len(raw)<=131072 and metadata['profile_id']==PROFILE_ID and metadata['profile_configuration_sha256']==CONFIG_SHA,'exact-independent-request-payload-and-cap')
    return payload


def response_frame(artifact_raw,receipt):
    artifact=strict_json(artifact_raw);raw=artifact['response'];choices=raw.get('choices')
    require(artifact.get('http_status')==200 and type(choices) is list and len(choices)==1
        and type(raw.get('id')) is str and raw['id'] and type(raw.get('model')) is str and raw['model'],'single-known-api-response')
    require(receipt.get('response_sha256')==raw_sha(artifact_raw) and receipt.get('api_response_id')==raw['id']
        and receipt.get('model_reported')==raw['model'] and receipt.get('unknown') is False
        and receipt.get('not_invoked') is False and receipt.get('dispatched') is True,'api-response-receipt-identity')
    choice=choices[0];message=choice.get('message')
    require(type(message) is dict and message.get('role')=='assistant' and type(message.get('tool_calls')) is list,'native-assistant-call-frame')
    return raw,choice,message['tool_calls']


def check_native_event(artifact_raw,receipt,event,trace):
    raw,choice,calls=response_frame(artifact_raw,receipt)
    require(choice.get('finish_reason')=='tool_calls','tool-call-finish-reason')
    selected=[c for c in calls if c.get('id')==trace.get('tool_call_id')]
    require(len(selected)==1 and all(c.get('function',{}).get('name')!='repo_finish' for c in calls),'real-broker-not-mixed-native-finish')
    call=selected[0];function=call.get('function')
    require(call.get('type')=='function' and type(call.get('id')) is str and call['id'].strip()
        and type(function) is dict and function.get('name')==event['tool'] and type(function.get('arguments')) is str,'actual-native-event-tool-id-type')
    require(digest(strict_json(function['arguments']))==event['arguments_sha256']
        and trace['broker_event_sha256']==digest(event) and trace['request_index']==receipt['request_index']
        and trace['response_artifact_sha256']==raw_sha(artifact_raw) and trace['api_response_id']==raw['id']
        and trace['api_model']==raw['model'],'actual-native-arguments-response-event-binding')
    return True


def check_native_finish(artifact_raw,receipt,report,terminal_state,last_chain,event_count,previous_call_ids,*,receipt_raw):
    raw,choice,calls=response_frame(artifact_raw,receipt)
    require(choice.get('finish_reason')=='tool_calls' and len(calls)==1,'sole-native-finish-with-tool-reason')
    call=calls[0];function=call.get('function')
    require(call.get('type')=='function' and type(call.get('id')) is str and call['id'].strip()
        and call['id'] not in previous_call_ids and type(function) is dict and function.get('name')=='repo_finish'
        and type(function.get('arguments')) is str,'finish-unique-id-type-and-tool')
    original=function['arguments'];value=strict_json(original)
    require(type(value) is dict and set(value)=={'summary','validation','helper_gap'} and type(value['summary']) is str
        and value['summary'].strip() and value['validation'] in ('passed','failed')
        and value['helper_gap']=='project_tool unavailable in bounded broker','strict-original-native-finish-schema')
    require(report['arguments_raw']==original and report['arguments_utf8_sha256']==raw_sha(original.encode())
        and report['arguments_sha256']==digest(value) and report['report']==value,'finish-original-arguments-never-cleaned')
    require(report['state_sha256']==terminal_state and report['last_broker_chain_sha256']==last_chain
        and report['broker_event_count']==event_count and report['tool_call_id']==call['id']
        and report['api_response_id']==raw['id'] and report['api_model']==raw['model']
        and report['request_index']==receipt['request_index'] and report['response_artifact_sha256']==raw_sha(artifact_raw)
        and strict_json(receipt_raw)==receipt and report['request_receipt_sha256']==raw_sha(receipt_raw)
        and type(report['api_tool_attempt_sequence']) is int and 1<=report['api_tool_attempt_sequence']<=32,
        'native-finish-current-state-prefix-and-request-binding')
    return {'native_report_verified':True,'report_arguments_sha256':digest(value),
        'quality':'UNASSESSED; file/VM/real-backend and external only-veto facts are not supplied by repo_finish'}


def observed_basic_components(raw_requests):
    """Retain observed raw basic usage even if a later integrity check fails."""
    fees={p:{c:Decimal(0) for c in cs} for p,cs in PRICES.items()};total=0;missing=0
    for record in raw_requests:
        raw=record.get('raw_usage');provider=record.get('metadata',{}).get('provider')
        if type(raw) is not dict or provider not in PRICES or any(type(raw.get(k)) is not int or raw[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens')) or raw['prompt_tokens']+raw['completion_tokens']!=raw['total_tokens']:
            missing+=1;continue
        total+=raw['total_tokens']
        for currency,amount in conservative_estimate(provider,raw['prompt_tokens'],raw['completion_tokens']).items():fees[provider][currency]+=amount
    return {'raw_basic_reported_token_subtotal':total,'requests_without_valid_basic_usage':missing,
        'all_raw_basic_components_estimate':{p:{c:str(v) for c,v in cs.items()} for p,cs in fees.items()},
        'boundary':'Observed basic counts only; invalid details/telemetry never become normalized usage or a zero invoice.'}


def check_ledger(ledger,raw_requests,configuration):
    observed=observed_basic_components(raw_requests)
    pending=ledger.get('pending',{});priced=set();exposure={p:{c:Decimal(0) for c in cs} for p,cs in PRICES.items()}
    for record in raw_requests:
        meta=record.get('metadata',{});identifier=meta.get('request_id');provider=meta.get('provider');size=meta.get('input_utf8_bytes')
        if identifier in pending and identifier not in priced and provider in PRICES and type(size) is int and 0<=size<=131072 and meta.get('output_cap')==8192:
            priced.add(identifier)
            for currency,amount in conservative_estimate(provider,size,8192).items():exposure[provider][currency]+=amount
    observed['original_pending_reservation_count']=len(pending)
    observed['pending_estimate_from_valid_raw_metadata']={p:{c:str(v) for c,v in cs.items()} for p,cs in exposure.items()}
    observed['pending_not_priceable_from_saved_metadata']=len(set(pending)-priced)
    observed['pending_fee_boundary']='Retained pending estimates may overlap observed charges. Unpriceable pending exposure is unknown, never zero.'
    try:
        result=_check_ledger(ledger,raw_requests,configuration)
    except EvidenceError as error:
        error.observed_accounting=observed
        raise
    result['observed_accounting']=observed
    return result


def _check_ledger(ledger,raw_requests,configuration):
    check_configuration(configuration);require(ledger['caps']==CAPS and ledger['ordinary_failure_stop_limit'] is None,'new24-caps-ordinary-continue-null')
    require(ledger['profile_id']==PROFILE_ID and ledger['profile_configuration_sha256']==CONFIG_SHA,'ledger-explicit-new-profile')
    require(len(raw_requests)<=288 and ledger['request_slots']==len(raw_requests),'every-reservation-counts-one-slot')
    ids=set();response_ids=set();by_actor={};known=0;committed={p:{c:Decimal(0) for c in cs} for p,cs in PRICES.items()};reserved=copy.deepcopy(committed);unknown_seen=False
    for record in raw_requests:
        metadata=record['metadata'];identifier=metadata['request_id'];provider=metadata['provider'];actor=metadata['actor_id']
        require(identifier not in ids and not unknown_seen,'unique-no-request-after-unknown');ids.add(identifier)
        by_actor[actor]=by_actor.get(actor,0)+1;require(metadata['request_index']==by_actor[actor]<=12,'actor12-request-prefix')
        require(provider in MODELS and metadata['model_requested']==MODELS[provider] and metadata['profile_id']==PROFILE_ID
            and metadata['profile_configuration_sha256']==CONFIG_SHA and metadata['output_cap']==8192
            and type(metadata['input_utf8_bytes']) is int and 0<=metadata['input_utf8_bytes']<=131072,'reservation-model-profile-input-cap')
        require(record['reservation_sha256']==raw_sha(record['reservation_raw']) and strict_json(record['reservation_raw'])==record['reservation']
            and all(record['reservation'].get(k)==v for k,v in metadata.items()),'durable-original-reservation-metadata-binding')
        expect=conservative_estimate(provider,metadata['input_utf8_bytes'],8192)
        require(record['reservation']['estimate']=={c:str(v) for c,v in expect.items()},'conservative-before-send-reservation')
        receipt=record.get('receipt');usage=None if receipt is None else raw_usage(record.get('raw_usage'))
        not_invoked=receipt is not None and receipt.get('not_invoked') is True
        if not_invoked:
            require(receipt.get('dispatched') is False and receipt.get('unknown') is False and usage is None,'not-invoked-cannot-carry-usage-or-dispatch')
        if usage is not None:
            require(receipt.get('not_invoked') is False and receipt.get('dispatched') is True,'known-usage-is-received-not-refused')
            check_deadline(receipt['deadline_telemetry']);known+=usage['total_tokens']
            for c,v in conservative_estimate(provider,usage['input_tokens'],usage['output_tokens']).items():committed[provider][c]+=v
            rid=receipt.get('api_response_id');require(type(rid) is str and rid and rid not in response_ids,'duplicate-response-retains-charge-but-blocks-integrity');response_ids.add(rid)
        uncertain=not not_invoked and (receipt is None or receipt.get('unknown') is not False or usage is None)
        if uncertain:
            require(identifier in ledger['pending'],'unknown-keeps-original-reserve-not-zero');unknown_seen=True
            for c,v in expect.items():reserved[provider][c]+=v
        else:require(identifier not in ledger['pending'],'settled-request-no-stale-pending')
    require(known==ledger['known_reported_tokens'],'all-known-usage-summed-without-cache-reasoning-doublecount')
    require(not unknown_seen or ledger['status']!='completed','completed-cannot-hide-unknown')
    return {'known_reported_tokens':known,'known_estimate':{p:{c:str(v) for c,v in cs.items()} for p,cs in committed.items()},
        'retained_unknown_estimate':{p:{c:str(v) for c,v in cs.items()} for p,cs in reserved.items()},'pending':len(ledger['pending']),
        'boundary':'Independent Decimal peak/all-input-miss estimates, not invoices. Currencies alternatives, not summed; unknown reserves may overlap known fees.'}


def check_timing(roles,chains,timing,launch):
    attributed=0.;observed={}
    for role in roles:
        identifier=role['actor_id']
        if not role['invoked']:
            require(role['runtime_seconds'] is None and role['timing'] is None,'missing-role-cost-null-not-zero');continue
        value=role['timing'];keys={'inclusive_seconds','pre_control_seconds','planner_seconds','incoming_seconds','container_seconds','attributed_seconds'}
        require(set(value)==keys and all(finite(x) for x in value.values()),'role-timing-finite-schema')
        require(abs(value['attributed_seconds']-value['inclusive_seconds']-value['pre_control_seconds'])<1e-6,'role-control-once')
        require(value['planner_seconds']+value['incoming_seconds']+value['container_seconds']<=value['inclusive_seconds']+1e-6,'nested-components-not-extra-cost')
        require(role['runtime_seconds']==value['attributed_seconds'],'role-published-cost-equals-attribution')
        attributed+=role['runtime_seconds'];observed[identifier]=role['runtime_seconds']
    for chain in chains:
        values=[observed[x] for x in chain['roles'] if x in observed]
        require(chain['wall_seconds'] is None if not values else finite(chain['wall_seconds']) and abs(sum(values)-chain['wall_seconds'])<1e-6,'chain-bracket-once-missing-null')
    require(all(finite(timing[k]) for k in ('runtime_seconds','shared_initial_seconds','shared_terminal_seconds')) and finite(launch),'runtime-and-launch-finite')
    require(abs(timing['runtime_seconds']-attributed-timing['shared_initial_seconds']-timing['shared_terminal_seconds'])<1e-6,'runtime-role-shared-partition')
    require(timing['publication_tail_seconds'] is None,'publication-tail-unknown-not-zero')
    require(abs(timing['launch_plus_runtime_seconds']-launch-timing['runtime_seconds'])<1e-6,'research-launch-separate-once')
    return {'runtime_seconds':timing['runtime_seconds'],'launch_seconds':launch,'publication_tail_seconds':None,
        'boundary':'Recorded monotonic arithmetic, not physical-clock attestation; all subsets included once.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--study-root',required=True);parser.add_argument('--terminal-confirmed',action='store_true')
    args=parser.parse_args()
    try:audit_study(args.study_root,terminal_confirmed=args.terminal_confirmed)
    except NotReady as error:
        print(json.dumps({'status':'BLOCKED','reason':str(error),'actual_study_read':False,'quality':'UNASSESSED','benefit':'NOT_ESTABLISHED'}));raise SystemExit(2)


if __name__=='__main__':main()
