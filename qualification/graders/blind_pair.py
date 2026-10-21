from __future__ import annotations
import argparse,json,os,pathlib,random,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from qualification.lib.core import normalized_outcome

def atomic_json(path, payload):
    path=pathlib.Path(path)
    fd,name=tempfile.mkstemp(prefix=path.name+".",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            stream.write(json.dumps(payload,indent=2,sort_keys=True)+"\n")
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("left"); ap.add_argument("right"); ap.add_argument("--seed",required=True); ap.add_argument("--output"); ap.add_argument("--mapping-output",help="Private operator artifact; do not give to the blind judge"); args=ap.parse_args()
    try:
        a=json.loads(pathlib.Path(args.left).read_text(encoding="utf-8")); b=json.loads(pathlib.Path(args.right).read_text(encoding="utf-8"))
        for row in (a,b):
            if not isinstance(row,dict) or not isinstance(row.get("scenario_id"),str) or not isinstance(row.get("outcome"),dict) or row.get("kind") not in {"behavioral","handoff","trigger"}:
                raise ValueError("inputs require scenario_id, kind, and an outcome object")
        if a["scenario_id"]!=b["scenario_id"]: raise ValueError("scenario mismatch")
        order=[0,1]; random.Random(args.seed).shuffle(order)
        items=[normalized_outcome((a,b)[index]) for index in order]
        if args.mapping_output:
            if args.output and pathlib.Path(args.output).resolve()==pathlib.Path(args.mapping_output).resolve(): raise ValueError("mapping must be separate from blinded output")
            atomic_json(args.mapping_output,{"schema_version":1,"seed":args.seed,"X":("left","right")[order[0]],"Y":("left","right")[order[1]]})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise SystemExit("invalid blind-pair input: "+str(exc))
    payload={"schema_version":1,"scenario_id":a["scenario_id"],"candidates":{"X":items[0],"Y":items[1]},"judge_prompt":"Choose X, Y, tie, or critical_failure using only observable outcome evidence. Do not infer treatment or model identity."}
    text=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if args.output: atomic_json(args.output,payload)
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
