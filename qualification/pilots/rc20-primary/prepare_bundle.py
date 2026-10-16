"""Source-bound primary generator; explicit planner preparation is separate.

Default preparation emits STUB plans and cannot pass actual admission. A later
root-authorized --authorize-trusted-planner-once runs only the two fixed frozen
governance planners, never the fixture/backend, model, Git or Docker.
"""
import argparse
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import HERE,IDENTITY,STUDY_KIND,ANALYSIS_SHA,COUNTS,canonical,sha,strict_json,regular_bytes,immutable,require,TRUSTED_HOST_BINARIES,file_map

ORDER_SEED=2026101601
PANEL_SEED=2026101609
FACTORY_MANIFEST_SHA='8e94ba21b2200b08bab732adfcadd363eac5dffb16ba284ec02fb7ffac5ac6cc'
BASELINE_PROVENANCE_SHA='5e7a2926601995c82b25cc496cdb7677cb545a0cd413e8a3cdaeb16d87d72f98'
SOURCE_FILES=('common.py','prepare_bundle.py','manual_assignment.py','collector.py','owner.py','winjob.py',
    'launch.py','run_once.py','audit_once.py','credential_loader.py','first_auditor.py','README.md','owner-source-lineage.json',
    'manual-source-lineage.json','analysis-source-lineage.json','analyze_primary.py','frozen-workflow-order.json','frozen-panel-assignment.json')
CONTEXTS={
    'rational_expr':{'operation':'refactor','domains':['code','api','docs']},
    'unicode_columns':{'operation':'refactor','domains':['code','api','docs']},
    'mime_body':{'operation':'refactor','domains':['code','api','docs']},
    'ini_inheritance':{'operation':'refactor','domains':['code','config','docs']},
    'component_patterns':{'operation':'refactor','domains':['code','api','docs']},
    'pcm_transform':{'operation':'refactor','domains':['code','data','docs']},
    'csv_formula_safety':{'operation':'security','domains':['code','data','security','docs']},
    'svg_viewport':{'operation':'refactor','domains':['code','data','docs']},
    'sqlite_upgrade':{'operation':'migration','domains':['code','schema','data','docs']}}


def load_source(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def build_specs(fixed_contracts):
    rows=fixed_contracts['families']
    require(len(rows)==9 and {row['case_id']for row in rows}==set(CONTEXTS),'fixed nine public source families')
    specs=[]
    for row in rows:
        require((row['work_seconds_per_actor'],row['maximum_requests_per_actor'],row['maximum_tools_per_actor'],
            row['dispatch_minimum_remaining_seconds'])==(180,12,32,15),'factory actor limits differ')
        receiver=row['receiver_contract'];cut=receiver['policy_intent']['policy_id']if receiver else None
        context=copy.deepcopy(CONTEXTS[row['case_id']])
        descriptor=None
        if cut:
            require(row['stage_count']==2,'controlled family stage count')
            descriptor={'task_id':row['source_task']['id']+'-receiver',
                'context':dict(copy.deepcopy(context),unfinished=True)}
        else:require(row['stage_count']==1,'single family stage count')
        specs.append({'case_id':row['case_id'],'cut_policy':cut,'source_task':copy.deepcopy(row['source_task']),
            'source_context':context,'receiver':descriptor})
    return {'schema_version':'primary-nine-fixed-source-specs-v1','workflows':specs}


def run_planner(package,context,workspace,host,*,runner=subprocess.run,clock=time.perf_counter):
    """A source-bound trusted generator only. Stubbed by this source's pure tests."""
    script=package/'scripts/plan_governance.py';context_path=workspace/'context.json'
    require(not context_path.exists(),'one planner context per empty preparation directory')
    immutable(context_path,context)
    argv=[host['python']['path'],'-B',str(script),'--context',str(context_path),'--json']
    start=clock();result=runner(argv,cwd=workspace,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    elapsed=clock()-start
    require(result.returncode==0 and result.stderr==b''and type(result.stdout)is bytes,'trusted planner did not return exact successful bytes')
    # Parse only for structural validity; preserve stdout byte-for-byte as its plan.
    require(type(strict_json(result.stdout))is dict,'planner JSON object')
    return result.stdout.decode('utf-8'),{'argv':argv,'cwd':str(workspace),'script_sha256':sha(regular_bytes(script)),
        'stdout_sha256':sha(result.stdout),'stderr_sha256':sha(result.stderr),'returncode':result.returncode,'wall_seconds':elapsed}


def build_contexts(specs,*,plan_generator,prompt_builder):
    """One baseline/full plan per role; attention differs only by its one sentence."""
    cases={}
    for spec in specs['workflows']:
        cases[spec['case_id']]={}
        for role in('source','receiver'):
            if role=='receiver'and not spec['cut_policy']:continue
            context=spec['source_context']if role=='source'else spec['receiver']['context'];entries={}
            for arm,package in(('rc19','baseline-runtime'),('full','full-runtime')):
                root=HERE/'shared/frozen'/package
                skill=regular_bytes(root/'SKILL.md').decode('utf-8')
                plan=plan_generator(root,context,spec['case_id'],role,arm)
                system=prompt_builder(skill,plan,'',terminal_report='native-tool',execution_backend='docker-cpython-project-v1')
                entries[arm]={'skill':skill,'plan_text':plan,'system_context':system,
                    'input_context_sha256':sha(canonical(context)),'skill_sha256':sha(skill.encode()),
                    'plan_sha256':sha(plan.encode()),'system_sha256':sha(system.encode()),
                    'planner_source_sha256':sha(regular_bytes(root/'scripts/plan_governance.py'))}
            entries['attention']=copy.deepcopy(entries['rc19'])
            entries['attention']['system_context']+='\n\nKeep the response concise and avoid unnecessary engineering.'
            entries['attention']['system_sha256']=sha(entries['attention']['system_context'].encode())
            cases[spec['case_id']][role]={arm:entries[arm]for arm in('rc19','attention','full')}
    return {'schema_version':'primary-frozen-arm-contexts-v1','cases':cases}


def actor_bindings(order,specs,contexts):
    families={row['case_id']:row for row in specs['workflows']};result={}
    for row in order['workflows']:
        spec=families[row['case_id']]
        for role in('source','receiver'):
            actor=row[role+'_actor_id']
            if actor is None:continue
            entry=contexts['cases'][row['case_id']][role][row['arm']]
            registered={key:entry[key]for key in('skill','plan_text','system_context','input_context_sha256')}
            context=spec['source_context']if role=='source'else spec['receiver']['context']
            result[actor]={'task_sha256':sha(canonical(spec['source_task'])+b'\n')if role=='source'else'DERIVE_VERIFIED_SOURCE_HANDOFF_V1',
                'context_sha256':sha(canonical(context)+b'\n'),'system_context_sha256':sha(entry['system_context'].encode()),
                'registered_entry_sha256':sha(canonical(registered)+b'\n')}
    require(len(result)==66,'exact finite actor bindings');return result


def source_map():
    files={name:sha(regular_bytes(HERE/name))for name in SOURCE_FILES}
    for directory in('shared','manual','frozen-fixture','frozen-inputs'):
        for path in(HERE/directory).rglob('*'):
            if path.is_file():files[path.relative_to(HERE).as_posix()]=sha(regular_bytes(path))
    files['analysis-registration.json']=sha(regular_bytes(HERE/'analysis-registration.json'))
    return dict(sorted(files.items()))


def validate_runtime_packages():
    expected={'baseline-runtime':('3.0.0-rc.19',8303,'6204675e555304a07a35af46038883ce285caec0a0fbe8b4ff8d98cde00d2ee4'),
        'full-runtime':('3.0.0-rc.20',6737,'b97a3b100d407a78f372f0c9f01b3fea8afc4d2f5901f47624e4aac3ec5a2f74')}
    identities={}
    for name,(version,size,skill_sha)in expected.items():
        root=HERE/'shared/frozen'/name;manifest=strict_json(regular_bytes(root/'integrity/manifest.json'))
        actual=file_map(root)
        require(len(manifest['files'])==17 and set(actual)==set(manifest['files'])|{'integrity/manifest.json'},'exact eighteen-file runtime namespace')
        require(all(actual[path]==digest for path,digest in manifest['files'].items()),'runtime integrity file differs')
        require(manifest['generated_for_version']==version and sha(regular_bytes(root/'SKILL.md'))==skill_sha
            and len(regular_bytes(root/'SKILL.md'))==size,'fixed runtime version/Skill bytes')
        identities[name]={'version':version,'skill_sha256':skill_sha,'files':actual,'file_count':18,
            'canonical_file_map_sha256':sha(canonical(actual))}
    provenance_raw=regular_bytes(HERE/'frozen-inputs/baseline-provenance.json')
    require(sha(provenance_raw)==BASELINE_PROVENANCE_SHA,'fixed root Git provenance bytes')
    provenance=strict_json(provenance_raw)
    require(provenance['schema']=='primary-rc19-git-baseline-provenance-v1'and provenance['status']=='EXACT_GIT_OBJECT_BYTES'
        and provenance['commit']=='bd4a4d5c1c6fb9fca829e410729879d1b01f05b9'
        and provenance['file_count']==len(provenance['files'])==18,'root Git commit and complete eighteen-file evidence')
    rows={row['path']:row for row in provenance['files']}
    require(len(rows)==18 and set(rows)==set(identities['baseline-runtime']['files']),'baseline Git namespace differs')
    for name,row in rows.items():
        raw=regular_bytes(HERE/'shared/frozen/baseline-runtime'/name)
        require(row['mode']=='100644'and sha(raw)==row['sha256']and len(raw)==row['bytes']
            and hashlib.sha1(b'blob '+str(len(raw)).encode('ascii')+b'\0'+raw).hexdigest()==row['git_blob'],
            'copied baseline bytes differ from root-observed Git blob')
    identities['baseline-runtime'].update(git_commit=provenance['commit'],git_blob_sha1={name:row['git_blob']for name,row in rows.items()},
        provenance_receipt_sha256=BASELINE_PROVENANCE_SHA)
    return identities


def prepare(bundle,*,authorize_planner=False):
    """Prepare a new bundle once. Never sets actual/qualification/extraction grants."""
    bundle=Path(bundle).resolve();require(not bundle.exists(),'no bundle overwrite/reprepare')
    before=source_map();require(before['analysis-registration.json']==ANALYSIS_SHA,'v8 source changed')
    require(before['frozen-fixture/candidate-manifest-v7.json']==FACTORY_MANIFEST_SHA,'frozen nine factory changed')
    factory_manifest=strict_json(regular_bytes(HERE/'frozen-fixture/candidate-manifest-v7.json'))
    require(before['frozen-fixture/workflow-source-contracts.json']==factory_manifest['workflow_source_contracts_sha256'],'public tasks/contract body not bound to frozen factory')
    runtime_identities=validate_runtime_packages()
    order_module=load_source('primary_preparation_order',HERE/'shared/order_primary.py')
    contract=load_source('primary_preparation_contract',HERE/'shared/managed_contract_primary.py')
    panels=load_source('primary_preparation_panels',HERE/'manual_assignment.py')
    specs=build_specs(strict_json(regular_bytes(HERE/'frozen-fixture/workflow-source-contracts.json')))
    order=order_module.make_order([{'case_id':row['case_id'],'cut_policy':row['cut_policy']}for row in specs['workflows']],ORDER_SEED)
    actors=order_module.actor_registry(order);assignment=panels.make_panels(order,PANEL_SEED)
    require(order==strict_json(regular_bytes(HERE/'frozen-workflow-order.json'))
        and assignment==strict_json(regular_bytes(HERE/'frozen-panel-assignment.json')),'pre-result order/panel artifacts differ')
    host=strict_json(regular_bytes(HERE/'frozen-inputs/host-identity.json'))
    require({role:{key:host[role][key]for key in('path','sha256')}for role in TRUSTED_HOST_BINARIES}==TRUSTED_HOST_BINARIES,'fixed host identity')
    configuration=strict_json(regular_bytes(HERE/'frozen-inputs/profile-configuration.json'))
    bundle.mkdir(parents=False,exist_ok=False);preparation=[]
    if authorize_planner:
        # This branch needs a separate root source-qualified preparation action.
        # It has no fixture import, credential callback or project/backend call.
        from common import trusted_binary_bytes
        trusted_binary_bytes('python',host['python']['path'],host['python']['sha256'])
        sys.path.insert(0,str(HERE/'shared/repository'))
        from evolution.tool_campaign import build_prompt
        def generate(package,context,case,role,arm):
            path=bundle/'planner-preparation'/case/role/arm;path.mkdir(parents=True,exist_ok=False)
            plan,receipt=run_planner(package,context,path,host);preparation.append(receipt);return plan
    else:
        def generate(*unused):return 'UNBOUND_TRUSTED_PLANNER_NOT_EXECUTED'
        def build_prompt(skill,plan,*unused,**kwargs):return 'UNBOUND_SOURCE_ONLY_PROMPT\n'+sha(skill.encode())+'\n'+plan
    contexts=build_contexts(specs,plan_generator=generate,prompt_builder=build_prompt)
    registry_identity={'source_sha256':before['shared/order_primary.py'],'actor_registry_sha256':sha(canonical(actors)),'expected_actor_count':66}
    caps=contract.derive_caps(actors,configuration,registry_identity=registry_identity,finalization_policy=contract.FINALIZATION_POLICY)
    require(caps['round_seconds_soft']==54840 and caps['request_slots']==792,'prospective complete envelope')
    assembly_sha=immutable(bundle/'assembly-source-map.json',{'source_map':before})
    shared_map={name[len('shared/'):]:digest for name,digest in before.items()if name.startswith('shared/')}
    shared_sha=immutable(bundle/'source-map.json',{'source_map':shared_map})
    dependencies={'runtime_root':str(HERE/'shared/repository'),'shared_reader_root':str(HERE/'shared'),
        'shared_ledger_root':str(HERE/'shared'),'source_pins':{},'binary_pins':TRUSTED_HOST_BINARIES}
    dep_sha=immutable(bundle/'dependencies.json',dependencies)
    order_sha=immutable(bundle/'workflow-order.json',order);specs_sha=immutable(bundle/'workflow-specs.json',specs)
    context_sha=immutable(bundle/'arm-contexts.json',contexts);assignment_sha=immutable(bundle/'manual-assignment.json',assignment)
    host_sha=immutable(bundle/'host-identity.json',host);immutable(bundle/'profile-configuration.json',configuration)
    # The analysis's historical pretty bytes are themselves its fixed identity.
    with(bundle/'analysis-registration.json').open('xb')as stream:stream.write(regular_bytes(HERE/'analysis-registration.json'))
    fixture={'schema':'nine-family-fixed-development-binding-v1','factory_manifest_sha256':FACTORY_MANIFEST_SHA,
        'contracts_sha256':before['frozen-fixture/workflow-source-contracts.json'],
        'qualification_receipt_sha256':'UNBOUND','qualification_scope':'old three P5 + six v7 fixed controls; exposed development, never independent holdout'}
    fixture_sha=immutable(bundle/'fixture-binding.json',fixture)
    from owner import OWNER_LIMITS
    manual_module=load_source('primary_preparation_manual',HERE/'manual/helper.py')
    analysis_module=load_source('primary_preparation_analysis',HERE/'analyze_primary.py')
    require(manual_module.ACTUAL_EXTRACTION_AUTHORIZATION!='UNBOUND'and analysis_module.ACTUAL_ANALYSIS_AUTHORIZATION!='UNBOUND','finite frozen post-audit grants required')
    p={'schema_version':'primary-managed-54-workflows-v1','identity':IDENTITY,'study_kind':STUDY_KIND,'counts':COUNTS,
        'arms':['rc19','attention','full'],'providers':['deepseek','mimo'],'actor_registry':actors,
        'actor_bindings':actor_bindings(order,specs,contexts),'ledger_registry_identity':registry_identity,
        'runtime_packages':runtime_identities,
        'baseline_runtime_commit':runtime_identities['baseline-runtime']['git_commit'],
        'baseline_runtime_provenance_receipt_sha256':BASELINE_PROVENANCE_SHA,
        'assembly_source_manifest_sha256':assembly_sha,'source_manifest_sha256':shared_sha,'dependencies_sha256':dep_sha,
        'reader_source_pins':shared_map,'order_sha256':order_sha,'workflow_specs_sha256':specs_sha,'contexts_sha256':context_sha,
        'fixture_binding_sha256':fixture_sha,'manual_assignment_sha256':assignment_sha,'manual_assignment_seed':PANEL_SEED,
        'analysis_registration_sha256':ANALYSIS_SHA,'host_identity_sha256':host_sha,'host':host,
        'analysis_consumer_source_sha256':before['analyze_primary.py'],
        'analysis_consumer_authorization':analysis_module.ACTUAL_ANALYSIS_AUTHORIZATION,
        'configuration_sha256':sha(canonical(configuration)),'api_source_sha256':before['shared/repository/evolution/provider_tools.py'],
        'ledger_source_sha256':before['shared/ledger_primary.py'],'raw_auditor_source_sha256':before['shared/raw_auditor_primary.py'],
        'native_auditor_source_sha256':before['shared/native_auditor_primary.py'],'project_auditor_source_sha256':before['shared/project_auditor_primary.py'],
        'phase_auditor_source_sha256':before['shared/phase_auditor_primary.py'],'first_auditor_source_sha256':before['first_auditor.py'],
        'first_audit_owner_source_sha256':before['audit_once.py'],'first_audit_cap_seconds':1200,
        'first_audit_required_artifacts':['entry.STARTED.json','source.before.json','raw.before.json','owner.before.json',
            'source.after.json','raw.after.json','owner.after.json','first-audit.json'],
        'round_caps':caps,'finalization_policy':contract.FINALIZATION_POLICY,'actor_caps':{'seconds':180,'requests':12,'tools':32,'minimum_dispatch_seconds':15},
        'settlement_policy':contract.POLICY,'settlement_max_seconds':600,'owner_policy':'windows-job-before-go-api-owner-v3','owner_limits':OWNER_LIMITS,
        'study_class':'DEVELOPMENT','fixture_backend_qualification':'UNBOUND','fixture_qualification_receipt_sha256':'UNBOUND',
        'api7_real_calibration':'UNBOUND','api7_calibration_receipt_sha256':'UNBOUND','owner_closure_sha256':'UNBOUND',
        'inclusive_publication_accounting':'BOUND_OWNER_OBSERVED_WORKFLOW_AND_SHARED_COST_V1',
        'cost_measurement_boundary':'owner-after-final-terminal-durable-readback-before-final-cost-observation-publication-v1',
        'shared_cost_allocation':'equal-registered-workflow-share-v1','run_root':'UNBOUND','owner_root':'UNBOUND','supervisor_root':'UNBOUND','first_audit_root':'UNBOUND',
        'first_audit_control_root':'UNBOUND','first_audit_exit_path':'UNBOUND',
        'manual_binding':{'helper_sha256':before['manual/helper.py'],'rubric_sha256':before['manual/rubric.json'],
            'supplement_sha256':before['manual/prospective-v8-manual-supplement.json'],'authorization':manual_module.ACTUAL_EXTRACTION_AUTHORIZATION,
            'panel_assignment_sha256':assignment_sha,'initial_lock_scope':'all 66 before cost/condition unblind',
            'reviewer_input':'only preassigned opaque eleven-packet panel; no combined66/private map/counterparts'},
        'trusted_planner_preparation':'EXECUTED_FIXED_TWO_PACKAGES'if authorize_planner else'UNBOUND_STUB_ONLY',
        'actual_readiness':'UNBOUND','independent_source_closure_sha256':'UNBOUND','actual_authorization':'UNBOUND',
        'outer_first_setup_scope':'run_once starts before admission; owner/collector nested clocks do not extend this stricter 54840s cap',
        'final_measurement_publication_cost':'outside own last operational sample; unknown, never zero',
        'research_manual_cost':'separate observed preparation receipts; other unknown costs prevent all-in break-even claims'}
    protocol_sha=immutable(bundle/'protocol.json',p)
    command=commands(bundle,protocol_sha,host['python']['path'])
    command_sha=immutable(bundle/'commands.json',command)
    plan_sha=immutable(bundle/'execution-plan.json',{'identity':IDENTITY,'protocol_sha256':protocol_sha,
        'source_manifest_sha256':shared_sha,'assembly_source_manifest_sha256':assembly_sha,'command_sha256':command_sha,
        'runtime':{role:host[role]for role in('python','git','docker')},'outer_cap_seconds':54840,'actual_authorization':'UNBOUND'})
    require(source_map()==before,'source changed during preparation')
    immutable(bundle/'preparation.receipt.json',{'source_before_after_exact':True,'trusted_planner_executed':authorize_planner,
        'planner_preparation_observations':preparation,'protocol_sha256':protocol_sha,'execution_plan_sha256':plan_sha,
        'models_keys_projects_backends_readers_started':0,'actual_readiness':'UNBOUND'})
    return p,protocol_sha,plan_sha


def commands(bundle,protocol_sha,python):
    child=[python,'-I','-B','-u',str(HERE/'owner.py'),'--child','--bundle',str(bundle),
        '--protocol-sha256',protocol_sha,'--execution-plan-sha256','EXTERNAL_EXECUTION_PLAN_SHA256']
    return {'schema':'api-managed-exact-commands-v2','cwd':str(HERE),
        'launcher_main_argv':[str(HERE/'launch.py'),'--bundle',str(bundle),'--protocol-sha256',protocol_sha,'--root-launch-authorized'],
        'launcher_process_policy':'main call in same Job child; no second OS spawn','child_argv_prefix':child,
        'parent_argv_template':child[:5]+child[6:]+['--root-launch-authorized'],'job_name_argument':'--job-name owner-generated UUID'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',required=True)
    parser.add_argument('--authorize-trusted-planner-once',action='store_true');args=parser.parse_args()
    prepare(args.bundle,authorize_planner=args.authorize_trusted_planner_once)
