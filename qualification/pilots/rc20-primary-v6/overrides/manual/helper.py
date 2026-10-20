"""One frozen extraction, one complete initial lock, then metadata unblinding.

Consumes a fixed first raw-audit result; never imports/runs an auditor, submitted
code, backend, model or reference. Public packets exclude private checks and
arm/provider/cost/timing fields. This is metadata blinding, not anonymity of prose.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat

ACTUAL_EXTRACTION_AUTHORIZATION='primary-nine-family-manual-after-first-raw-pass-once-v1'
ANALYSIS_SHA256='50b5d41812424c1c0cb2bb950473546bd15cf0fc12ca9dace0f410da0767caec'
REGISTRATION_SCHEMA='nine-family-manual-extraction-registration-v2'
RAW_AUDIT_SCHEMA='primary-first-raw-audit-v1'
RULE=('Assess public task semantics, relevant current code/docs and original bounded observations. '
      'Use every applicable frozen requirement. Wording and line count are not quality scores. '
      'SUPPORTED implementation requires current code or observed behavior; a task contract alone is not implementation proof. '
      'UNSUPPORTED is an observed noncritical defect; '
      'UNKNOWN means evidence is missing; VETO is a definite serious safety/scope/contract/factual violation. '
      'Do not compensate serious errors with other successes or infer untested behavior from passed checks. '
      'Controlled-cut sources are unfinished and never completion-graded, but factual/safety violations remain reviewable. '
      'Cite exact JSON pointers and explain each decision. No condition/provider/cost/counterpart access before all initials lock.')

def require(value,code):
    if not value:raise ValueError(code)
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def finite(value):return type(value)in(int,float)and math.isfinite(value)
def loads(raw):
    def pairs(items):
        value={}
        for name,item in items:
            require(name not in value,'duplicate-json-key');value[name]=item
        return value
    def floating(value):
        value=float(value);require(math.isfinite(value),'nonfinite-json');return value
    return json.loads(raw,object_pairs_hook=pairs,parse_float=floating,
        parse_constant=lambda value:(_ for _ in()).throw(ValueError('nonfinite-json')))
def raw(path,maximum=16_777_216):
    path=Path(path).absolute()
    for parent in(path,*path.parents):
        info=parent.lstat();require(not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'linked-input')
    before=path.lstat()
    require(stat.S_ISREG(before.st_mode)and before.st_nlink==1 and before.st_size<=maximum,'ordinary-bounded-input')
    value=path.read_bytes();after=path.lstat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_nlink)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_nlink)and len(value)==before.st_size,'input-changed')
    return value
def read(path,expected=None):
    value=raw(path)
    if expected is not None:require(sha(value)==expected,'fixed-input-sha-differs')
    return loads(value)
def within(root,name):
    require(type(name)is str and name and ':'not in name and'\\'not in name
        and all(p not in('','.','..')for p in name.split('/')),'relative-reference-required')
    path=Path(root).joinpath(*name.split('/'))
    require(Path(root).absolute()in path.absolute().parents,'reference-outside-root')
    return path
def immutable(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);data=canonical(value)+b'\n'
    with path.open('xb')as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    require(raw(path)==data,'immutable-readback');return sha(data)
def tree_map(root):
    root=Path(root).absolute();info=root.lstat()
    require(stat.S_ISDIR(info.st_mode)and not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'ordinary-root')
    result={}
    for directory,dirs,names in os.walk(root,followlinks=False):
        for name in dirs:
            info=(Path(directory)/name).lstat()
            require(stat.S_ISDIR(info.st_mode)and not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'linked-tree')
        for name in names:
            path=Path(directory)/name;result[path.relative_to(root).as_posix()]=sha(raw(path))
    return dict(sorted(result.items()))

def stage_files(task,events,snapshot):
    """Byte replay only after the first auditor has qualified this exact prefix."""
    if snapshot is None:return None
    files=copy.deepcopy(task['initial_files'])
    for event in events:
        if event['tool']=='repo_patch'and event['result'].get('ok')is True:
            seen=set()
            for op in event['arguments']['operations']:
                name=op['path'];old=files.get(name)
                require(name in task['writable_files']and name not in seen
                    and op['old_sha256']==(sha(old.encode())if old is not None else None),'stage-scope-precondition')
                seen.add(name)
                if op['new_text']is None:
                    require(old is not None,'stage-delete-existing');files.pop(name)
                else:require(type(op['new_text'])is str,'stage-text-type');files[name]=op['new_text']
        require(event['state_sha256']==sha(canonical({p:sha(t.encode())for p,t in files.items()})),'stage-prefix-state')
    require({p:sha(t.encode())for p,t in files.items()}==snapshot,'stage-final-bytes')
    return files

def make_packet(task,files,events,report,rubric,*,opaque_id,controlled_source,evidence_gaps):
    require(report is None or type(report)is dict and set(report)=={'summary','validation','helper_gap'},'public-typed-report-only')
    observations=[]
    allowed={'repo_read':('ok','files','error'),'repo_search':('ok','matches','truncated','error'),
        'repo_patch':('ok','changed','files','write_state','error'),'repo_status':('ok','argv_profile','exit_code','stdout')}
    for event in events:
        tool=event['tool'];value=event['result']
        if tool=='repo_validate':
            # No trusted test source, private expectations, telemetry or paths.
            result={n:value[n]for n in('ok','suite','checks_total','checks_passed')if n in value}
            execution=value.get('execution',{})
            result['execution']={n:execution[n]for n in('status','unknown','container_removed','scratch_removed')if n in execution}
        else:
            require(tool in allowed,'unknown-public-observation')
            result={n:value[n]for n in allowed[tool]if n in value}
        observations.append({'tool':tool,'arguments':event['arguments'],'result':result})
    require(type(rubric)is dict and rubric['public_contract_sha256']==sha(task['initial_files']['CONTRACT.md'].encode()),'public-contract-rubric-binding')
    requirements=[copy.deepcopy(c)for c in rubric['requirements']if not controlled_source or c['scope']in('all','controlled-source')]
    return {'schema':'nine-family-blind-packet-v1','packet_id':opaque_id,'review_rule':RULE,
        'assessment_scope':'UNFINISHED_NOT_GRADED'if controlled_source else'COMPLETION_REQUIRED',
        'completion_grade':'UNASSESSED_FOR_REGISTERED_CUT'if controlled_source else'REQUIRES_COMPLETION',
        'task_prompt':task['prompt'],'initial_files':copy.deepcopy(task['initial_files']),
        'public_contract':task['initial_files']['CONTRACT.md'],'writable_files':list(task['writable_files']),
        'required_read_paths':list(task.get('required_read_paths',[])),'final_files':copy.deepcopy(files),
        'broker_observations':observations,'final_report':copy.deepcopy(report),
        'evidence_gaps':list(evidence_gaps),'requirements':requirements,
        'limits':'Public bounded facts only; no private check source/reference, cost inference, style score or universal guarantee.'}


def qualify_first_audit(reg,protocol,audit,owner_exit):
    """Consume only the externally confirmed first publication, never rerun it."""
    original_audit=read(reg['first_raw_audit']['path'],reg['first_raw_audit']['sha256'])
    require(canonical(audit)==canonical(original_audit),'passed-audit-must-equal-original-pinned-report')
    exit_record=read(reg['first_audit_exit']['path'],reg['first_audit_exit']['sha256'])
    seal_path=Path(reg['first_audit_seal']['path']).absolute()
    seal=read(seal_path,reg['first_audit_seal']['sha256'])
    report_path=Path(reg['first_raw_audit']['path']).absolute()
    require(seal_path.parent==report_path.parent and seal_path!=report_path,'same-first-audit-publication')
    failure_tail=seal_path.parent/'failure-tail.json'
    require(Path(reg['failure_tail_path']).absolute()==failure_tail and not os.path.lexists(failure_tail),
        'first-audit-failure-tail-forbids-extraction')
    require(audit.get('status')=='RAW_PASS'and audit.get('first_error')is None,'first-audit-success-required')
    require(exit_record.get('schema')=='primary-first-audit-exit-v1'
        and exit_record.get('process_exited')is True and exit_record.get('worker_alive')is False
        and exit_record.get('confirmed')is True and type(exit_record.get('exit_code'))is int
        and exit_record['exit_code']==0,'independent-first-audit-process-exit-required')
    require(exit_record.get('first_raw_audit_sha256')==reg['first_raw_audit']['sha256']
        and exit_record.get('seal_sha256')==reg['first_audit_seal']['sha256']
        and exit_record.get('first_auditor_source_sha256')==protocol['first_auditor_source_sha256'],
        'external-first-audit-publication-binding')
    require(finite(exit_record.get('observed_exit_monotonic'))
        and finite(audit.get('started_monotonic'))
        and exit_record['observed_exit_monotonic']>=audit['started_monotonic']>=owner_exit['observed_exit_monotonic'],
        'first-audit-observed-exit-order')
    require(seal.get('schema')=='primary-first-raw-audit-seal-v1'
        and seal.get('first_raw_audit_sha256')==reg['first_raw_audit']['sha256'],
        'original-first-audit-success-seal')
    expected=protocol['first_audit_required_artifacts'];artifacts=seal.get('required_artifacts')
    require(type(expected)is list and len(expected)>=8 and all(type(n)is str for n in expected)
        and len(expected)==len(set(expected))and type(artifacts)is dict
        and set(artifacts)==set(expected)and report_path.name in artifacts
        and seal_path.name not in artifacts and 'failure-tail.json'not in artifacts,
        'complete-first-audit-required-artifacts')
    for name,digest in artifacts.items():
        require(type(digest)is str and len(digest)==64 and all(c in'0123456789abcdef'for c in digest),
            'first-audit-artifact-sha256')
        read(within(seal_path.parent,name),digest)
    require(artifacts[report_path.name]==reg['first_raw_audit']['sha256'],'first-audit-original-report-artifact')

def extract(registration_path,expected_registration_sha256,*,authorization=None):
    # This equality is fixed in a new prospective source identity, never enabled
    # by a caller option, elapsed time, helper test or a previous calibration.
    require(ACTUAL_EXTRACTION_AUTHORIZATION!='UNBOUND'and authorization==ACTUAL_EXTRACTION_AUTHORIZATION
        and type(expected_registration_sha256)is str and len(expected_registration_sha256)==64
        and all(c in'0123456789abcdef'for c in expected_registration_sha256),'actual-extraction-unbound')
    reg=read(registration_path,expected_registration_sha256)
    require(reg['schema']==REGISTRATION_SCHEMA,'registration-schema')
    pinned={}
    for name in('protocol','terminal','owner_exit','first_raw_audit','first_audit_exit','first_audit_seal','rubric','supplement'):
        item=reg[name];pinned[name]=read(item['path'],item['sha256'])
    protocol=pinned['protocol'];terminal=pinned['terminal'];exit=pinned['owner_exit'];audit=pinned['first_raw_audit']
    supplement=pinned['supplement']
    require(protocol['analysis_registration_sha256']==supplement['parent_analysis_sha256']==ANALYSIS_SHA256
        and protocol['manual_binding']['rubric_sha256']==reg['rubric']['sha256']
        and protocol['manual_binding']['supplement_sha256']==reg['supplement']['sha256']
        and protocol['manual_binding']['helper_sha256']==sha(raw(Path(__file__)))
        and protocol['manual_binding']['authorization']==authorization,'prospective-manual-protocol-binding')
    root=Path(reg['run_root']).absolute();control=Path(reg['manual_root']).absolute()
    require(not control.exists()and root not in control.parents and control not in root.parents,'new-external-manual-root-required')
    require(exit['schema']=='primary-owner-exit-v1'and exit['run_root']==str(root)
        and exit['process_exited']is True and exit['worker_alive']is False and type(exit['exit_code'])is int
        and finite(exit['observed_exit_monotonic']),'original-owner-process-exit-required')
    require(audit['schema']==RAW_AUDIT_SCHEMA and audit['first_audit']is True and audit['raw_integrity']is True
        and audit['accounting_complete']is True and audit['terminal_sha256']==reg['terminal']['sha256']
        and audit['protocol_sha256']==reg['protocol']['sha256']and audit['owner_exit_sha256']==reg['owner_exit']['sha256']
        and finite(audit['started_monotonic'])and audit['started_monotonic']>=exit['observed_exit_monotonic'],'first-raw-audit-after-exit-required')
    qualify_first_audit(reg,protocol,audit,exit)
    require(reg['terminal']['sha256']==sha(raw(root/'terminal.json')),'exact-original-terminal')
    before=tree_map(root);require(sha(canonical(before))==audit['input_raw_map_sha256'],'raw-audit-original-input-map')
    registry=protocol['actor_registry'];bindings=reg['stage_bindings']
    require(set(bindings)==set(registry)==set(audit['actor_proofs'])and len(registry)==66,'complete-66-stage-roster')
    require(len({b['workflow_id']for b in registry.values()})==54 and len({b['block_id']for b in registry.values()})==18,'primary-denominator')
    rubric=pinned['rubric'];packets={};private=[]
    control.mkdir(exist_ok=False)
    immutable(control/'extract-once.claim.json',{'registration_sha256':expected_registration_sha256,'replay_authorized':False})
    for actor in secrets.SystemRandom().sample(list(registry),len(registry)):
        budget=registry[actor];binding=bindings[actor];proof=audit['actor_proofs'][actor]
        family=binding['family'];require(family in rubric['families'],'registered-family-rubric')
        controlled=budget['role']=='source'and budget['cut_policy']is not None
        verified_cut=controlled and proof['status']=='RAW_PASS'and proof.get('phase_cut_verified')is True
        gaps=[];events=[];report=None;files=None;mechanical=None
        if proof['status']=='UNINVOKED':
            task=binding['uninvoked_public_task'];gaps=['uninvoked-stage-no-current-result']
        else:
            require(proof['status']=='RAW_PASS'and proof['raw_integrity']is True and proof['accounting_complete']is True,'stage-first-audit-qualified')
            record=read(within(root,proof['actor_record_ref']),proof['actor_record_sha256'])
            require(record['actor_id']==actor,'raw-audited-stage-record')
            task=read(within(root,record['task_ref']),record['task_sha256'])
            result=read(within(root,record['result_ref']),record['result_sha256'])
            events=result['tool_events'];files=stage_files(task,events,result['final_state_snapshot'])
            if files is None:gaps.append('verified-current-files-missing')
            require(result['final_state_sha256']==proof['verified_final_state_sha256'],'first-audit-stage-current-state')
            report=result['final_report']['report']if result.get('final_report')is not None else None
            mechanical=proof['independent_task_pass']
            require(type(mechanical)is bool,'independent-mechanical-result-type')
            if verified_cut:require(proof['phase_cut_verified']is True and result['quality']['source_completed']is False
                and result['quality']['source_graded']is False and result['quality']['task_success']is None,'controlled-source-not-complete')
            if controlled:mechanical=None  # Observed prefix is audited, completion is deliberately ungraded.
        if controlled and not verified_cut:gaps.append('registered-controlled-phase-not-observed')
        opaque='p'+secrets.token_hex(16)
        require(opaque not in packets,'opaque-id-collision')
        packets[opaque]=make_packet(task,files,events,report,rubric['families'][family],opaque_id=opaque,
            controlled_source=controlled,evidence_gaps=gaps)
        private.append({'packet_id':opaque,'actor_id':actor,'workflow_id':budget['workflow_id'],'block_id':budget['block_id'],
            'case_id':budget['case_id'],'family':family,'arm':budget['arm'],'provider':budget['provider'],
            'role':budget['role'],'controlled_source':controlled,'mechanical_pass':mechanical})
    require(tree_map(root)==before,'actual-input-changed-during-extract')
    public={'schema':'nine-family-blind-packets-v1','review_rule':RULE,'packets':packets}
    packet_sha=immutable(control/'reviewer-public'/'packets.json',public)
    private_sha=immutable(control/'owner-private'/'condition-map.json',{'schema':'nine-family-private-map-v1','stages':private,
        'registration_path':str(Path(registration_path).absolute()),'registration_sha256':expected_registration_sha256,
        'packets_sha256':packet_sha,'rubric_sha256':reg['rubric']['sha256'],'input_raw_map_sha256':audit['input_raw_map_sha256']})
    extract_sha=immutable(control/'extract.complete.json',{'schema':'nine-family-extract-complete-v1',
        'registration_path':str(Path(registration_path).absolute()),'registration_sha256':expected_registration_sha256,
        'packets_sha256':packet_sha,'private_map_sha256':private_sha})
    return {'packet_count':len(packets),'packets_sha256':packet_sha,'private_map_sha256':private_sha,
        'extract_seal_sha256':extract_sha,'status':'EXTRACTED_ONCE_NO_UNBLIND'}

def pointer(packet,reference):
    require(type(reference)is str and reference.startswith('/'),'packet-json-pointer-required')
    value=packet
    for part in reference[1:].split('/'):
        require('~'not in part.replace('~0','').replace('~1',''),'invalid-json-pointer-escape')
        key=part.replace('~1','/').replace('~0','~')
        if type(value)is list:require(key.isdigit()and str(int(key))==key and int(key)<len(value),'packet-array-pointer');value=value[int(key)]
        else:require(type(value)is dict and key in value,'packet-pointer-missing');value=value[key]
    return value

def validate_decision(packet,decision):
    require(set(decision)=={'packet_id','reviewer','requirements','overall'}and decision['packet_id']==packet['packet_id']
        and type(decision['reviewer'])is str and decision['reviewer'].strip(),'initial-decision-shape')
    expected={r['id']for r in packet['requirements']};rows=decision['requirements']
    require(type(rows)is dict and set(rows)==expected,'all-applicable-requirements-required')
    statuses=[]
    for value in rows.values():
        require(set(value)=={'status','reason','evidence'}and value['status']in('SUPPORTED','UNSUPPORTED','UNKNOWN','VETO')
            and type(value['reason'])is str and value['reason'].strip()and len(value['reason'])<=2000
            and type(value['evidence'])is list and value['evidence'],'bounded-cited-initial-required')
        for ref in value['evidence']:pointer(packet,ref)
        statuses.append(value['status'])
    overall=('VETO'if'VETO'in statuses else'UNKNOWN'if packet['evidence_gaps']or'UNKNOWN'in statuses else
        'FAIL'if'UNSUPPORTED'in statuses else'UNFINISHED'if packet['assessment_scope']=='UNFINISHED_NOT_GRADED'else'PASS')
    require(decision['overall']==overall,'initial-overall-cannot-compensate-or-promote-unknown')
    return overall

def extraction_seal(root,expected_extract_sha256):
    seal=read(root/'extract.complete.json',expected_extract_sha256)
    require(seal['schema']=='nine-family-extract-complete-v1'
        and sha(raw(root/'reviewer-public/packets.json'))==seal['packets_sha256']
        and sha(raw(root/'owner-private/condition-map.json'))==seal['private_map_sha256'],'original-extraction-seal')
    return seal

def lock_initials(manual_root,decisions,*,expected_extract_sha256):
    root=Path(manual_root);public=read(root/'reviewer-public/packets.json');private=read(root/'owner-private/condition-map.json')
    extraction_seal(root,expected_extract_sha256)
    require(sha(raw(root/'reviewer-public/packets.json'))==private['packets_sha256'],'original-public-packets')
    packets=public['packets'];require(type(decisions)is dict and set(decisions)==set(packets),'lock-all-initials-before-unblind')
    for opaque,packet in packets.items():validate_decision(packet,decisions[opaque])
    return immutable(root/'initial-decisions.lock.json',{'schema':'nine-family-complete-initial-lock-v1',
        'packets_sha256':private['packets_sha256'],'private_map_sha256':sha(raw(root/'owner-private/condition-map.json')),
        'decisions':decisions,'cost_or_condition_unblinded':False})

def unblind(manual_root,*,expected_extract_sha256,expected_initial_lock_sha256):
    root=Path(manual_root)
    extraction_seal(root,expected_extract_sha256)
    lock=read(root/'initial-decisions.lock.json',expected_initial_lock_sha256);private=read(root/'owner-private/condition-map.json')
    public=read(root/'reviewer-public/packets.json');packets=public['packets']
    require(lock['schema']=='nine-family-complete-initial-lock-v1'and lock['cost_or_condition_unblinded']is False
        and lock['private_map_sha256']==sha(raw(root/'owner-private/condition-map.json'))
        and lock['packets_sha256']==private['packets_sha256']==sha(raw(root/'reviewer-public/packets.json')),'fixed-complete-lock-required')
    require(set(lock['decisions'])==set(packets)=={r['packet_id']for r in private['stages']},'unblind-complete-roster')
    joined=[]
    for row in private['stages']:
        opaque=row['packet_id'];overall=validate_decision(packets[opaque],lock['decisions'][opaque])
        require(overall!='PASS'or not row['controlled_source'],'controlled-source-cannot-pass')
        joined.append(dict(row,manual_overall=overall,
            completion_grade='UNASSESSED_FOR_REGISTERED_CUT'if row['controlled_source']else'REQUIRES_COMPLETION',
            completion_pass=(not row['controlled_source']and row['mechanical_pass']is True and overall=='PASS')))
    # No regrade or cost calculation: the existing primary aggregator consumes
    # this locked join with its already fixed quality/18-block/two-cost gates.
    return immutable(root/'condition-unblind.once.json',{'schema':'nine-family-locked-condition-join-v1',
        'initial_lock_sha256':sha(raw(root/'initial-decisions.lock.json')),'stages':joined,
        'quality_cost_standard_changed':False,'new_review_or_regrade_authorized':False})
