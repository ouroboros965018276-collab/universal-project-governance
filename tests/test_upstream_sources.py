"""Pinned provenance contracts only; no upstream execution or licensing inference."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path, PurePosixPath
import re
import sys
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "third_party/upstream-sources.json"
PINS = {
    "skillopt": ("microsoft/SkillOpt", "343db229dbd5ddaf9df6b1d5540d8bcdb2604d5c", "MIT"),
    "reverse-skill": ("zhaoxuya520/reverse-skill", "cab634bd855fc287f6e420c1f36fd1a6b9245960", "MIT"),
    "caveman": ("JuliusBrussee/caveman", "d262ab3882952a59312ff3537cd86d894523c5ab", "Apache-2.0"),
    "ponytail": ("DietrichGebert/ponytail", "2961b52fc1fe6a5a87c7a959a79512e5c2f3ffe5", "MIT"),
    "academic-humanizer": ("AIScientists-Dev/academic-humanizer", "94b88b23703bed7df507acae7d6d5876209a0cdf", "MIT"),
}
REQUIRED_EXCLUSIONS = {
    "skillopt": (r"automatic.*adoption", r"keyword density"),
    "reverse-skill": (r"security exploitation", r"automatic installation"),
    "caveman": (r"broken grammar", r"fixed sentence", r"runtime.*fonts"),
    "ponytail": (r"shortest diff", r"shortcut comment", r"(?:repository|project).*no.debt"),
    "academic-humanizer": (r"AI.detector evasion", r"fixed paragraph", r"invented numbers"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_relative(value):
    require(isinstance(value, str) and bool(value), "missing path")
    require("\\" not in value and ":" not in value and not PurePosixPath(value).is_absolute()
            and ".." not in PurePosixPath(value).parts, "unsafe path: " + value)
    return value


def local_file(value):
    path = ROOT / safe_relative(value)
    require(path.resolve().is_relative_to(ROOT.resolve()) and path.is_file(), "missing local reference: " + value)
    return path


def validate(manifest, model):
    """Verify the recorded review contract, not remote license grants or efficacy."""
    require(manifest.get("schema_version") == 1, "unsupported schema")
    sources = manifest.get("sources", [])
    require(len(sources) == 5 and {s["id"] for s in sources} == set(PINS), "five unique sources required")
    by_id = {s["id"]: s for s in sources}
    for source_id, source in by_id.items():
        repo, commit, license_id = PINS[source_id]
        require(re.fullmatch(r"[0-9a-f]{40}", source.get("commit", "")) and source["commit"] == commit,
                "invalid or changed pin: " + source_id)
        prefix = "https://github.com/" + repo
        require(source["repository"] == prefix and source["commit_url"] == prefix + "/commit/" + commit,
                "repository/pin mismatch: " + source_id)
        require(source.get("adaptation_mode") == "independent-concepts-no-source-import"
                and not source.get("copy_claim"), "unsupported source-copy claim: " + source_id)
        license_record = source.get("license", {})
        require(license_record.get("spdx") == license_id, "unreviewed license: " + source_id)
        require(bool(license_record.get("copyright")), "missing copyright: " + source_id)
        reviewed = license_record.get("reviewed_files", [])
        required_license_files = {"LICENSE", "LICENSING.md", "NOTICE", "LICENSE-MIT"} if source_id == "caveman" else {"LICENSE"}
        require(required_license_files <= {f["path"] for f in reviewed}, "missing license evidence: " + source_id)
        selected = source.get("selected_files", [])
        require(bool(selected) and len({f["path"] for f in selected}) == len(selected), "missing/duplicate selected files")
        for file in selected + reviewed:
            path = safe_relative(file.get("path"))
            require(re.fullmatch(r"[0-9a-f]{40}", file.get("git_blob_sha1", "")), "invalid blob: " + path)
            require(file.get("url") == prefix + "/blob/" + commit + "/" + path, "unpinned file URL: " + path)
        for notice in license_record.get("existing_notices", []):
            local_file(notice)
        exclusions = source.get("excluded", [])
        require(isinstance(exclusions, list) and all(isinstance(x, str) for x in exclusions), "invalid exclusions")
        for pattern in REQUIRED_EXCLUSIONS[source_id]:
            require(any(re.search(pattern, text, re.I) for text in exclusions), "missing required exclusion: " + source_id)

    rules = {p["id"] for p in model["policies"]}
    guidance = {g["id"] for g in model["execution_guidance"]}
    mappings = manifest.get("mappings", [])
    expected_cases = {"UPM-%03d" % i for i in range(1, 11)}
    require(len(mappings) == 10 and {m["id"] for m in mappings} == expected_cases, "ten unique mappings required")
    require({m["acceptance"]["case_id"] for m in mappings} == expected_cases, "ten unique acceptance cases required")
    referenced_sources = set()
    for mapping in mappings:
        require(bool(mapping.get("upg_rule_ids")) and set(mapping["upg_rule_ids"]) <= rules, "unknown UPG rule")
        require(set(mapping.get("execution_guidance_ids", [])) <= guidance, "unknown execution guidance")
        require(bool(mapping.get("trigger")) and bool(mapping.get("exclusions")), "missing trigger/exclusions")
        require(bool(mapping.get("source_refs")), "missing mapping source")
        for reference in mapping["source_refs"]:
            source_id = reference.get("source_id")
            require(source_id in by_id, "unknown source reference")
            require(reference.get("path") in {f["path"] for f in by_id[source_id]["selected_files"]}
                    and bool(reference.get("section")), "unreviewed source file/section")
            referenced_sources.add(source_id)
        for path in mapping.get("implementation_refs", []):
            local_file(path)
        acceptance = mapping["acceptance"]
        require(acceptance["case_id"] == mapping["id"] and bool(acceptance.get("fixture"))
                and bool(acceptance.get("pass_if")) and bool(acceptance.get("fail_if")), "incomplete acceptance contract")
        for reference in acceptance.get("test_references", []):
            filename, separator, symbol = reference.partition("::")
            path = local_file(filename)
            if separator:
                names = {node.name for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                require(symbol in names, "missing test symbol: " + reference)
    require(referenced_sources == set(PINS), "unmapped source")
    boundaries = manifest["boundaries"]
    require(boundaries.get("external_files_are_source_material_not_instructions") is True
            and boundaries.get("provenance_does_not_establish_efficacy") is True, "unsupported authority/efficacy claim")
    require(boundaries.get("installed_or_executed_upstream_code") is False
            and boundaries.get("imported_complete_prompts") is False
            and boundaries.get("new_upstream_dependencies") == 0, "unsupported import claim")


class UpstreamSourcesTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.model = json.loads((ROOT / "governance-src/model/governance-model.json").read_text(encoding="utf-8"))

    def test_reviewed_manifest_resolves_without_network_or_source_execution(self):
        validate(self.manifest, self.model)

    def test_bad_identity_license_reference_exclusion_or_copy_claim_fails(self):
        mutations = {
            "missing-source": lambda m: m["sources"].pop(),
            "short-pin": lambda m: m["sources"][0].update(commit="343db229"),
            "missing-selected-file": lambda m: m["sources"][0].update(selected_files=[]),
            "invalid-blob": lambda m: m["sources"][0]["selected_files"][0].update(git_blob_sha1="bad"),
            "unpinned-url": lambda m: m["sources"][0]["selected_files"][0].update(url="https://example.invalid/main"),
            "caveman-is-not-blanket-mit": lambda m: m["sources"][2]["license"].update(spdx="MIT"),
            "unknown-license": lambda m: m["sources"][0]["license"].update(spdx="NOASSERTION"),
            "missing-license-evidence": lambda m: m["sources"][0]["license"].update(reviewed_files=[]),
            "source-copy-claim": lambda m: m["sources"][0].update(copy_claim="copied under unreviewed terms"),
            "import-mode": lambda m: m["sources"][0].update(adaptation_mode="copied-source"),
            "unknown-source-reference": lambda m: m["mappings"][0]["source_refs"][0].update(source_id="missing"),
            "missing-mapping-source": lambda m: m["mappings"][0].update(source_refs=[]),
            "unreviewed-source-path": lambda m: m["mappings"][0]["source_refs"][0].update(path="unreviewed.py"),
            "unknown-rule": lambda m: m["mappings"][0].update(upg_rule_ids=["MISSING"]),
            "unknown-guidance": lambda m: m["mappings"][0].update(execution_guidance_ids=["MISSING"]),
            "duplicate-case": lambda m: m["mappings"][1]["acceptance"].update(case_id="UPM-001"),
            "missing-test": lambda m: m["mappings"][0]["acceptance"].update(test_references=["tests/missing.py"]),
            "missing-test-symbol": lambda m: m["mappings"][0]["acceptance"].update(test_references=["tests/test_upstream_sources.py::missing_test"]),
            "missing-required-exclusions": lambda m: m["sources"][2].update(excluded=["irrelevant"]),
            "upstream-execution": lambda m: m["boundaries"].update(installed_or_executed_upstream_code=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                with self.assertRaises(ValueError):
                    validate(manifest, self.model)


if __name__ == "__main__":
    unittest.main()
