from __future__ import annotations
import argparse,hashlib,json,pathlib,random,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qualification.lib.core import normalized_outcome

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("left"); ap.add_argument("right"); ap.add_argument("--seed",required=True); ap.add_argument("--output"); args=ap.parse_args()
    a=json.loads(pathlib.Path(args.left).read_text(encoding="utf-8")); b=json.loads(pathlib.Path(args.right).read_text(encoding="utf-8"))
    if a["scenario_id"]!=b["scenario_id"]: raise SystemExit("scenario mismatch")
    rng=random.Random(args.seed); items=[normalized_outcome(a),normalized_outcome(b)]; rng.shuffle(items)
    payload={"schema_version":1,"scenario_id":a["scenario_id"],"candidates":{"X":items[0],"Y":items[1]},"judge_prompt":"Choose X, Y, tie, or critical_failure using only observable outcome evidence. Do not infer treatment or model identity."}
    text=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if args.output: pathlib.Path(args.output).write_text(text,encoding="utf-8")
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
