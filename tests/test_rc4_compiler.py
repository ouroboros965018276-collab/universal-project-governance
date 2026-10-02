from __future__ import annotations
import json, pathlib, shutil, subprocess, sys, tempfile, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
PY=sys.executable
RUNTIME=ROOT/"universal-project-governance"

def run(*args,cwd=None):
    return subprocess.run([PY,*map(str,args)],cwd=str(cwd or ROOT),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)

class RC4CompilerTests(unittest.TestCase):
    def test_compiler_drift_check(self):
        cp=run("compiler/compile_governance.py","--check")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)

    def test_governance_lint_and_budget(self):
        cp=run("tools/governance_lint.py",".")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertLessEqual(len((RUNTIME/"SKILL.md").read_text(encoding="utf-8").splitlines()),120)
        self.assertFalse((RUNTIME/"references").exists())
        self.assertFalse((RUNTIME/"assets").exists())

    def test_runtime_integrity(self):
        cp=run(RUNTIME/"scripts/validate_integrity.py",RUNTIME)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)

    def test_integrity_detects_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            dst=pathlib.Path(td)/RUNTIME.name
            shutil.copytree(RUNTIME,dst)
            p=dst/"SKILL.md"; p.write_text(p.read_text(encoding="utf-8")+"\nmutated\n",encoding="utf-8")
            cp=subprocess.run([PY,str(dst/"scripts/validate_integrity.py"),str(dst)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertNotEqual(cp.returncode,0)
            self.assertIn("integrity mismatch",cp.stderr)

    def test_compiler_write_requires_confirmation(self):
        cp=run("compiler/compile_governance.py","--write")
        self.assertEqual(cp.returncode,2)

    def test_plan_cases(self):
        cases=json.loads((ROOT/"evals/rc4_plan_cases.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory() as td:
                ctx=pathlib.Path(td)/"context.json"; ctx.write_text(json.dumps(case["context"]),encoding="utf-8")
                cp=subprocess.run([PY,str(RUNTIME/"scripts/plan_governance.py"),"--context",str(ctx),"--json"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
                self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
                plan=json.loads(cp.stdout); exp=case["expect"]
                for key in ("risk_level","report","handoff"):
                    if key in exp: self.assertEqual(plan[key],exp[key])
                for rid in exp.get("contains",[]): self.assertIn(rid,plan["active_rules"])
                if "max_rules" in exp: self.assertLessEqual(len(plan["active_rules"]),exp["max_rules"])

    def test_handoff_schema_validate_and_render(self):
        sample={"updated_at":"2026-10-03T00:00:00+08:00","goal":"Continue migration","status":"in_progress","completed":["new endpoint"],"in_progress":["consumer cutover"],"decisions":["v2 canonical"],"invariants":["no dual truth"],"risks":["legacy client"],"next_actions":["migrate client"],"validation":["contract tests"],"canonical_sources":["PROJECT_STATE.md"]}
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/"handoff.json"; p.write_text(json.dumps(sample),encoding="utf-8")
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"validate",str(p),"--schema","handoff"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"render",str(p),"--schema","handoff"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr); self.assertIn("Project Handoff",cp.stdout)

    def test_compaction_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); d=root/".governance/execution"; d.mkdir(parents=True)
            payload={"updated_at":"2026-10-03T00:00:00+08:00","level":"engineering","task":"x","status":"complete","actions":[],"cleanup":[],"validation":[],"findings":[],"governance_feedback":[],"retain_for_audit":False,"durable_summary_recorded":True}
            p=d/"latest.json"; p.write_text(json.dumps(payload),encoding="utf-8")
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"compact",str(root)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0); self.assertTrue(p.exists())
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"compact",str(root),"--apply"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0); self.assertFalse(p.exists())

    def test_feedback_compaction_keeps_only_open(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); d=root/".governance/feedback"; d.mkdir(parents=True)
            data={"updated_at":"2026-10-03T00:00:00+08:00","items":[{"id":"a","status":"resolved","observation":"x","evidence":[],"consequence":"x","scope":"skill"},{"id":"b","status":"open","observation":"y","evidence":["z"],"consequence":"y","scope":"project"}]}
            p=d/"open.json"; p.write_text(json.dumps(data),encoding="utf-8")
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"compact",str(root),"--apply"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            left=json.loads(p.read_text(encoding="utf-8"))["items"]; self.assertEqual([x["id"] for x in left],["b"])

    def test_evidence_export_excludes_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); g=root/".governance"; g.mkdir()
            (g/"handoff.json").write_text(json.dumps({"x":1}),encoding="utf-8")
            (root/"secret.txt").write_text("never export",encoding="utf-8")
            out=root/"bundle.json"
            cp=subprocess.run([PY,str(RUNTIME/"scripts/state_tool.py"),"export",str(root),"--output",str(out)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            text=out.read_text(encoding="utf-8"); self.assertIn("handoff.json",text); self.assertNotIn("never export",text)

    def test_linter_detects_cycle(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=pathlib.Path(td)
            shutil.copytree(ROOT/"governance-src",tmp/"governance-src")
            model_path=tmp/"governance-src/model/governance-model.json"
            model=json.loads(model_path.read_text(encoding="utf-8"))
            by={p["id"]:p for p in model["policies"]}
            by["CLEANUP_OBSOLETE"]["requires"]=["EVIDENCE_AFFECTED"]
            by["EVIDENCE_AFFECTED"]["requires"]=["CLEANUP_OBSOLETE"]
            model_path.write_text(json.dumps(model),encoding="utf-8")
            cp=subprocess.run([PY,str(ROOT/"tools/governance_lint.py"),str(tmp)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            self.assertNotEqual(cp.returncode,0); self.assertIn("G007",cp.stderr)

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as td:
            a=pathlib.Path(td)/"a"; b=pathlib.Path(td)/"b"
            cp1=run("tools/package_release.py","universal-project-governance","--output-dir",a)
            cp2=run("tools/package_release.py","universal-project-governance","--output-dir",b)
            self.assertEqual(cp1.returncode,0,cp1.stdout+cp1.stderr); self.assertEqual(cp2.returncode,0,cp2.stdout+cp2.stderr)
            import hashlib
            z1=next(a.glob("*.zip")); z2=next(b.glob("*.zip"))
            self.assertEqual(hashlib.sha256(z1.read_bytes()).hexdigest(),hashlib.sha256(z2.read_bytes()).hexdigest())

if __name__=="__main__":
    unittest.main()
