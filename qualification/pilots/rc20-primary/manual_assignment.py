"""Before-result finite assignment: six fresh panels, no family counterparts."""
import random
def make_panels(order,seed):
    if type(seed)is not int or type(order)is not dict or len(order['workflows'])!=54:
        raise ValueError('fixed full primary order and independent integer assignment seed')
    families={}
    for row in order['workflows']:families.setdefault(row['case_id'],[]).append(row)
    if len(families)!=9 or any(len(rows)!=6 for rows in families.values()):raise ValueError('nine groups of six counterparts')
    rng=random.Random(seed);panels={'panel-%d'%i:[]for i in range(1,7)}
    for family,rows in sorted(families.items()):
        rows=sorted(rows,key=lambda row:row['workflow_id']);rng.shuffle(rows)
        for panel,row in zip(panels,rows):
            actors=[row['source_actor_id']]+([row['receiver_actor_id']]if row['receiver_actor_id']else[])
            panels[panel].append({'case_id':family,'workflow_id':row['workflow_id'],'actor_ids':actors})
    allactors=[actor for rows in panels.values()for row in rows for actor in row['actor_ids']]
    if len(allactors)!=66 or len(set(allactors))!=66 or any(sum(len(row['actor_ids'])for row in rows)!=11 for rows in panels.values()):
        raise ValueError('six panels require eleven unique stages each')
    return {'schema':'primary-six-panel-assignment-v1','assignment_seed':seed,'panels':panels,
        'reviewer_context_rule':'fresh context per panel; only its nine workflows/eleven opaque packets; no family counterpart condition/provider/cost access',
        'assignment_uses_results':False}

def project_public_panel(assignment,condition_map,public_packets,panel_id):
    """Owner-side opaque subset only; graders never receive condition_map."""
    wanted={actor for row in assignment['panels'][panel_id]for actor in row['actor_ids']}
    stages=condition_map['stages'];selected={row['packet_id']for row in stages if row['actor_id']in wanted}
    if len(selected)!=11 or len(wanted)!=11:raise ValueError('exact preassigned panel subset')
    return {'schema':'primary-blind-panel-packets-v1','packets':{key:public_packets['packets'][key]for key in sorted(selected)}}
