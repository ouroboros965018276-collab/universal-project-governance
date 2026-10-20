"""Single registered activation of the unchanged shared C3 workflow collector."""
from pathlib import Path
from common import protocol,roots,runtime,require,immutable,sha,regular_bytes

ENABLED=False
ACTUAL_ENTRY_AUTHORIZATION='UNBOUND'


def collect(bundle,protocol_sha256,lazy_key_loader):
    require(ENABLED is True and ACTUAL_ENTRY_AUTHORIZATION==protocol_sha256,'assembly actual grant absent')
    p,_=protocol(bundle,protocol_sha256);run,owner,supervisor=roots(p)
    require(not run.exists()and owner.is_dir()and supervisor.is_dir(),'single owned launch/new raw root required')
    api,broker,contract,ledger,shared,raw,native=runtime(bundle,protocol_sha256)
    require(shared.ENABLED is False and shared.ACTUAL_ENTRY_AUTHORIZATION=='UNBOUND','unexpected shared activation')
    require(raw.READINESS_BINDINGS['actual_registration']=='UNBOUND','unexpected shared raw activation')
    prior=dict(raw.READINESS_BINDINGS)
    immutable(owner/'collector-activation.before.json',{'protocol_sha256':protocol_sha256,
        'shared_collector_source_sha256':sha(regular_bytes(Path(shared.__file__))),
        'shared_raw_source_sha256':p['raw_auditor_source_sha256'],
        'bounded_in_memory_activation_only':True,'no_source_rewrite':True})
    shared.ENABLED=True;shared.ACTUAL_ENTRY_AUTHORIZATION=protocol_sha256
    raw.READINESS_BINDINGS['actual_registration']=protocol_sha256
    try:
        return shared.collect(bundle,run,protocol_sha256,lazy_key_loader)
    finally:
        shared.ENABLED=False;shared.ACTUAL_ENTRY_AUTHORIZATION='UNBOUND'
        raw.READINESS_BINDINGS.clear();raw.READINESS_BINDINGS.update(prior)
        immutable(owner/'collector-activation.after.json',{'protocol_sha256':protocol_sha256,
            'shared_collector_disabled':shared.ENABLED is False,'shared_collector_grant':shared.ACTUAL_ENTRY_AUTHORIZATION,
            'shared_raw_readiness_restored':raw.READINESS_BINDINGS==prior})
