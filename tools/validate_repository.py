#!/usr/bin/env python3
"""Validate current RC9 canonical source, generated runtime, test freeze, deployment, and release surfaces."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKILL = "universal-project-governance"

def run(cmd, root):
    cp = subprocess.run(
        cmd, cwd=str(root), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    return cp.returncode, cp.stdout + cp.stderr

def skill_version(path):
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^\s{2}version:\s*["\']?([^"\'\n]+)', text, re.M)
    return match.group(1).strip() if match else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors = []

    required = [
        "README.md", "CHANGELOG.md", "PUBLISHING.md", "PROJECT_STATE.md",
        "MODULE_MAP.md", "DECISIONS.md", "AGENTS.md", "SECURITY.md",
        "audits/rc9-readiness.audit.json",
        "governance-src/model/governance-model.json",
        "governance-src/schemas/field-report.schema.json",
        "governance-src/runtime-scripts/project_tool.py",
        "compiler/compile_governance.py",
        "qualification/protocol/qualification-v3.json",
        "qualification/FREEZE.json",
        "tools/governance_lint.py", "tools/validate_qualification.py",
        "upg.py", SKILL + "/SKILL.md",
    ]
    for rel in required:
        if not (root / rel).exists():
            errors.append("missing repository surface: " + rel)

    try:
        model = json.loads((root / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))
        version = model["version"]
    except Exception as exc:
        print("error: invalid canonical model: %s" % exc, file=sys.stderr)
        return 1

    runtime_version = skill_version(root / SKILL / "SKILL.md")
    if runtime_version != version:
        errors.append("canonical/runtime version mismatch: %r != %r" % (version, runtime_version))

    try:
        index = json.loads((root / SKILL / "policy-index.json").read_text(encoding="utf-8"))
        if index.get("version") != version:
            errors.append("policy-index version mismatch")
        if index.get("source_sha256") is None:
            errors.append("policy-index missing source identity")
        structural = index.get("structural_integration", {})
        if structural.get("policy_id") != "STRUCTURAL_INTEGRATION":
            errors.append("compiled runtime missing structural-integration contract")
        if structural.get("scope_guard") != "task-bounded-responsible-layer":
            errors.append("compiled runtime structural integration is not task-bounded")
        binding = index.get("project_binding", {})
        if binding.get("managed_files_max") != 2:
            errors.append("compiled runtime managed project file budget mismatch")
        if binding.get("field_test_reporting") is not True:
            errors.append("compiled runtime field-test reporting not enabled")
        if binding.get("schema_version") != 2:
            errors.append("compiled runtime RC9 binding schema mismatch")
        if binding.get("adoption_mode") != "in-place":
            errors.append("compiled runtime missing in-place legacy adoption")
        if binding.get("continuity_mode") != "handoff-or-reconstruct":
            errors.append("compiled runtime missing interruption reconstruction")
        if binding.get("capability_handshake") != "observe-before-assume":
            errors.append("compiled runtime missing capability handshake")
    except Exception as exc:
        errors.append("invalid policy-index: %s" % exc)

    for rel in ["AGENTS.md", "MODULE_MAP.md", "PUBLISHING.md", "CONTRIBUTING.md"]:
        if version not in (root / rel).read_text(encoding="utf-8"):
            errors.append(rel + " current candidate mismatch")

    readme = (root / "README.md").read_text(encoding="utf-8", errors="replace")
    if version not in readme:
        errors.append("README does not mention current version")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
    if ("## " + version) not in changelog:
        errors.append("CHANGELOG latest candidate missing")

    obsolete = [
        "RC3_UPGRADE_PLAN.md",
        "audits/RC3_PRE_RELEASE_AUDIT.md",
        "audits/rc4-pre-release.audit.json",
        "audits/rc5-qualification-readiness.audit.json",
        "audits/rc6-readiness.audit.json",
        "audits/rc7-readiness.audit.json",
        "audits/rc8-readiness.audit.json",
        "qualification/protocol/qualification-v1.json",
        "qualification/protocol/qualification-v2.json",
        "tools/validate_freeze_delta.py",
        "tests/test_rc4_compiler.py",
        "tests/test_rc5_qualification.py",
        "evals/evals.json", "evals/trigger_set.json",
        "evals/rc4_plan_cases.json", "evals/governance_plan_cases.json",
    ]
    for rel in obsolete:
        if (root / rel).exists():
            errors.append("obsolete current-tree artifact remains: " + rel)

    if (root / SKILL / "references").exists() or (root / SKILL / "assets").exists():
        errors.append("legacy document/template tree remains in generated runtime")

    expected_runtime = [
        "schemas/field-report.schema.json",
        "scripts/project_tool.py",
    ]
    for rel in expected_runtime:
        if not (root / SKILL / rel).is_file():
            errors.append("compiled runtime missing RC9 surface: " + rel)

    checks = [
        ([sys.executable, "compiler/compile_governance.py", "--check"], "compiler drift"),
        ([sys.executable, "tools/governance_lint.py", "."], "governance lint"),
        ([sys.executable, "tools/validate_qualification.py", "."], "qualification contract"),
        ([sys.executable, "tools/qualification_freeze.py", ".", "--check"], "real-agent freeze"),
        ([sys.executable, "tools/validate_skill_bundle.py", SKILL], "runtime bundle"),
        ([sys.executable, SKILL + "/scripts/validate_integrity.py", SKILL], "runtime integrity"),
    ]
    for cmd, label in checks:
        code, output = run(cmd, root)
        if code != 0:
            errors.append("%s failed: %s" % (label, output.strip()))

    for error in errors:
        print("error: " + error, file=sys.stderr)
    if errors:
        return 1

    print(
        "Repository check passed: %s %s "
        "(canonical source, bounded generated runtime, project deployment, "
        "qualification v3, and real-agent test freeze synchronized)."
        % (SKILL, version)
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
