"""Fixed v8 DEVELOPMENT aggregation of already qualified and locked originals.

No provider/raw verifier, helper grade, clock, model, Git or project is invoked.
The actual entry is disabled until a new pre-call source identity binds its grant.
"""
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import stat

ANALYSIS_SHA='50b5d41812424c1c0cb2bb950473546bd15cf0fc12ca9dace0f410da0767caec'
ACTUAL_ANALYSIS_AUTHORIZATION='primary-v8-locked-development-analysis-once-v1'
ARMS=('rc19','attention','full')
COUNTS={'blocks':18,'workflows':54,'actors':66,'families':9,'single_families':7,'controlled_families':2}
MEASUREMENT='owner-after-final-terminal-durable-readback-before-final-cost-observation-publication-v1'
SHARED='equal-registered-workflow-share-v1'


def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(value,code):
    if not value:raise ValueError(code)
def decode(raw):
    def pairs(rows):
        result={}
        for name,value in rows:require(name not in result,'duplicate JSON key');result[name]=value
        return result
    return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite JSON')))
def finite(value):return type(value)in(int,float)and math.isfinite(value)and value>=0


def regular(path):
    path=Path(path).absolute()
    for target in(path,*path.parents):
        info=target.lstat();require(not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'linked analysis input')
    before=path.lstat();require(stat.S_ISREG(before.st_mode)and before.st_nlink==1,'single regular analysis input')
    raw=path.read_bytes();after=path.lstat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)and len(raw)==before.st_size,'analysis input changed during read')
    return raw


class Inputs:
    """One captured authoritative buffer per absolute path; hashes never reparse."""
    def __init__(self):self.buffers={}
    def read(self,path,digest):
        path=Path(path).absolute();name=str(path)
        if name not in self.buffers:self.buffers[name]=regular(path)
        raw=self.buffers[name];require(sha(raw)==digest,'analysis original input SHA differs')
        return decode(raw)
    def item(self,item):return self.read(item['path'],item['sha256'])
    def after(self):
        require(all(regular(path)==raw for path,raw in self.buffers.items()),'analysis original input changed after aggregation')


def load_inputs(registration,expected_sha256):
    """Only original identity/qualification joins; never rerun the raw verifier."""
    cache=Inputs();reg=cache.read(registration,expected_sha256)
    require(reg['schema']=='primary-v8-analysis-input-registration-v1','fixed analysis input schema')
    names=('analysis','protocol','order','terminal','owner_exit','first_raw_audit','first_audit_seal','first_audit_exit',
        'first_raw_map','first_owner_map','accounting','round_observation','manual_registration','extract','initial_lock','private_map','public_packets','condition_unblind')
    objects={name:cache.item(reg[name])for name in names}
    p=objects['protocol'];audit=objects['first_raw_audit'];seal=objects['first_audit_seal'];exit=objects['first_audit_exit']
    require(reg['analysis']['sha256']==p['analysis_registration_sha256']==ANALYSIS_SHA,'original v8 standard identity')
    require(p['analysis_consumer_source_sha256']==sha(regular(Path(__file__)))
        and p['analysis_consumer_authorization']==ACTUAL_ANALYSIS_AUTHORIZATION,'pre-call frozen analysis source/grant')
    require(p['order_sha256']==reg['order']['sha256'],'original complete order')
    rawroot=Path(p['run_root']).absolute();auditroot=Path(p['first_audit_root']).absolute();supervisor=Path(p['supervisor_root']).absolute()
    expected_paths={'first_raw_audit':auditroot/'first-audit.json','first_audit_seal':auditroot/'audit.seal.json',
        'first_raw_map':auditroot/'raw.before.json','first_owner_map':auditroot/'owner.before.json',
        'owner_exit':supervisor/'owner-exit.json','first_audit_exit':Path(p['first_audit_exit_path']).absolute(),
        'terminal':rawroot/'terminal.json','accounting':rawroot/'accounting.json','round_observation':supervisor/'round-observation.json'}
    require(all(Path(reg[name]['path']).absolute()==path for name,path in expected_paths.items()),'registered original input paths')
    require(not os.path.lexists(auditroot/'failure-tail.json'),'failed first-audit tail forbids analysis')
    require(audit['schema']=='primary-first-raw-audit-v1'and audit['status']=='RAW_PASS'and audit['first_error']is None
        and audit['first_audit']is True and audit['raw_integrity']is True and audit['accounting_complete']is True,'qualified first raw audit required')
    require(audit['protocol_sha256']==reg['protocol']['sha256']and audit['terminal_sha256']==reg['terminal']['sha256']
        and audit['owner_exit_sha256']==reg['owner_exit']['sha256'],'first raw audit original input bridge')
    require(exit['schema']=='primary-first-audit-exit-v1'and exit['process_exited']is True and exit['worker_alive']is False
        and type(exit['exit_code'])is int and exit['exit_code']==0 and exit['confirmed']is True
        and exit['first_raw_audit_sha256']==reg['first_raw_audit']['sha256']and exit['seal_sha256']==reg['first_audit_seal']['sha256']
        and exit['first_auditor_source_sha256']==p['first_auditor_source_sha256'],'confirmed successful first-auditor process exit')
    owner=objects['owner_exit']
    require(owner['schema']=='primary-owner-exit-v1'and owner['process_exited']is True and owner['worker_alive']is False
        and type(owner['exit_code'])is int and owner['exit_code']==0 and owner['confirmed']is True
        and finite(owner['observed_exit_monotonic'])and finite(audit['started_monotonic'])and finite(exit['observed_exit_monotonic'])
        and owner['observed_exit_monotonic']<=audit['started_monotonic']<=exit['observed_exit_monotonic'],'owner/audit original exit order')
    require(seal['schema']=='primary-first-raw-audit-seal-v1'and seal['status']=='RAW_PASS'and seal['first_error']is None
        and seal['first_raw_audit_sha256']==reg['first_raw_audit']['sha256'],'successful original first-audit seal')
    required=p['first_audit_required_artifacts'];require(len(required)==len(set(required))==8 and set(seal['required_artifacts'])==set(required),'fixed complete first-audit artifact set')
    for name,digest in seal['required_artifacts'].items():
        require(type(name)is str and name not in('','..','.')and '/'not in name and '\\'not in name and ':'not in name,'first-audit artifact path')
        cache.read(auditroot/name,digest)
    require(seal['required_artifacts']['first-audit.json']==reg['first_raw_audit']['sha256']
        and seal['required_artifacts']['raw.before.json']==reg['first_raw_map']['sha256']
        and seal['required_artifacts']['owner.before.json']==reg['first_owner_map']['sha256'],'same cached report/map artifact buffers')
    rawmap=objects['first_raw_map'];ownermap=objects['first_owner_map']
    require(rawmap['status']==ownermap['status']=='READABLE'and sha(canonical(rawmap['files']))==audit['input_raw_map_sha256'],'first-audited original raw map')
    for name,relative in(('accounting','accounting.json'),('terminal','terminal.json')):
        require(rawmap['files'][relative]==reg[name]['sha256'],'qualified raw input member')
    require(ownermap['files']['supervisor/round-observation.json']==reg['round_observation']['sha256']
        and ownermap['files']['supervisor/owner-exit.json']==reg['owner_exit']['sha256'],'qualified publication/owner original members')
    bind_manual(objects,reg)
    records={}
    for actor,proof in audit['actor_proofs'].items():
        if proof['status']=='RAW_PASS':
            relative='actor-records/'+actor+'.json'
            require(proof['actor_record_ref']==relative and rawmap['files'][relative]==proof['actor_record_sha256'],'qualified original actor record reference')
            records[actor]=cache.read(rawroot/relative,proof['actor_record_sha256'])
    objects['actor_records']=records
    return objects,cache



def bind_manual(objects,reg):
    """Identity-only join to the helper's original extraction and complete lock."""
    p=objects['protocol'];audit=objects['first_raw_audit'];manual=objects['manual_registration']
    require(manual['schema']=='nine-family-manual-extraction-registration-v2'
        and manual['protocol']['sha256']==reg['protocol']['sha256']
        and manual['first_raw_audit']['sha256']==reg['first_raw_audit']['sha256'],'same original extraction protocol/audit registration')
    extract=objects['extract'];lock=objects['initial_lock'];private=objects['private_map'];public=objects['public_packets'];join=objects['condition_unblind']
    require(extract['registration_sha256']==private['registration_sha256']==reg['manual_registration']['sha256']
        and Path(extract['registration_path']).absolute()==Path(private['registration_path']).absolute()==Path(reg['manual_registration']['path']).absolute(),
        'original extraction registration bridge')
    require(private['rubric_sha256']==manual['rubric']['sha256']==p['manual_binding']['rubric_sha256'],'same pre-call frozen nine-family rubric')
    require(extract['schema']=='nine-family-extract-complete-v1'and extract['packets_sha256']==reg['public_packets']['sha256']
        and extract['private_map_sha256']==reg['private_map']['sha256'],'original once extraction seal')
    require(lock['schema']=='nine-family-complete-initial-lock-v1'and lock['cost_or_condition_unblinded']is False
        and lock['packets_sha256']==reg['public_packets']['sha256']and lock['private_map_sha256']==reg['private_map']['sha256'],'complete original blind decision lock')
    require(join['schema']=='nine-family-locked-condition-join-v1'and join['initial_lock_sha256']==reg['initial_lock']['sha256']
        and join['quality_cost_standard_changed']is False and join['new_review_or_regrade_authorized']is False,'one locked condition join; no regrade')
    require(private['packets_sha256']==reg['public_packets']['sha256']and private['input_raw_map_sha256']==audit['input_raw_map_sha256'],
        'same original extracted packets/raw map')
    stage_rows={row['packet_id']:row for row in private['stages']}
    require(len(stage_rows)==66 and set(stage_rows)==set(public['packets'])==set(lock['decisions'])
        and len(join['stages'])==66,'all66 original blind packets and locked initial decisions')
    for row in join['stages']:
        require(row['packet_id']in stage_rows and all(row[key]==value for key,value in stage_rows[row['packet_id']].items()),'locked original condition mapping')
        require(row['manual_overall']==lock['decisions'][row['packet_id']]['overall'],'unblind cannot replace locked initial verdict')

def evaluate(objects):
    """Pure arithmetic and fixed decision joins over already qualified objects."""
    p=objects['protocol'];audit=objects['first_raw_audit'];ledger=objects['accounting'];terminal=objects['terminal'];round_=objects['round_observation']
    analysis=objects['analysis'];order=objects['order']['workflows'];registry=p['actor_registry'];records=objects['actor_records']
    joined=objects['condition_unblind']['stages'];lock=objects['initial_lock']['decisions']
    require(analysis['planned_blocks']==18 and analysis['planned_workflows']==54 and analysis['planned_actor_roles']==66,'v8 denominator')
    require(len(order)==54 and len(registry)==66 and len({row['block_id']for row in order})==18,'fixed primary topology')
    workflows={row['workflow_id']:row for row in order};require(len(workflows)==54,'unique workflow identities')
    blocks={};stages={};reasons=[];invalid_primary_workflows=set()
    def block(reason):
        if reason not in reasons:reasons.append(reason)
    for row in order:
        require(row['arm']in ARMS,'fixed three arms');bucket=blocks.setdefault(row['block_id'],{})
        require(row['arm']not in bucket,'one arm per paired block');bucket[row['arm']]=row['workflow_id']
    require(all(set(row)==set(ARMS)for row in blocks.values()),'all eighteen three-arm paired blocks')
    for block_rows in blocks.values():
        pair=[workflows[identifier]for identifier in block_rows.values()]
        require(len({(row['case_id'],row['source_provider'],row['receiver_provider'],row['cut_policy'])for row in pair})==1,'same family/provider/cut in paired block')
    require(len({row['case_id']for row in order})==9,'fixed nine families')
    expected_actors=[actor for row in order for actor in(row['source_actor_id'],row['receiver_actor_id'])if actor is not None]
    require(len(expected_actors)==len(set(expected_actors))==66 and set(expected_actors)==set(registry),'complete actor coverage; no prefix cost omitted')
    for row in joined:
        actor=row['actor_id'];require(actor in registry and actor not in stages,'one locked stage per registered actor')
        budget=registry[actor]
        require(all(row[key]==budget[key]for key in('workflow_id','block_id','case_id','arm','provider','role')),'locked stage same registered identity')
        decision=lock[row['packet_id']];require(decision['overall']==row['manual_overall'],'same original initial verdict')
        veto=row['manual_overall']=='VETO'or any(value['status']=='VETO'for value in decision['requirements'].values())
        unknown=row['manual_overall']=='UNKNOWN'or any(value['status']=='UNKNOWN'for value in decision['requirements'].values())
        controlled=budget['role']=='source'and budget['cut_policy']is not None
        require(row['controlled_source']is controlled and row['completion_grade']==('UNASSESSED_FOR_REGISTERED_CUT'if controlled else'REQUIRES_COMPLETION'),
            'controlled source completion remains ungraded')
        proof=audit['actor_proofs'].get(actor,{});record=records.get(actor);known=proof.get('status')=='RAW_PASS'and proof.get('raw_integrity')is True and proof.get('accounting_complete')is True and record is not None
        if not known:
            block('missing_or_unqualified_actor:'+actor);invalid_primary_workflows.add(budget['workflow_id'])
        if known and type(proof.get('independent_task_pass'))is not bool:block('missing_independent_mechanical_result:'+actor)
        if controlled and proof.get('phase_cut_verified')is not True:
            block('missing_registered_controlled_cut:'+actor);invalid_primary_workflows.add(budget['workflow_id'])
        if unknown:block('unknown_locked_stage:'+actor)
        if record is not None:
            require(record['actor_id']==actor,'original record actor identity');result=record['result']
            if any(result.get(name)is not False for name in('unknown_usage','execution_state_unknown','execution_infrastructure_failed','work_deadline_reached')):
                block('unknown_or_deadline_actor:'+actor);invalid_primary_workflows.add(budget['workflow_id'])
            if result.get('status')!=('controlled-phase-stop-unfinished'if controlled else'completed'):
                block('unintended_actor_stop:'+actor);invalid_primary_workflows.add(budget['workflow_id'])
        if controlled:
            require(row['mechanical_pass']is None and row['completion_pass']is False,'source cut never a completion PASS')
            passed=known and proof.get('phase_cut_verified')is True and not veto and not unknown
            completion=None
        else:
            require(row['mechanical_pass']is proof.get('independent_task_pass')if known else True,'locked same independent mechanical result')
            completion=known and proof.get('independent_task_pass')is True and row['manual_overall']=='PASS'and not veto and not unknown
            require(row['completion_pass']is bool(row['mechanical_pass']is True and row['manual_overall']=='PASS'),'helper completion projection')
            passed=completion
        stages[actor]={'completion_pass':completion,'prefix_or_completion_pass':bool(passed),'serious_veto':veto,
            'manual_overall':row['manual_overall'],'controlled_source_ungraded':controlled,
            'packet_id':row['packet_id'],'completion_grade':row['completion_grade']}
    if set(stages)!=set(registry):
        block('incomplete_locked_66_stages');invalid_primary_workflows.update(workflows)
    if audit.get('complete66')is not True or len(records)!=66:
        block('incomplete_original_66_actor_records');invalid_primary_workflows.update(workflows)
    if set(audit.get('verified_workflow_ids',[]))!=set(workflows):
        block('incomplete_original_54_workflows');invalid_primary_workflows.update(workflows)
    if any(terminal.get(name)is not value for name,value in(('unknown',False),('ledger_pending',False)))or terminal.get('unfinished_actor')is not None or terminal.get('first_error_class')is not None or terminal.get('ledger_persistence_fault')is not None:
        block('terminal_unknown_partial_or_error');invalid_primary_workflows.update(workflows)
    if terminal.get('status')!='completed'or terminal.get('completed_actor_records')!=66 or terminal.get('completed_workflow_records')!=54:
        block('terminal_incomplete_denominator');invalid_primary_workflows.update(workflows)
    proof_ledger=audit.get('ledger')or{}
    if proof_ledger.get('raw_integrity')is not True or proof_ledger.get('accounting_complete')is not True or ledger.get('pending')or proof_ledger.get('persistence_fault_observed')is not False:block('unknown_or_pending_ledger')
    by_actor={actor:0 for actor in registry};unknown_cost_actors=set();seen=set();known_tokens=0;slots=ledger['requests']
    for row in slots:
        identifier=row['request_id'];actor=row['actor_id'];require(identifier not in seen and actor in registry,'each original registered request once');seen.add(identifier)
        require(row['provider']==registry[actor]['provider'],'request same registered provider')
        receipt=row.get('receipt')or{};usage=receipt.get('usage')
        basic=type(usage)is dict and all(type(usage.get(key))is int and usage[key]>=0 for key in('input_tokens','output_tokens','total_tokens'))and usage['total_tokens']==usage['input_tokens']+usage['output_tokens']
        if basic:
            known_tokens+=usage['total_tokens'];by_actor[actor]+=usage['total_tokens']
            if row.get('known_usage_accounted')is not True:block('usage_not_accounted:'+identifier)
        elif row.get('status')!='confirmed-not-invoked-before-send'or usage is not None:
            block('missing_reported_usage:'+identifier);unknown_cost_actors.add(actor)
        if row.get('status')=='unknown-reservation-retained'or receipt.get('unknown')is not False:unknown_cost_actors.add(actor)
        if row.get('status')not in('reported-usage-estimate-committed','confirmed-not-invoked-before-send')or receipt.get('unknown')is not False or row.get('reported_usage_over_reservation')is True:
            block('unknown_or_overrun_request:'+identifier);invalid_primary_workflows.add(registry[actor]['workflow_id'])
    if ledger.get('known_reported_tokens')!=known_tokens or proof_ledger.get('known_reported_tokens')!=known_tokens:block('known_token_projection_mismatch')
    if ledger.get('request_slots')!=len(slots)or proof_ledger.get('request_slots')!=len(slots):block('request_prefix_count_mismatch')
    times=round_.get('attributed_inclusive_workflow_seconds',{})
    if (round_.get('measurement_boundary')!=MEASUREMENT or round_.get('shared_allocation')!=SHARED
        or round_.get('registered_workflow_denominator')!=54 or round_.get('round_overrun')is not False
        or round_.get('all_workflows_observed')is not True or set(times)!=set(workflows)
        or any(not finite(value)for value in times.values())):
        block('incomplete_unknown_or_overrun_inclusive_wall');invalid_primary_workflows.update(workflows)
    observations=terminal.get('workflow_finalization_observations',[])
    if len(observations)!=54 or {row.get('workflow_id')for row in observations}!=set(workflows):
        block('workflow_publication_missing_or_overrun');invalid_primary_workflows.update(workflows)
    for observation in observations:
        if observation.get('overrun')is not False:
            block('workflow_publication_missing_or_overrun');invalid_primary_workflows.add(observation['workflow_id'])
    if proof_ledger.get('accounting_complete')is not True or(ledger.get('pending')and not unknown_cost_actors):unknown_cost_actors=set(registry)
    invalid_primary_arms={workflows[identifier]['arm']for identifier in invalid_primary_workflows}
    unknown_token_arms={registry[actor]['arm']for actor in unknown_cost_actors}|invalid_primary_arms
    missing_wall_arms={row['arm']for identifier,row in workflows.items()if not finite(times.get(identifier))}|invalid_primary_arms
    totals={arm:{'workflow_passes':0,'reported_tokens':0,'inclusive_wall_seconds':Decimal(0)}for arm in ARMS};rows={}
    for identifier,workflow in workflows.items():
        source=workflow['source_actor_id'];receiver=workflow['receiver_actor_id'];expected=[source]+([receiver]if receiver else[])
        require(all(actor in registry and registry[actor]['workflow_id']==identifier for actor in expected),'fixed workflow actors')
        passed=all(stages.get(actor,{}).get('prefix_or_completion_pass')is True for actor in expected)
        tokens=sum(by_actor[actor]for actor in expected);wall=times.get(identifier)
        rows[identifier]={'block_id':workflow['block_id'],'case_id':workflow['case_id'],'arm':workflow['arm'],
            'source_provider':workflow['source_provider'],'receiver_provider':workflow['receiver_provider'],
            'workflow_pass':passed,'reported_tokens':None if identifier in invalid_primary_workflows or any(actor in unknown_cost_actors for actor in expected)else tokens,
            'reported_tokens_known_component':tokens,'inclusive_wall_seconds':str(Decimal(str(wall)))if finite(wall)and identifier not in invalid_primary_workflows else None,
            'inclusive_wall_known_component_seconds':str(Decimal(str(wall)))if finite(wall)else None,
            'primary_execution_denominator_valid':identifier not in invalid_primary_workflows,
            'stages':{actor:stages.get(actor,{'status':'MISSING'})for actor in expected}}
        total=totals[workflow['arm']];total['workflow_passes']+=int(passed);total['reported_tokens']+=tokens
        if finite(wall):total['inclusive_wall_seconds']+=Decimal(str(wall))
    full_veto=[actor for actor,value in stages.items()if registry[actor]['arm']=='full'and value['serious_veto']]
    if full_veto:block('serious_full_VETO')
    paired={}
    for identifier,condition in blocks.items():
        full=rows[condition['full']];paired[identifier]={'workflows':condition,'control_pass_full_regressions':[],
            'conditions':{arm:{key:rows[workflow][key]for key in('workflow_pass','reported_tokens','inclusive_wall_seconds')}
                for arm,workflow in condition.items()},'full_minus_control':{}}
        for control in('rc19','attention'):
            other=rows[condition[control]]
            paired[identifier]['full_minus_control'][control]={
                'reported_tokens':full['reported_tokens']-other['reported_tokens']if full['reported_tokens']is not None and other['reported_tokens']is not None else None,
                'inclusive_wall_seconds':str(Decimal(full['inclusive_wall_seconds'])-Decimal(other['inclusive_wall_seconds']))
                    if full['inclusive_wall_seconds']is not None and other['inclusive_wall_seconds']is not None else None}
            if other['workflow_pass']and not full['workflow_pass']:
                paired[identifier]['control_pass_full_regressions'].append(control);block('paired_regression:'+identifier+':'+control)
    for control in('rc19','attention'):
        if totals['full']['workflow_passes']<totals[control]['workflow_passes']:block('full_pass_count_below:'+control)
        if {'full',control}&unknown_token_arms:block('primary_reported_tokens_unknown:'+control)
        elif totals['full']['reported_tokens']>=totals[control]['reported_tokens']:block('tokens_not_strictly_lower:'+control)
        if {'full',control}&missing_wall_arms:block('primary_inclusive_wall_missing:'+control)
        elif totals['full']['inclusive_wall_seconds']>=totals[control]['inclusive_wall_seconds']:block('wall_not_strictly_lower:'+control)
    for arm,total in totals.items():
        total['reported_tokens_known_component']=total['reported_tokens']
        if arm in unknown_token_arms:total['reported_tokens']=None
        total['inclusive_wall_known_component_seconds']=str(total['inclusive_wall_seconds'])
        total['inclusive_wall_seconds']=None if arm in missing_wall_arms else str(total['inclusive_wall_seconds'])
    return {'schema':'primary-v8-locked-development-analysis-v1','favorable_development_net_result':not reasons,
        'failure_reasons':reasons,'fixed_denominator':COUNTS,'arms':totals,'blocks':paired,'workflows':rows,
        'serious_full_VETO_actors':full_veto,'all_invoked_known_reported_prefix_tokens':known_tokens,
        'fees':{'provider_currency_alternatives':ledger.get('accounts'),'scope':'already verified committed/reserved estimates; MiMo currencies are alternatives, never summed or an invoice'},
        'research_preparation_seconds':round_.get('research_preparation_seconds'),'independent_review_seconds':round_.get('independent_review_seconds'),
        'final_measurement_publication_seconds':round_.get('last_cost_observation_publication_seconds'),
        'all_in_research_break_even':'UNASSESSED','formal_qualification':'UNASSESSED','locked_independent_holdout':'NOT_RUN',
        'Stable':False,'promotion_authorized':False,'selection_claim':'preregistered-development-not-independent-efficacy',
        'wall_arithmetic':'Decimal(str(original attributed observation)); fixed shared allocation already included; no new clock or allocation',
        'standard_sha256':ANALYSIS_SHA,'new_grade_or_regrade':False}


def output_path(output,objects):
    path=Path(output).absolute();p=objects['protocol']
    protected=[Path(p[name]).absolute()for name in('run_root','owner_root','supervisor_root','first_audit_root','first_audit_control_root')]
    protected.extend((Path(objects['manual_registration']['manual_root']).absolute(),Path(__file__).absolute().parent))
    require(all(path!=root and root not in path.parents for root in protected),'analysis output must be outside frozen inputs and source')
    return path


def analyze(registration,expected_registration_sha256,output,*,authorization=None):
    require(ACTUAL_ANALYSIS_AUTHORIZATION!='UNBOUND'and authorization==ACTUAL_ANALYSIS_AUTHORIZATION,'actual analysis UNBOUND')
    objects,cache=load_inputs(registration,expected_registration_sha256)
    result=evaluate(objects);cache.after()
    path=output_path(output,objects);require(path.parent.is_dir()and not path.exists(),'once analysis publication')
    require(all(path!=Path(name)and Path(name)not in path.parents for name in cache.buffers),'analysis output cannot replace input')
    raw=canonical(dict(result,input_registration_sha256=expected_registration_sha256,input_path_sha256={name:sha(value)for name,value in cache.buffers.items()}))+b'\n'
    with path.open('xb')as stream:require(stream.write(raw)==len(raw),'short analysis output');stream.flush();os.fsync(stream.fileno())
    require(regular(path)==raw,'analysis output readback differs');cache.after()
    return sha(raw)
