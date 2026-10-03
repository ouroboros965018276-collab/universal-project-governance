from __future__ import annotations
import argparse,json,pathlib,hashlib

def build(config):
    cases=[]; n=0
    for obj in config["objects"]:
        for lang,key in (("en","positive_templates_en"),("zh","positive_templates_zh")):
            for template in config[key]:
                n+=1; cases.append({"id":"P%03d"%n,"query":template.format(object=obj[lang]),"should_trigger":True,"language":lang,"object_id":obj["id"]})
        for lang,key in (("en","negative_templates_en"),("zh","negative_templates_zh")):
            for template in config[key]:
                n+=1; cases.append({"id":"N%03d"%n,"query":template.format(object=obj[lang]),"should_trigger":False,"language":lang,"object_id":obj["id"]})
    return cases

def metrics(records):
    tp=fp=tn=fn=0
    for r in records:
        exp=bool(r["should_trigger"]); got=bool(r["triggered"])
        if exp and got: tp+=1
        elif exp and not got: fn+=1
        elif not exp and got: fp+=1
        else: tn+=1
    precision=tp/float(tp+fp) if tp+fp else 0.0
    recall=tp/float(tp+fn) if tp+fn else 0.0
    fpr=fp/float(fp+tn) if fp+tn else 0.0
    fnr=fn/float(fn+tp) if fn+tp else 0.0
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":precision,"recall":recall,"false_positive_rate":fpr,"false_negative_rate":fnr}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--config",default="qualification/fixtures/trigger-families.json"); ap.add_argument("--output"); args=ap.parse_args()
    cfg=json.loads(pathlib.Path(args.config).read_text(encoding="utf-8")); cases=build(cfg)
    payload={"schema_version":1,"cases":cases,"sha256":hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
    # ASCII JSON keeps Chinese samples intact through narrow Windows pipe encodings.
    text=json.dumps(payload,indent=2,ensure_ascii=True)+"\n"
    if args.output: pathlib.Path(args.output).write_text(text,encoding="utf-8")
    else: print(text,end="")
    return 0
if __name__=="__main__": raise SystemExit(main())
