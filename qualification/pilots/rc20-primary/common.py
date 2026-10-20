"""Primary assembly identity, bounded reads and shared source loading.

The assembly map is canonical. source-map.json is its shared/ subview for the
unchanged C3 collector; neither map permits adding a source after registration.
Importing this module cannot load a key, API, project or actual reader.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
IDENTITY = 'rc20-primary-nine-family-api7-v1'
STUDY_KIND = 'PRIMARY_NINE_FAMILY_DEVELOPMENT'
ANALYSIS_SHA = '50b5d41812424c1c0cb2bb950473546bd15cf0fc12ca9dace0f410da0767caec'
COUNTS = {'blocks':18,'workflows':54,'actors':66,'families':9,'single_families':7,'controlled_families':2}


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, code):
    if not value:raise ValueError(code)


def valid_sha(value):
    return type(value)is str and re.fullmatch('[0-9a-f]{64}',value)is not None


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            require(key not in result,'duplicate JSON key');result[key]=value
        return result
    return json.loads(raw.decode('utf-8',errors='strict'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite JSON')))


def relative(name):
    require(type(name)is str and '\\'not in name and ':'not in name
        and all(piece not in('','.','..')for piece in name.split('/')),'unsafe source reference')
    return name


def regular_bytes(path):
    path=Path(path)
    for current in(path,*path.parents):
        info=current.lstat()
        require(not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'linked namespace')
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode)and info.st_nlink==1,'single regular file required')
    raw=path.read_bytes();after=path.lstat()
    require((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)and len(raw)==info.st_size,'file changed while reading')
    return raw


TRUSTED_HOST_BINARIES={
    'python':{'path':r'C:\Users\96501\AppData\Local\Programs\Python\Python312\python.exe','sha256':'4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a'},
    'git':{'path':r'D:\DevTools\Git\cmd\git.exe','sha256':'7cd588850959546663c81077af076835558c6a6af33506a64a65784743df92a1'},
    'docker':{'path':r'D:\DockerDesktop\resources\bin\docker.exe','sha256':'1aaf3dd59c24ff4c83d930bc51ecac8bf6f6f4e7a310573ee69d14ca3a7ef85c'}}


def trusted_binary_bytes(role,path,expected_sha256):
    require(role in TRUSTED_HOST_BINARIES,'unknown trusted binary role')
    require({'path':str(path),'sha256':expected_sha256}==TRUSTED_HOST_BINARIES[role],'trusted binary exact role/path/hash differs')
    path=Path(path)
    for target in(path,*path.parents):
        info=target.lstat()
        require(not stat.S_ISLNK(info.st_mode)and not getattr(info,'st_file_attributes',0)&1024,'trusted binary linked namespace')
    before=path.lstat();require(stat.S_ISREG(before.st_mode),'trusted binary must be regular')
    raw=path.read_bytes();after=path.lstat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_nlink)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_nlink)
        and len(raw)==before.st_size and sha(raw)==expected_sha256,'trusted binary changed or differs')
    return raw


def immutable(path,value):
    raw=canonical(value)+b'\n';path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as stream:
        require(stream.write(raw)==len(raw),'short immutable write');stream.flush();os.fsync(stream.fileno())
    require(regular_bytes(path)==raw,'immutable readback differs')
    return sha(raw)


def file_map(root):
    root=Path(root);info=root.lstat()
    require(stat.S_ISDIR(info.st_mode)and not stat.S_ISLNK(info.st_mode)
        and not getattr(info,'st_file_attributes',0)&1024,'unsafe map root')
    result={}
    for directory,dirs,leaves in os.walk(root,followlinks=False):
        for name in dirs:
            info=(Path(directory)/name).lstat()
            require(stat.S_ISDIR(info.st_mode)and not stat.S_ISLNK(info.st_mode)
                and not getattr(info,'st_file_attributes',0)&1024,'unsafe map directory')
        for name in leaves:
            path=Path(directory)/name;result[path.relative_to(root).as_posix()]=sha(regular_bytes(path))
    return dict(sorted(result.items()))


def owner_observation(p):
    """One original ownership namespace, with explicit parent/supervisor prefixes."""
    _,owner,supervisor=roots(p)
    return {**{'owner/'+key:value for key,value in file_map(owner).items()},
        **{'supervisor/'+key:value for key,value in file_map(supervisor).items()}}


def roots(p):
    values=[p[name]for name in('run_root','owner_root','supervisor_root')]
    require(all(type(value)is str and value!='UNBOUND'for value in values),'actual roots remain UNBOUND')
    paths=tuple(Path(value).resolve()for value in values)
    require(len(set(paths))==3 and all(path.is_absolute()and path!=HERE and HERE not in path.parents
        and path not in HERE.parents for path in paths),'new external disjoint roots required')
    require(all(a not in b.parents and b not in a.parents for i,a in enumerate(paths)for b in paths[i+1:]),'nested actual roots')
    return paths


def pinned_json(path,expected,*,canonical_digest=False,with_raw=False):
    """Bind the consumed JSON object to one captured registered buffer."""
    raw=regular_bytes(Path(path))
    if not canonical_digest:require(sha(raw)==expected,'registered JSON raw SHA differs')
    value=strict_json(raw)
    if canonical_digest:require(sha(canonical(value))==expected,'registered JSON canonical SHA differs')
    return (raw,value)if with_raw else value


def source_observation(bundle,expected_protocol_sha256):
    bundle=Path(bundle);result={}
    p=pinned_json(bundle/'protocol.json',expected_protocol_sha256)
    raw,manifest=pinned_json(bundle/'assembly-source-map.json',p['assembly_source_manifest_sha256'],with_raw=True)
    result[str(bundle/'assembly-source-map.json')]=sha(raw)
    local=manifest['source_map'];require(type(local)is dict and local,'complete assembly map')
    for name,digest in local.items():
        path=HERE/relative(name);result[str(path)]=sha(regular_bytes(path))
        require(result[str(path)]==digest,'assembly source drift:'+name)
    shared_raw,shared_value=pinned_json(bundle/'source-map.json',p['source_manifest_sha256'],with_raw=True);shared=shared_value['source_map']
    require(shared=={name[len('shared/'):]:digest for name,digest in local.items()if name.startswith('shared/')},'shared subview differs')
    result[str(bundle/'source-map.json')]=sha(shared_raw)
    deps_raw,deps=pinned_json(bundle/'dependencies.json',p['dependencies_sha256'],with_raw=True)
    result[str(bundle/'dependencies.json')]=sha(deps_raw)
    for name,digest in deps['source_pins'].items():
        require(valid_sha(digest),'external source remains UNBOUND')
        result[name]=sha(regular_bytes(Path(name)));require(result[name]==digest,'external source drift')
    require(deps['binary_pins']==TRUSTED_HOST_BINARIES,'fixed three trusted host binaries')
    for role,binding in deps['binary_pins'].items():
        result[binding['path']]=sha(trusted_binary_bytes(role,binding['path'],binding['sha256']))
    return dict(sorted(result.items()))


def module(name,relative_name,manifest):
    return external_module(name,HERE/relative(relative_name),
        {str(HERE/key):digest for key,digest in manifest['source_map'].items()})


def external_module(name,path,pins):
    path=Path(path).resolve();require(pins.get(str(path))==sha(regular_bytes(path)),'module omitted/differs:'+name)
    if name in sys.modules:
        require(Path(sys.modules[name].__file__).resolve()==path,'foreign module:'+name);return sys.modules[name]
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value


def shared_module(bundle,name,expected_protocol_sha256):
    p=pinned_json(Path(bundle)/'protocol.json',expected_protocol_sha256)
    manifest=pinned_json(Path(bundle)/'assembly-source-map.json',p['assembly_source_manifest_sha256'])
    sys.path.insert(0,str(HERE/'shared'))
    return module(name,'shared/'+name+'.py',manifest)


def runtime(bundle,expected_protocol_sha256):
    p=pinned_json(Path(bundle)/'protocol.json',expected_protocol_sha256)
    deps=pinned_json(Path(bundle)/'dependencies.json',p['dependencies_sha256'])
    manifest=pinned_json(Path(bundle)/'assembly-source-map.json',p['assembly_source_manifest_sha256'])
    source_observation(bundle,expected_protocol_sha256)
    runtime_root=HERE/'shared/repository';sys.dont_write_bytecode=True
    require(Path(deps['runtime_root']).resolve()==runtime_root,'runtime origin')
    sys.path.insert(0,str(runtime_root));sys.path.insert(0,str(HERE/'shared'))
    import importlib
    api=importlib.import_module('evolution.provider_tools');broker=importlib.import_module('evolution.engineering_broker')
    require(Path(api.__file__).resolve()==runtime_root/'evolution/provider_tools.py','foreign API7')
    require(sha(regular_bytes(Path(api.__file__)))=='e6bff4926c3c725d0937dc5e0f77e58517b861665fe052810e4a6d223caa3363','exact API7 source')
    modules=[shared_module(bundle,name,expected_protocol_sha256)for name in('managed_contract_primary','ledger_primary','collector_primary','raw_auditor_primary','native_auditor_primary')]
    pins=manifest['source_map']
    for name,value in tuple(sys.modules.items()):
        if getattr(value,'__file__',None)and(name=='evolution'or name.startswith(('evolution.','tools.'))):
            path=Path(value.__file__).resolve();require(runtime_root in path.parents,'foreign transitive runtime')
            require(pins.get(path.relative_to(HERE).as_posix())==sha(regular_bytes(path)),'transitive source omitted')
    return api,broker,*modules


def protocol(bundle,expected,*,allow_unbound=False):
    bundle=Path(bundle).resolve();raw=regular_bytes(bundle/'protocol.json')
    require(sha(raw)==expected,'external protocol SHA differs');p=strict_json(raw)
    require(p['identity']==IDENTITY and p['study_kind']==STUDY_KIND and p['counts']==COUNTS,'fixed primary identity/denominator')
    inputs={}
    for name,field in(('assembly-source-map.json','assembly_source_manifest_sha256'),('source-map.json','source_manifest_sha256'),
        ('dependencies.json','dependencies_sha256'),('workflow-order.json','order_sha256'),('workflow-specs.json','workflow_specs_sha256'),
        ('arm-contexts.json','contexts_sha256'),('host-identity.json','host_identity_sha256'),('fixture-binding.json','fixture_binding_sha256'),
        ('manual-assignment.json','manual_assignment_sha256'),('analysis-registration.json','analysis_registration_sha256')):
        captured=regular_bytes(bundle/name)
        require(sha(captured)==p[field],'registered input differs:'+name)
        inputs[name]=captured
    require(p['analysis_registration_sha256']==ANALYSIS_SHA,'v8 quality/cost/stop identity')
    manifest=strict_json(inputs['assembly-source-map.json'])
    require(p['manual_binding']['helper_sha256']==manifest['source_map']['manual/helper.py']
        and p['analysis_consumer_source_sha256']==manifest['source_map']['analyze_primary.py'],'frozen post-audit module identities')
    order_module=module('primary_order_admission','shared/order_primary.py',manifest)
    order=strict_json(inputs['workflow-order.json']);specs=strict_json(inputs['workflow-specs.json'])['workflows']
    headers=[{'case_id':row['case_id'],'cut_policy':row['cut_policy']}for row in specs]
    require(order_module.make_order(headers,order['seed'])==order,'fair seeded order differs')
    actors=order_module.actor_registry(order)
    require(p['actor_registry']==actors and len(actors)==66,'complete immutable primary map')
    require(p['ledger_registry_identity']=={'source_sha256':sha(regular_bytes(HERE/'shared/order_primary.py')),
        'actor_registry_sha256':sha(canonical(actors)),'expected_actor_count':66},'primary registry source/count/hash')
    require(p['actor_caps']=={'seconds':180,'requests':12,'tools':32,'minimum_dispatch_seconds':15}
        and p['round_caps']['round_seconds_soft']==54840 and p['round_caps']['request_slots']==792,'fixed primary limits')
    assignment_module=module('primary_panel_admission','manual_assignment.py',manifest)
    assignment=strict_json(inputs['manual-assignment.json'])
    require(assignment==assignment_module.make_panels(order,p['manual_assignment_seed']),'pre-result panel assignment differs')
    configuration_raw=regular_bytes(bundle/'profile-configuration.json')
    require(sha(canonical(strict_json(configuration_raw)))==p['configuration_sha256'],'profile configuration')
    if not allow_unbound:
        require(p['actual_readiness']=='BOUND_BY_SEPARATE_ROOT_ADMISSION'and valid_sha(p['independent_source_closure_sha256']),'primary readiness UNBOUND')
        require(p['fixture_backend_qualification']=='KNOWN_INDEPENDENT_FIXED_CONTROLS_PASS'
            and p['api7_real_calibration']=='KNOWN_INDEPENDENT_NEW_HOOK_PATHS_PASS','independent prerequisites UNBOUND')
        require(all(valid_sha(p[name])for name in('fixture_qualification_receipt_sha256','api7_calibration_receipt_sha256','owner_closure_sha256')),'qualification/owner bridge missing')
        require(p['manual_binding']['helper_sha256']==manifest['source_map']['manual/helper.py']
            and p['manual_binding']['authorization']!='UNBOUND'
            and p['analysis_consumer_authorization']!='UNBOUND','manual/analysis grant UNBOUND')
        require(p['trusted_planner_preparation']=='EXECUTED_FIXED_TWO_PACKAGES','stub planner context cannot enter actual')
        require(p['baseline_runtime_commit']=='bd4a4d5c1c6fb9fca829e410729879d1b01f05b9'
            and p['baseline_runtime_provenance_receipt_sha256']=='5e7a2926601995c82b25cc496cdb7677cb545a0cd413e8a3cdaeb16d87d72f98',
            'RC19 source commit provenance differs')
        baseline_module=module('primary_baseline_admission','prepare_bundle.py',manifest)
        require(p['runtime_packages']==baseline_module.validate_runtime_packages(),'frozen packages differ from Git-bound baseline/current full')
        roots(p);source_observation(bundle,expected)
    return p,manifest


def host_check(host):
    for role in('python','git','docker'):trusted_binary_bytes(role,host[role]['path'],host[role]['sha256'])
    require(Path(sys.executable).resolve()==Path(host['python']['path']).resolve(),'actual Python differs')
