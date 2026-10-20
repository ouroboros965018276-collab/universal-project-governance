"""Pinned v11 pure receipt ancestry with source8 canonical API contract overlays."""
import copy,importlib.util,re,sys
from pathlib import Path
from reader_binding_primary import HERE,strict_json as loads,NATIVE_INSTRUCTION
from managed_contract_primary import canonical,sha,ADAPTER,MODELS
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
P=load('primary_pure_fee_kernels',HERE/'frozen/fee_kernels.py')
K=load('primary_pure_parser_kernels',HERE/'frozen/parser_kernels.py')
require,EvidenceError=P.require,P.EvidenceError
digest=lambda value:sha(canonical(value))
TOOLS,FINAL_SCHEMA=K.TOOLS,K.FINAL_SCHEMA
P.MODELS=MODELS
BACKEND='docker-cpython-project-v1'
BROKER_PROFILE='stdlib-python-project-v1'
SUITE='registered-python-project-checks-v1'
IMAGE='docker.io/library/python@sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d'
PLATFORM='linux/amd64'
BOUND_FIELDS=('provider','model_requested','profile_id','thinking','reasoning_effort_requested','request_index','input_utf8_bytes','output_cap','request_payload_sha256','input_task_sha256','adapter','broker_profile_id','profile_configuration_sha256','execution_backend','connect_retry_policy','tool_feedback_policy','retry_of_request_id','settlement_policy','settlement_max_seconds','work_deadline_monotonic','settlement_deadline_monotonic')
def forbid_execution(*args,**kwargs):raise EvidenceError('project-execution-forbidden-in-audit')
def project_reader():
    # A separate module instance; never disable the producer's project executor.
    module=load('primary_receipt_reader_only',HERE/'repository/evolution/project_executor.py')
    module.execute_project=module.validate_with_project_execution=module._capture=forbid_execution
    return module
def exact_json(raw,value,code):require(raw==canonical(value)+b'\n',code)

EXECUTION_KEYS = {'backend', 'status', 'unknown', 'received_snapshot_sha256', 'contract_sha256', 'runner_sha256', 'input_sha256', 'image_reference', 'image_id', 'platform', 'output_sha256', 'check_count', 'container_removed', 'scratch_removed', 'receipt_ref', 'receipt_sha256', 'observed_wall_seconds'}

def state(files):return{name:sha(text.encode())for name,text in sorted(files.items())}

def task_scope(task,files):
    initial=task['initial_files'];writable=set(task['writable_files'])
    require(type(files)is dict and set(initial)-writable<=set(files)<=set(initial)|writable and len(files)<=64,'registered-project-namespace')
    require(all(type(t)is str and len(t.encode())<=65536 for t in files.values())and sum(len(t.encode())for t in files.values())<=1048576,'registered-project-byte-bounds')
    require(all(files.get(p)==t for p,t in initial.items()if p not in writable),'protected-current-bytes')

def project_execution(view,directory,summary,task,files,reader=None):
    require(type(summary)is dict and set(summary)==EXECUTION_KEYS,'project-exact-summary-fields')
    require(summary['backend']==BACKEND and summary['status']=='EXECUTED'and summary['unknown']is False,'project-known-executed-only')
    require(summary['received_snapshot_sha256']==digest(state(files))and summary['contract_sha256']==digest(task['engineering_contract']),'project-current-source-contract')
    require(summary['image_reference']==IMAGE and summary['platform']==PLATFORM and summary['container_removed']is summary['scratch_removed']is True,'project-isolation-cleanup')
    require(type(summary['check_count'])is int and summary['check_count']==len(task['engineering_contract']['checks'])and P.finite(summary['observed_wall_seconds']),'project-check-count-window')
    require(type(summary['receipt_ref'])is str and re.fullmatch(r'validation-[0-9]{3,}/result\.json',summary['receipt_ref'])and P.is_sha(summary['receipt_sha256']),'project-original-reference')
    rel=directory+'/'+summary['receipt_ref'];raw=view.raw(rel);receipt=loads(raw)
    require(sha(raw)==summary['receipt_sha256'],'project-original-raw-sha')
    require(receipt.get('status')=='EXECUTED'and receipt.get('unknown')is False and receipt.get('quality_assessed')is False,'project-no-prepared-or-self-report')
    for key in('backend','status','unknown','contract_sha256','runner_sha256','input_sha256','image_reference','image_id','platform','output_sha256','container_removed','scratch_removed'):
        require(receipt.get(key)==summary[key],'project-summary-vs-raw:'+key)
    require(receipt.get('snapshot_sha256')==digest(state(files))and not any(receipt.get(k)for k in('cleanup_unconfirmed','scratch_cleanup_unconfirmed','evidence_persistence_unconfirmed')),'project-no-unknown-cleanup')
    base=rel.rsplit('/',1)[0]
    rr=reader or project_reader()
    checked,saved,received=rr.read_project_receipt(files,task['engineering_contract'],view.path(base),receipt_sha256=summary['receipt_sha256'])
    require(saved==receipt and received==sha(raw)and checked.get('integrity_ok')is True,'pure-original-project-reader-integrity')
    require(type(checked.get('ok'))is bool and type(checked.get('checks_passed'))is int and checked.get('checks_total')==len(task['engineering_contract']['checks'])and checked['ok']==(not checked.get('failures')),'project-checked-result-shape')
    require(P.finite(receipt.get('wall_seconds'))and summary['observed_wall_seconds']+1e-6>=receipt['wall_seconds'],'project-window-includes-cleanup')
    # The reader checks every saved raw command/stream, fixed argv, image,
    # owner, isolation, test IDs, import origins, CLI streams/files and absence.
    # Cleanup byte maps/scratch are separate retained evidence.
    require(view.json(base+'/src.cleanup-byte-map.json')==state(files),'project-src-cleanup-map')
    require(view.json(base+'/trusted.cleanup-byte-map.json')==state(task['engineering_contract']['trusted_files']),'project-trusted-cleanup-map')
    require(view.json(base+'/runner.cleanup-byte-map.json')=={'runner.py':receipt['runner_sha256'],'checker.py':receipt['checker_sha256'],'input.json':receipt['input_sha256']},'project-runner-cleanup-map')
    require(all(not view.path(base+'/'+p).exists()for p in('src','trusted','runner')),'project-scratch-actually-absent')
    return checked

def validation_result(view,directory,result,task,files,reader=None):
    require(type(result)is dict and set(result)=={'ok','suite','failures','checks_total','checks_passed','execution','diagnostics'}and type(result['ok'])is bool and result['suite']==SUITE,'project-validation-closed-envelope')
    checked=project_execution(view,directory,result['execution'],task,files,reader)
    require(all(result[k]==checked[k]for k in('ok','failures','checks_total','checks_passed'))and canonical(result['diagnostics'])==canonical(checked['diagnostics']),'project-native-validation-vs-original-receipts')
    return checked

CANONICAL_BROKER_SHA256='85f9a1c1b004e410780f6e4096d69fde3fada6b6d6bc10a688e447411e34c0db'
CANONICAL_PROVIDER_SCHEMA_SOURCE_SHA256='e6bff4926c3c725d0937dc5e0f77e58517b861665fe052810e4a6d223caa3363'

def _replacement_contents(operation, previous):
    """One patch interpretation for the live broker and pure receipt reader."""
    if (type(operation) is not dict
            or set(operation) not in ({'path', 'old_sha256', 'new_text'},
                                      {'path', 'old_sha256', 'new_text', 'old_text'})):
        raise ValueError('patch requires path, old_sha256, new_text and optional old_text')
    text = operation['new_text']
    if 'old_text' not in operation:
        return text
    fragment = operation['old_text']
    if (type(previous) is not str or type(fragment) is not str or not fragment
            or type(text) is not str):
        raise ValueError('fragment replacement requires an existing file, nonempty old_text and string new_text')
    start = previous.find(fragment)
    if start < 0 or previous.find(fragment, start + 1) >= 0:
        raise ValueError('old_text must occur exactly once in the current file')
    return previous[:start] + text + previous[start + len(fragment):]

def _confirmed_deletion_readback(value, previous_sha256):
    return (type(value) is dict and set(value) == {'sha256', 'deleted', 'previous_sha256'}
            and value['sha256'] is None and value['deleted'] is True
            and type(value['previous_sha256']) is str and value['previous_sha256'] == previous_sha256)

def base_definitions():
    """Inverse field projection of the existing independent base API schemas.

    Canonical engineering.tool_definitions uses only name/description/inputSchema;
    native MCP annotations are outside the API wire projection and are not added.
    """
    return [{'name': row['function']['name'], 'description': row['function']['description'],
             'inputSchema': copy.deepcopy(row['function']['parameters'])}
            for row in K.tools_schema()]

def tool_definitions():
    definitions = copy.deepcopy(base_definitions())
    for item in definitions:
        if item['name'] == 'repo_read':
            item['description'] = ('Read registered paths in one batch. Existing files return text and SHA256. '
                                   'Currently absent writable paths return exists=false, text=null, sha256=null; '
                                   'this is an absence observation, not a read of file contents. '
                                   'initial_paths are existing files; writable_files may also name files allowed to be created. '
                                   'Unregistered paths and unexpected filesystem errors are rejected.')
            item['inputSchema']['properties']['paths']['description'] = (
                'Registered existing or writable paths only; writable paths need not exist yet.')
        if item['name'] == 'repo_patch':
            properties = item['inputSchema']['properties']['operations']['items']['properties']
            properties['new_text']['type'] = ['string', 'null']
            properties['new_text']['description'] = (
                'Complete replacement file contents when old_text is absent; with old_text, replacement fragment only '
                '(may be empty). Null deletes an existing writable file only without old_text.')
            properties['old_sha256']['description'] = (
                'Exact current SHA256 from a successful read/write receipt; null only for a currently absent writable file.')
            properties['old_text'] = {'type': 'string', 'minLength': 1,
                'description': 'Optional exact nonempty fragment occurring exactly once in the current existing file. '
                               'Requires its current SHA/read; only that fragment is replaced by string new_text. '
                               'Omit for whole-file replacement, creation or file deletion.'}
            item['description'] += (' Without old_text, new_text is the entire replacement file, never a fragment or diff; preserve required contents. '
                                    'Optional old_text selects a unique exact fragment in an existing file; the current read/SHA remains required '
                                    'and all bytes outside that occurrence are preserved. '
                                    'No-op replacements and stale SHA values are rejected. In this explicit project profile, '
                                    'new_text=null deletes an existing writable file with a verified prior read and SHA; it cannot remove directories.')
        if item['name'] == 'repo_validate':
            item['description'] = ('Execute the fixed registered stdlib Python project suite in an isolated container. '
                                   'Returns current snapshot-bound test/CLI/import observations, never arbitrary commands or universal correctness.')
    return definitions

def _schema(value, schema, depth=0):
    """Validate the bounded subset used by canonical broker/FINAL_SCHEMA."""
    if depth > 32:
        return False
    kind = schema.get("type")
    if isinstance(kind, list):
        return any(_schema(value, dict(schema, type=item), depth + 1) for item in kind)
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
             "integer": type(value) is int, "number": type(value) in (int, float), "boolean": type(value) is bool,
             "null": value is None}
    if kind and not valid.get(kind, False):
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])) <= set(value):
            return False
        if schema.get("additionalProperties") is False and not set(value) <= set(properties):
            return False
        return all(_schema(item, properties[name], depth + 1) for name, item in value.items() if name in properties)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10000):
            return False
        return all(_schema(item, schema.get("items", {}), depth + 1) for item in value)
    return True

def wire_tools():
    """Exact engineering branch of provider_tools' definitions-to-API projection."""
    definitions = {item['name']: item for item in tool_definitions()}
    definitions['repo_finish'] = {'name': 'repo_finish',
        'description': 'Submit the final typed report after all required repository work, current validation and status. Call alone once; this does not perform or waive any repository operation.',
        'inputSchema': copy.deepcopy(FINAL_SCHEMA)}
    return [{'type': 'function', 'function': {'name': name, 'description': item['description'],
             'parameters': item['inputSchema']}} for name, item in definitions.items()]

def schema_valid(tool,args):
    schema = next((row['function']['parameters'] for row in wire_tools()
                   if row['function']['name'] == tool), None)
    return schema is not None and _schema(args,schema)

def broker_arguments_valid(tool,args):
    if tool=='repo_patch':return schema_valid(tool,args)and 1<=len(args['operations'])<=64
    return K.arguments_valid(tool,args)

def required_initial_reads(events,task):
    seen=set()
    for event in events:
        if event['tool']=='repo_patch':break
        if event['tool']=='repo_read'and event['result'].get('ok')is True:
            for p in event['arguments']['paths']:
                if p in task['initial_files']and event['result'].get('files',{}).get(p)=={'text':task['initial_files'][p],'sha256':sha(task['initial_files'][p].encode())}:seen.add(p)
    return set(task.get('required_read_paths',[]))<=seen

def batch_shape(calls,seen,task):
    parsed=[];rejected=[];ids=set()
    for ordinal,call in enumerate(calls):
        require(type(call)is dict and set(call)in({'id','type','function'},{'id','type','function','index'})and('index'not in call or type(call['index'])is int and call['index']==ordinal)and call['type']=='function'and type(call['id'])is str and call['id'].strip()and call['id']not in seen|ids,'engineering-native-envelope')
        f=call['function'];require(type(f)is dict and set(f)=={'name','arguments'}and f['name']in(*TOOLS,'repo_finish')and type(f['arguments'])is str,'engineering-tool-argument-envelope')
        ids.add(call['id'])
        try:args=loads(f['arguments'])
        except(ValueError,TypeError,RecursionError):args=None
        if type(args)is dict and f['name']=='repo_read'and type(args.get('paths'))is list:
            require(all(type(p)is not str or p in set(task['initial_files'])|set(task['writable_files'])for p in args['paths']),'schema-correction-cannot-hide-read-scope')
        if type(args)is dict and f['name']=='repo_patch'and type(args.get('operations'))is list:
            require(all(type(op)is not dict or type(op.get('path'))is not str or op['path']in task['writable_files']for op in args['operations']),'schema-correction-cannot-hide-write-scope')
        if not schema_valid(f['name'],args):rejected.append(call['id'])
        parsed.append({'call_id':call['id'],'tool':f['name'],'arguments_utf8_sha256':sha(f['arguments'].encode())})
    return parsed,rejected

def schema_rejection(view,folder,index,receipt,response_raw,calls,seen,task,files,sequence):
    parsed,rejected=batch_shape(calls,seen,task)
    require(rejected,'schema-correction-needs-actual-schema-failure')
    rel=folder+'/schema-rejections/%02d.json'%index;raw=view.raw(rel);observed=loads(raw)
    metadata={k:receipt[k]for k in(*BOUND_FIELDS,'controlled_local_stop_policy','request_id','reservation_receipt_sha256')if k in receipt}
    expected=dict(metadata,status='NOT_EXECUTED_SCHEMA_REJECTED',batch_executed=False,state_sha256=digest(state(files)),calls=parsed,rejected_call_ids=rejected,response_artifact_sha256=sha(response_raw),request_receipt_sha256=sha(view.raw(folder+'/requests/%02d.receipt.json'%index)),schema_rejection_sequence=sequence,correction_permitted=sequence<=1)
    require(observed==expected,'durable-schema-rejection-exact-known-request')
    exact_json(raw,observed,'schema-rejection-canonical-original')
    require(sequence<=2 and observed['correction_permitted']is(sequence==1),'one-schema-correction-only')
    defs={t['function']['name']:t['function']['parameters']for t in wire_payload('deepseek',[])['tools']}
    messages=[]
    if sequence==1:
        for item in parsed:
            value={'ok':False,'status':'NOT_EXECUTED_SCHEMA_REJECTED','batch_executed':False,'rejected':item['call_id']in rejected,'correction_permitted':True,'use_new_call_ids':True,'remaining_schema_corrections':0,'inputSchema':defs[item['tool']]}
            messages.append({'role':'tool','tool_call_id':item['call_id'],'content':canonical(value).decode()})
    return messages,{'request_index':index,'sha256':sha(raw)}

def replay_event(view,execution_root,task,files,event,reads,observed):
    tool,args,result=event['tool'],event['arguments'],event['result']
    require(tool in TOOLS and broker_arguments_valid(tool,args)and event['arguments_sha256']==digest(args)and event['result_sha256']==digest(result),'native-broker-event-hashes')
    before=dict(files);checked=None
    if tool!='repo_validate'and result.get('ok')is False:
        require(set(result)=={'ok','error'}and type(result['error'])is str and 0<len(result['error'])<=300 and event['state_sha256']==digest(state(files)),'known-tool-refusal-has-exact-unchanged-state-no-partial-write')
        task_scope(task,files)
        return None,False
    if tool=='repo_validate':checked=validation_result(view,execution_root,result,task,files)
    else:
        require(result.get('ok')is True,'prepared-denied-partial-or-unknown-tool-is-not-success')
        if tool=='repo_read':
            paths=args['paths']
            require(1<=len(paths)<=64 and len(paths)==len(set(paths))
                and set(paths)<=set(files)|set(task['writable_files']), 'read-current-registered-distinct-paths')
            require(type(result.get('files'))is dict and set(result['files'])==set(paths), 'read-exact-result-namespace')
            expected={}
            for p in paths:
                if p not in files:
                    value=result['files'][p]
                    require(p in task['writable_files']and type(value)is dict
                        and set(value)=={'exists','text','sha256'}and value['exists']is False
                        and value['text']is None and value['sha256']is None, 'read-exact-current-writable-absence')
                    expected[p]={'exists':False,'text':None,'sha256':None}
                else:expected[p]={'text':files[p],'sha256':sha(files[p].encode())}
            require(result=={'ok':True,'files':expected},'read-current-raw-bytes')
            reads.update(p for p in paths if p in files and files[p]==task['initial_files'].get(p))
            observed.update({p:sha(files[p].encode())for p in paths if p in files})
        elif tool=='repo_patch':
            changed={}
            for op in args['operations']:
                p=op['path'];old=files.get(p)
                require(p in task['writable_files']and p not in changed and op['old_sha256']==(sha(old.encode())if old is not None else None),'patch-current-scope-precondition')
                require(old is None or observed.get(p)==sha(old.encode()),'patch-requires-current-read-or-write')
                text=_replacement_contents(op,old)
                if text is None:
                    require(old is not None,'deletion-requires-existing-writable-file')
                    require(_confirmed_deletion_readback(result.get('files',{}).get(p),sha(old.encode())), 'patch-confirmed-deletion-readback')
                    changed[p]={'sha256':None,'deleted':True,'previous_sha256':sha(old.encode())};files.pop(p);observed.pop(p,None)
                else:
                    require(type(text)is str and text and text!=old and len(text.encode())<=65536,'patch-real-bounded-change')
                    readback=result.get('files',{}).get(p)
                    require(type(readback)is dict and type(readback.get('byte_size'))is int, 'patch-typed-full-byte-readback')
                    files[p]=text;changed[p]={'sha256':sha(files[p].encode()),'byte_size':len(files[p].encode())};observed[p]=sha(files[p].encode())
            require(result=={'ok':True,'changed':sorted(changed),'files':dict(sorted(changed.items()))},'patch-verified-byte-readback')
        elif tool=='repo_search':
            found=[{'path':p,'line':i,'text':line[:512]}for p,t in sorted(files.items())for i,line in enumerate(t.splitlines(),1)if args['needle']in line]
            require(result=={'ok':True,'matches':found[:100],'truncated':len(found)>=100},'literal-search-current-source')
        elif tool=='repo_status':
            require(result.get('argv_profile')=='git-status-porcelain-v1'and result.get('exit_code')==0 and type(result.get('stdout'))is str and result.get('stdout_sha256')==sha(result['stdout'].encode()),'fixed-status-raw-stream')
    require(event['state_sha256']==digest(state(files)),'every-native-prefix-state')
    task_scope(task,files)
    return checked,files!=before

def usage_from_raw(value):
    normalized=P.raw_usage(value)
    return None if normalized is None else dict(normalized,measurement='actual-official-chat-api-response')

def initial_messages(system,task,instruction):
    require(type(instruction) is str and instruction!='UNBOUND','explicit-reviewed-native-instruction')
    manifest={'initial_paths':sorted(task['initial_files']),'required_read_paths':sorted(task.get('required_read_paths',[])),
              'writable_files':sorted(task['writable_files'])}
    return [{'role':'system','content':system+'\n\n'+instruction},
            {'role':'user','content':task['prompt']+'\n\nRegistered repository paths (public metadata; actual reads remain required):\n'+canonical(manifest).decode()}]

def wire_payload(provider,messages):
    return {'model':MODELS[provider],'messages':messages,'tools':wire_tools(),'tool_choice':'auto','stream':False,
            'thinking':{'type':'disabled'},'max_tokens' if provider=='deepseek' else 'max_completion_tokens':8192}
