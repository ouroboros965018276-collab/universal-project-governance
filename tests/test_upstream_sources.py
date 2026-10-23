"""Pinned provenance contracts only; no upstream execution or licensing inference."""
from __future__ import annotations

import ast
import copy
import hashlib
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
    "pstack": ("cursor/plugins", "8b3326d99fd4b993cb33a24dad8af03175c642c5", "MIT"),
}
REQUIRED_EXCLUSIONS = {
    "skillopt": (r"automatic.*adoption", r"keyword density"),
    "reverse-skill": (r"security exploitation", r"automatic installation"),
    "caveman": (r"broken grammar", r"fixed sentence", r"runtime.*fonts"),
    "ponytail": (r"shortest diff", r"shortcut comment", r"(?:repository|project).*no.debt"),
    "academic-humanizer": (r"AI.detector evasion", r"fixed paragraph", r"invented numbers"),
    "pstack": (r"Cursor", r"automatic merge", r"source import", r"comment persona"),
}

# Observed pinned tree identities, independently fixed from the manifest under test.
PSTACK_INVENTORY_COUNTS = {"skills": 57, "playbooks": 23, "agents": 2, "automation_skills": 3}
PSTACK_INVENTORY_SHA256 = {
    "skills": "638e4cedf7093e920b145f2af16a8f94df06d0fdcfd72d240b02fc3321edf96d",
    "playbooks": "cd4b98bd5ffffe1675c6468a8dfe138e11ac9b3e2c65d583646c8e0985ec322f",
    "agents": "23f9a5e60c74881a89eab15706dd231a7b0c73b057d99d51edec610f98c1be42",
    "automation_skills": "cd94dedce28fb860512e3f65f917f4c4a27bea3bcfebac89eb494e98656b192b",
}
PSTACK_DISPOSITIONS = {
    "adapted-workflow", "adapted-review", "existing-policy", "conditional-specialized", "excluded-host-specific",
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
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        raise ValueError("local reference escapes repository: " + value)
    require(path.is_file(), "missing local reference: " + value)
    return path


def validate(manifest, model):
    """Verify the recorded review contract, not remote license grants or efficacy."""
    require(manifest.get("schema_version") == 1, "unsupported schema")
    sources = manifest.get("sources", [])
    require(len(sources) == 6 and {s["id"] for s in sources} == set(PINS), "six unique sources required")
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
        required_license_files = ({"LICENSE", "LICENSING.md", "NOTICE", "LICENSE-MIT"} if source_id == "caveman"
                                  else {"pstack/LICENSE"} if source_id == "pstack" else {"LICENSE"})
        require(required_license_files <= {f["path"] for f in reviewed}, "missing license evidence: " + source_id)
        selected = source.get("selected_files", [])
        require(bool(selected) and len({f["path"] for f in selected}) == len(selected), "missing/duplicate selected files")
        for file in selected + reviewed:
            path = safe_relative(file.get("path"))
            require(re.fullmatch(r"[0-9a-f]{40}", file.get("git_blob_sha1", "")), "invalid blob: " + path)
            require(file.get("url") == prefix + "/blob/" + commit + "/" + path, "unpinned file URL: " + path)
        for notice in license_record.get("existing_notices", []):
            notice_path = local_file(notice)
            if notice_path.suffix == ".json":
                record = json.loads(notice_path.read_text(encoding="utf-8"))
                if record.get("file_identity_algorithm") == "git-blob-sha1" and "files" in record:
                    require(record.get("repository") == source["repository"]
                            and record.get("commit") == commit, "notice source identity mismatch")
                    catalog = {f["path"]: f["git_blob_sha1"] for f in selected + reviewed}
                    for path, digest in record["files"].items():
                        require(catalog.get(path) == digest, "uncatalogued notice blob: " + path)
        exclusions = source.get("excluded", [])
        require(isinstance(exclusions, list) and all(isinstance(x, str) for x in exclusions), "invalid exclusions")
        for pattern in REQUIRED_EXCLUSIONS[source_id]:
            require(any(re.search(pattern, text, re.I) for text in exclusions), "missing required exclusion: " + source_id)

    rules = {p["id"] for p in model["policies"]}
    guidance = {g["id"] for g in model["execution_guidance"]}
    operational = {g["id"] for g in model.get("operational_guidance", [])}
    mappings = manifest.get("mappings", [])
    expected_cases = {"UPM-%03d" % i for i in range(1, 14)}
    require(len(mappings) == 13 and {m["id"] for m in mappings} == expected_cases, "thirteen unique mappings required")
    require({m["acceptance"]["case_id"] for m in mappings} == expected_cases, "thirteen unique acceptance cases required")
    referenced_sources = set()
    for mapping in mappings:
        require(bool(mapping.get("upg_rule_ids")) and set(mapping["upg_rule_ids"]) <= rules, "unknown UPG rule")
        require(set(mapping.get("execution_guidance_ids", [])) <= guidance, "unknown execution guidance")
        require(set(mapping.get("operational_guidance_ids", [])) <= operational, "unknown operational guidance")
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
    pstack = by_id["pstack"]
    require(pstack.get("plugin_version") == "0.15.30" and bool(pstack.get("inspection_scope")),
            "missing pstack version/inspection scope")
    inventory = pstack.get("inventory", {})
    require(set(inventory) == set(PSTACK_INVENTORY_COUNTS), "incomplete pstack inventory groups")
    inventory_paths = set()
    pstack_prefix = "https://github.com/cursor/plugins/blob/" + PINS["pstack"][1] + "/"
    for kind, count in PSTACK_INVENTORY_COUNTS.items():
        entries = inventory[kind]
        require(isinstance(entries, list) and len(entries) == count, "incomplete pstack inventory: " + kind)
        for entry in entries:
            path = safe_relative(entry.get("path"))
            require(path not in inventory_paths, "duplicate pstack inventory path: " + path)
            inventory_paths.add(path)
            require(entry.get("url") == pstack_prefix + path, "unpinned pstack inventory URL: " + path)
            require(re.fullmatch(r"[0-9a-f]{40}", entry.get("git_blob_sha1", "")), "invalid pstack inventory blob")
            require(isinstance(entry.get("bytes"), int) and entry["bytes"] > 0, "invalid pstack inventory size")
            require(entry.get("disposition") in PSTACK_DISPOSITIONS and bool(entry.get("handling")),
                    "missing pstack inventory disposition: " + path)
            require(bool(entry.get("upg_rule_ids")) and set(entry["upg_rule_ids"]) <= rules,
                    "unknown pstack inventory rule: " + path)
        observed = "\n".join("\t".join((f["path"], f["git_blob_sha1"], str(f["bytes"])))
                             for f in sorted(entries, key=lambda f: f["path"])) + "\n"
        require(hashlib.sha256(observed.encode("utf-8")).hexdigest() == PSTACK_INVENTORY_SHA256[kind],
                "changed pstack pinned inventory identity: " + kind)
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
            "missing-notice-blob": lambda m: m["sources"][1]["selected_files"].pop(),
            "mismatched-notice-blob": lambda m: m["sources"][1]["selected_files"][-1].update(git_blob_sha1="0" * 40),
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
            "unknown-operational-guidance": lambda m: m["mappings"][-1].update(operational_guidance_ids=["MISSING"]),
            "duplicate-case": lambda m: m["mappings"][1]["acceptance"].update(case_id="UPM-001"),
            "missing-test": lambda m: m["mappings"][0]["acceptance"].update(test_references=["tests/missing.py"]),
            "missing-test-symbol": lambda m: m["mappings"][0]["acceptance"].update(test_references=["tests/test_upstream_sources.py::missing_test"]),
            "missing-required-exclusions": lambda m: m["sources"][2].update(excluded=["irrelevant"]),
            "upstream-execution": lambda m: m["boundaries"].update(installed_or_executed_upstream_code=True),
            "missing-pstack-inventory": lambda m: m["sources"][-1]["inventory"]["skills"].pop(),
            "changed-pstack-inventory-blob": lambda m: m["sources"][-1]["inventory"]["skills"][0].update(git_blob_sha1="0" * 40),
            "changed-pstack-inventory-size": lambda m: m["sources"][-1]["inventory"]["playbooks"][0].update(bytes=1),
            "missing-pstack-disposition": lambda m: m["sources"][-1]["inventory"]["skills"][0].pop("disposition"),
            "unknown-pstack-disposition": lambda m: m["sources"][-1]["inventory"]["agents"][0].update(disposition="installed"),
            "missing-pstack-handling": lambda m: m["sources"][-1]["inventory"]["skills"][0].update(handling=""),
            "unknown-pstack-rule": lambda m: m["sources"][-1]["inventory"]["skills"][0].update(upg_rule_ids=["MISSING"]),
            "wrong-pstack-version": lambda m: m["sources"][-1].update(plugin_version="0.0.0"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                with self.assertRaises(ValueError):
                    validate(manifest, self.model)


if __name__ == "__main__":
    unittest.main()
