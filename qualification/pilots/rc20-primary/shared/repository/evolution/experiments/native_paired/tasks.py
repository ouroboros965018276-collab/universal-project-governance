"""Eight fresh native artifact instances; no final tool fixtures are imported."""
import copy
import json

SCHEMA = {"type": "object", "additionalProperties": False, "properties": {
    "files": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    "validation": {"type": "string", "enum": ["not_run"]}}, "required": ["files", "validation"]}


def make_tasks():
    tasks = []
    contexts = {
        "json-migration": {"operation": "migration", "domains": ["config", "schema"], "risk": {"scope": 1}},
        "dependency": {"operation": "dependency", "domains": ["code", "config"], "risk": {"scope": 1}},
        "python-refactor": {"operation": "refactor", "domains": ["code"], "risk": {"scope": 1}},
        "documentation": {"operation": "docs", "domains": ["docs", "data"], "risk": {"scope": 1}}}
    for phase, number in (("cold", 731), ("repeat", 947)):
        fixtures = []
        before = {"format": 1, "package": "fixture_" + str(number), "enabled": True, "settings": {"attempts": 3}}
        after = copy.deepcopy(before); after["format"] = 2; after["settings"]["max_attempts"] = after["settings"].pop("attempts")
        fixtures.append(("json-migration", {"settings.json": json.dumps(before, indent=2) + "\n"},
                         {"settings.json": json.dumps(after, indent=2) + "\n"}, {"settings.json": "json"},
                         "Migrate settings.json format from 1 to 2, rename settings.attempts to settings.max_attempts, and preserve every other value."))
        initial = {"requirements.txt": "transport-kit==%d.1\nlogging-kit==4.2\n" % number,
                   "requirements.lock": "transport-kit==%d.1\nlogging-kit==4.2\n" % number}
        expected = {name: text.replace("transport-kit==%d.1" % number, "transport-kit==%d.2" % number) for name, text in initial.items()}
        fixtures.append(("dependency", initial, expected, {},
                         "Update only transport-kit from %d.1 to %d.2 in both supplied requirement files; preserve logging-kit and all other lines." % (number, number)))
        initial = {"unit.py": 'LABEL = "fixture_%d"\n\ndef convert(value):\n    return value * 3\n\ndef use(value):\n    return convert(value) + 1\n' % number}
        expected = {"unit.py": initial["unit.py"].replace("convert", "scale")}
        fixtures.append(("python-refactor", initial, expected, {"unit.py": "python-ast"},
                         "Rename convert to scale at its definition and internal caller. Preserve the LABEL, behavior and all other declarations; remove the old function name."))
        initial = {"README.md": "# Fixture %d\n\nRun with mode=legacy.\nKeep this note intact.\n" % number,
                   "contract.json": json.dumps({"fixture": number, "mode": "legacy", "stable": True}, indent=2) + "\n"}
        expected = {"README.md": initial["README.md"].replace("mode=legacy", "mode=current"),
                    "contract.json": json.dumps({"fixture": number, "mode": "current", "stable": True}, indent=2) + "\n"}
        fixtures.append(("documentation", initial, expected, {"contract.json": "json"},
                         "Change mode from legacy to current consistently in README.md and contract.json; preserve the title, note and unrelated contract fields."))
        for family, initial, expected, kinds, instruction in fixtures:
            tasks.append({"id": "native-rc19-%s-%s-%d" % (family, phase, number), "family": family,
                          "context_group": family, "context_phase": phase,
                          "plan_context": dict(copy.deepcopy(contexts[family]), signals=[], profiles=[],
                                               unfinished=False, explicit_audit=False, field_test_reporting=False),
                          "prompt": instruction + " Return complete final contents of every supplied file, preserve unrelated content, and return no extra files. No tests or commands can be executed in this artifact-only task: report validation as not_run. Output the requested JSON only.",
                          "payload": {"initial_files": initial}, "output_schema": copy.deepcopy(SCHEMA),
                          "artifact_checks": [{"path": name, "expected": text, "kind": kinds.get(name, "text"), "forbidden_text": []}
                                              for name, text in expected.items()]})
    return tasks
