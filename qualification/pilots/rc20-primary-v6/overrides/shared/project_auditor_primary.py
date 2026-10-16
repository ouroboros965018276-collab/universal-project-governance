"""Independent native-prefix/project behavior consumer; never executes a task.

Known test FAIL/NOT_RUN is a calibration observation, not raw-integrity FAIL.
Unknown transport/execution/persistence always prevents a complete RAW_PASS.
"""
import copy,re
import base64
from pathlib import Path
import project_receipt_kernels_primary as k
import native_auditor_primary as transport
from reader_binding_primary import NATIVE_INSTRUCTION
from managed_contract_primary import POLICY,ADAPTER,canonical,sha
from reader_binding_primary import require
def digest(value):return sha(canonical(value))
class View:
    def __init__(self,root):
        from reader_binding_primary import tree_map
        self.root=Path(root).absolute();self.before=tree_map(self.root)
    def path(self,name):
        require(type(name)is str and not any(p in('','..','.')for p in name.split('/'))and not name.startswith('/')and'\\'not in name and':'not in name,'relative raw reference')
        value=self.root.joinpath(*name.split('/'));require(self.root in value.resolve().parents,'raw escaped root')
        for p in(value,*value.parents):
            if p==self.root.parent:break
            if p.exists():require(not p.is_symlink()and not getattr(p.lstat(),'st_file_attributes',0)&1024,'raw reparse')
        return value
    def raw(self,name):
        from reader_binding_primary import owned_raw
        raw=owned_raw(self.path(name))
        require(name in self.before and sha(raw)==self.before[name],'raw-read-original-map-bytes')
        return raw
    def json(self,name):
        raw=self.raw(name);value=k.loads(raw)
        if name=='accounting.json':
            import json
            expected=(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
            # save_run uses a text stream's native newline: LF on Linux,
            # CRLF on Windows. Both are exact reviewed writer encodings.
            require(raw in(expected,expected.replace(b'\n',b'\r\n')),'original-atomic-ledger-json')
        elif re.fullmatch(r'actors/[^/]+/artifacts/(?:native/calls/[0-9a-f]{64}/)?execution/validation-[0-9]{3,}/(?:src|trusted|runner)\.cleanup-byte-map\.json',name):
            require(raw==canonical(value),'original-project-cleanup-json')
        else:require(raw==canonical(value)+b'\n','original-canonical-json')
        return value
    def exists(self,name):return self.path(name).is_file()
    def after(self):
        from reader_binding_primary import tree_map
        after=tree_map(self.root);require(after==self.before,'raw changed during independent read');return digest(after)
def verify_actor(view,actor_id,task,system,record,ledger_rows,*,actor_registry,phase=None,require_current_disk=True):
    b=actor_registry[actor_id];provider=b['provider'];folder='actors/'+actor_id+'/artifacts'
    raw=view.raw(folder+'/actor.result.json');result=k.loads(raw)
    verify_git(view,task,record,actor_registry=actor_registry)
    require(record['actor_id']==actor_id and record['provider']==provider and record['artifact_ref']==folder and record['result_ref']==folder+'/actor.result.json'and record['result_sha256']==sha(raw),'original actor record/result')
    transport_verified=transport.verify_actor_transport(view.root,actor_id,result,actor_registry=actor_registry)
    require(transport_verified['accounting_complete']is True,'unknown-accounting-fails-closed')
    require(result.get('execution_state_unknown')is result.get('execution_infrastructure_failed')is False,'unknown-project-or-infrastructure-fails-closed')
    expected={'adapter':ADAPTER,'provider':provider,'model_requested':b['model'],'task_id':task['id'],'input_task_sha256':digest(task),'effective_task_sha256':digest(task),
        'received_state_sha256':digest(k.state(task['initial_files'])),'system_context_sha256':sha(system.encode()),'thinking':'disabled','response_json_mode':False,
        'max_requests':b['max_requests'],'max_tools':32,'output_cap':8192,'timeout_seconds':b['work_seconds'],'application_execution':True,
        'profile_id':'thinking-disabled-deepseek-pro-mimo-flash-8192-v1','reasoning_effort_requested':None,
        'profile_configuration_sha256':'db21a61c86bb3398f9b9568cdb290482407115dfc1ac0be3c21b8fb62ac8ced6','deadline_telemetry_schema':'bounded-post-wait-v1',
        'execution_backend':k.BACKEND,'broker_profile_id':k.BROKER_PROFILE,'schema_correction_limit':1,'connect_retry_policy':'confirmed-pre-http-connect-once-v1',
        'application_execution_scope':'Registered multi-module stdlib Python project commands in the explicit isolated backend; no arbitrary shell, dependency installation, deployment or project_tool lifecycle.',
        'settlement_policy':POLICY,'settlement_max_seconds':600,'work_deadline_monotonic':result['work_deadline_monotonic'],'settlement_deadline_monotonic':result['settlement_deadline_monotonic'],
        'settlement_scope':'Only account the same in-flight HTTPS attempt; no late tools, report, success or new dispatch. Inclusive wall includes settlement.'}
    expected['actor_timing']=record['actor_timing']
    if b['cut_policy']is not None:expected['controlled_phase_stop_policy']=b['cut_policy']
    require(all(canonical(result.get(n))==canonical(v)for n,v in expected.items()),'exact actual API entry')
    for name in('actor.started.json','actor.pending.json'):
        if view.exists(folder+'/'+name):require(canonical(view.json(folder+'/'+name))==canonical(expected),'retained entry original bytes')
    require(not view.exists(folder+'/actor.lock'),'actor lock remains')
    events=[k.loads(line)for line in view.raw(folder+'/broker.jsonl').splitlines()]if view.exists(folder+'/broker.jsonl')else[]
    traces=[view.json(folder+'/tool-receipts/%02d.json'%i)for i in range(1,len(events)+1)]
    require(events==result['tool_events']and traces==result['api_tool_trace']and len(events)<=32,'journal/native trace original copies')
    require(len([n for n in view.before if re.fullmatch(re.escape(folder)+r'/tool-receipts/\d{2}\.json',n)])==len(traces),'orphan native trace')
    files=copy.deepcopy(task['initial_files']);reads=set();observed={};last_tools={};last_validation=None;event_index=0;previous=None;seen=set();attempts=0;finish=None;closed=False;schemas=[];schema_count=0
    messages=k.initial_messages(system,task,NATIVE_INSTRUCTION)
    names=[folder+'/requests/%02d.receipt.json'%i for i in range(1,result['requests']+1)]
    for index,name in enumerate(names,1):
        require(not closed,'request after closed prefix');receipt=view.json(name);rr=view.raw(name);payload=k.wire_payload(provider,messages)
        require(receipt['request_payload_sha256']==digest(payload)and receipt['input_utf8_bytes']==len(canonical(payload))and receipt['input_task_sha256']==digest(task),'exact native payload/messages')
        require(all(canonical(receipt[n])==canonical(expected[n])for n in('adapter','provider','model_requested','profile_id','thinking','reasoning_effort_requested','profile_configuration_sha256','execution_backend','broker_profile_id','settlement_policy','settlement_max_seconds','work_deadline_monotonic','settlement_deadline_monotonic')),'native entry/deadline identity')
        if receipt['not_invoked']is True:continue # Independent ledger reader checks exact parent/grant/child.
        response_raw=view.raw(folder+'/requests/%02d.response.json'%index);response=view.json(folder+'/requests/%02d.response.json'%index)['response'];rid=response['id']
        final_deadline=result['work_deadline_reached']is True and index==len(names)
        native_late=receipt['settlement']['accounting_only']or receipt['settlement']['actor_elapsed_before_account_seconds']>=b['work_seconds']
        remaining_for_response=any(t['api_response_id']==rid for t in traces[event_index:])
        finish_for_response=result.get('final_report')is not None and result['final_report']['api_response_id']==rid
        if native_late or(final_deadline and not remaining_for_response and not finish_for_response and result['tool_attempts']==attempts):
            require(index==len(names)and not remaining_for_response and not finish_for_response,'late response cannot execute or continue');closed=True;continue
        choice=response['choices'][0];message=choice['message'];messages.append({n:message[n]for n in('role','content','reasoning_content','tool_calls')if n in message})
        calls=message.get('tool_calls')or[]
        if not isinstance(calls,list)or len(calls)>32-attempts:
            require(index==len(names)and event_index==len(events)and not remaining_for_response and not finish_for_response and result['status']=='tool-contract-failed','known whole-batch budget/shape refusal before admitted attempts')
            closed=True;continue
        attempts+=len(calls)
        if not calls or choice.get('finish_reason')!='tool_calls'or(len(calls)!=1 and any(c.get('function',{}).get('name')=='repo_finish'for c in calls)):
            require(index==len(names),'known rejected batch must terminate');closed=True;continue
        try:parsed,rejected=k.batch_shape(calls,seen,task)
        except k.EvidenceError:
            require(index==len(names)and result['status']=='tool-contract-failed'and event_index==len(events),'known native envelope refusal before broker');closed=True;continue
        if rejected:
            schema_count+=1;projection,ref=k.schema_rejection(view,folder,index,receipt,response_raw,calls,seen,task,files,schema_count)
            schemas.append(ref);seen.update(p['call_id']for p in parsed)
            if schema_count>1:require(index==len(names),'second schema correction cannot continue');closed=True
            else:messages.extend(projection)
            continue
        if phase is not None and phase['phase']=='validated-batch-before-tool-delivery'and index==phase['api_requests_observed']:
            require(index==len(names)and event_index==0 and not rejected,'phase-zero-tool-exact-full-valid-batch')
            seen.update(c['id']for c in calls);closed=True;continue
        for call in calls:
            tool=call['function']['name'];identifier=call['id'];args=k.loads(call['function']['arguments']);seen.add(identifier)
            if final_deadline and event_index==len(events)and not finish_for_response:
                closed=True;break # Honest unconsumed tail after a per-tool cutoff.
            if tool=='repo_finish':
                finish=view.json(folder+'/report-receipt.json')
                k.P.check_native_finish(response_raw,receipt,finish,digest(k.state(files)),previous,event_index,seen-{identifier},receipt_raw=rr)
                require(finish['adapter']==ADAPTER and finish['broker_profile_id']==k.BROKER_PROFILE and finish['execution_backend']==k.BACKEND,'finish project identity')
                require(index==len(names)and len(calls)==1 and finish==result['final_report']and result['final_report_receipt_sha256']==sha(view.raw(folder+'/report-receipt.json')),'sole original terminal finish')
                closed=True;continue
            require(event_index<len(events),'native operation needs original broker event');event=events[event_index];trace=traces[event_index]
            require(event['sequence']==event_index+1 and event['tool']==tool and event['arguments']==args,'native to broker call order')
            k.P.check_native_event(response_raw,receipt,event,trace)
            require(trace['adapter']==ADAPTER and trace['broker_profile_id']==k.BROKER_PROFILE and trace['execution_backend']==k.BACKEND and trace['previous_chain_sha256']==previous and trace['chain_sha256']==digest({n:v for n,v in trace.items()if n!='chain_sha256'}),'original native chain')
            previous=trace['chain_sha256'];event_index+=1
            if tool=='repo_validate':require(type(event['result'].get('checks_total'))is int and type(event['result'].get('checks_passed'))is int,'typed project check counts')
            checked,_=k.replay_event(view,folder+'/execution',task,files,event,reads,observed)
            if checked is not None:last_validation=(event['state_sha256'],event['result'],checked)
            if event['result'].get('ok')is True:last_tools[tool]=event['state_sha256']
            if event['result'].get('ok')is False and tool!='repo_validate':require(index==len(names)and event_index==len(events),'non-validation refusal cannot recover');closed=True;break
            messages.append({'role':'tool','tool_call_id':identifier,'content':canonical(event['result']).decode()})
    current=digest(k.state(files));require(event_index==len(events),'unbound broker action')
    require(result['schema_rejections']==schema_count and result['schema_rejection_receipts']==schemas,'every schema correction')
    require(result['final_state_snapshot']==k.state(files)and result['final_state_sha256']==current,'final-source-prefix-exact')
    if require_current_disk:require(k.K.disk_files(view.path(record['workspace_ref']))==files,'actual-final-disk-prefix-bytes')
    require(result['tool_attempts']==attempts,'native tool attempt count')
    checked=last_validation[2]if last_validation is not None and last_validation[0]==current else None
    if checked is not None and phase is None:require(result['quality'].get('validation')==last_validation[1],'current original project validation')
    elif phase is None:require(result['quality'].get('validation')is None and result['quality'].get('final_execution_not_run_reason')=='required-current-project-validation-missing','typed current NOT_RUN')
    if phase is not None:require(result['quality'].get('validation')is None,'phase-source-never-graded')
    strict=bool(checked is not None and checked['ok']and set(task['required_tools'])<=set(last_tools)and all(last_tools.get(t)==current for t in('repo_validate','repo_status'))
        and files!=task['initial_files']and k.required_initial_reads(events,task)and finish is not None and finish['report']['validation']=='passed'and result['status']=='completed'and not result['work_deadline_reached'])
    require(result['quality']['hard_pass']is strict,'independent behavior versus producer hard-pass')
    if phase is not None:
        require(not strict and result['quality']['task_success']is None and result['quality'].get('source_completed')is False and result['quality'].get('source_graded')is False and result['quality'].get('assessment')=='NOT_GRADED_CONTROLLED_STOP','controlled-source-is-unfinished-ungraded')
    elif result['work_deadline_reached']:require(result['quality']['task_success']is False,'settled unfinished cannot succeed')
    else:require(type(result['quality']['task_success'])is int and result['quality']['task_success']==int(strict),'independent task success')
    if finish is None:require(result['final_report']is None and not view.exists(folder+'/report-receipt.json'),'no invented finish')
    expected_exec={folder+'/execution/'+e['result']['execution']['receipt_ref']for e in events if e['tool']=='repo_validate'}
    actual_exec={n for n in view.before if re.fullmatch(re.escape(folder)+r'/execution/validation-\d+/result\.json',n)}
    require(actual_exec==expected_exec,'all and only native-bound project execution receipts')
    return {'raw_integrity':True,'actor_id':actor_id,'independent_task_pass':strict,'current_checks_total':len(task['engineering_contract']['checks']),
        'current_checks_passed':checked['checks_passed']if checked else None,'current_validation':'EXECUTED'if checked else'NOT_RUN',
        'scope':'original registered unittest IDs/import/CLI/file-processing receipt semantics; not universal efficacy','settled_unfinished':result['work_deadline_reached'],
        '_replayed_files':files,'_events':events,'_traces':traces}

def verify_git(view,task,record,*,actor_registry):
    """Original seven-command source / same-baseline two-command receiver."""
    host=view.json('host-identity.json');entry=record['git_entry']
    role=actor_registry[record['actor_id']]['role'];workflow=record['workflow_id']
    ref='git-baselines/'+workflow+'/'+role+'.json'
    require(set(entry)=={'ref','sha256','baseline_commit'}and entry['ref']==ref
        and sha(view.raw(ref))==entry['sha256'],'original-role-git-entry-reference')
    saved=view.json(ref)
    require(saved['schema_version']=='stdlib-project-chain-git-entry-v7'
        and saved['initial_commit_created']is(role=='source')
        and saved['baseline_commit']==entry['baseline_commit']
        and re.fullmatch('[0-9a-f]{40}',entry['baseline_commit']),'git-baseline-identity')
    args=[['rev-parse','HEAD'],['status','--porcelain=v1','--untracked-files=all']]
    if role=='source':
        args=[['init','--quiet'],['config','user.name','UPG Development Fixture'],
              ['config','user.email','upg-development@example.invalid'],['add','--',*sorted(task['initial_files'])],
              ['commit','--quiet','-m','Registered source initial snapshot']]+args
    rows=saved['commands'];require(len(rows)==len(args),'fixed-role-git-command-count')
    safe=['--no-optional-locks','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-c','core.autocrlf=false']
    cwd=str(view.path(record['workspace_ref']).resolve())
    for i,(row,arguments)in enumerate(zip(rows,args),1):
        require(set(row)=={'argv','cwd','returncode','stdout_base64','stderr_base64','stdout_sha256','stderr_sha256','wall_seconds','before_receipt_sha256','after_receipt_sha256'}
            and row['argv']==[host['git']['path'],*safe,*arguments]and row['cwd']==cwd
            and type(row['returncode'])is int and row['returncode']==0 and k.P.finite(row['wall_seconds']),'fixed-actual-git-argv-result')
        prefix=ref[:-5]+'.command-%02d'%i
        before=view.raw(prefix+'.before.json');after=view.raw(prefix+'.after.json')
        require(sha(before)==row['before_receipt_sha256']and sha(after)==row['after_receipt_sha256'],'git-original-linked-raw')
        require(k.loads(before)=={'schema_version':'stdlib-project-git-command-before-v7','git_binary':host['git']['path'],
            'helper_arguments':arguments,'cwd':cwd,'scope':'fixed canonical git_command adds its pinned safe flags; not proof of completion'},'git-before-envelope')
        require(after==canonical({n:v for n,v in row.items()if n!='after_receipt_sha256'})+b'\n','git-after-envelope')
        for name in('stdout','stderr'):
            require(sha(base64.b64decode(row[name+'_base64'],validate=True))==row[name+'_sha256'],'git-original-stream-hash')
    require(base64.b64decode(rows[-2]['stdout_base64']).decode().strip()==entry['baseline_commit'],'git-source-baseline-revision')
    if role=='source':require(base64.b64decode(rows[-1]['stdout_base64'])==b'','initial-source-clean-status')
