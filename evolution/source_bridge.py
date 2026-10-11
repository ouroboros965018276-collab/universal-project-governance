"""Atomic, hash-bound edits from SkillOpt to canonical governance source.

Only existing policy prose is exposed. Structural governance (including the
hot path, dependency closure, triggers, and thresholds) has no editable view.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


class SourceBridgeError(ValueError):
    """A patch cannot be applied completely and safely to its source."""


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SourceBridge:
    """An immutable source snapshot with an allowlisted policy text view.

    ``update_target`` identifies ``policies/<unique ID>/<field>``;
    ``update_origin`` binds that edit to the original field's SHA-256.
    ``ranking_details.source_hash`` binds the entire patch to this model.
    These are existing SkillOpt type fields, rather than a second patch type.
    """

    EDITABLE_FIELDS = frozenset({"statement", "closure"})
    _OPS = frozenset({"append", "insert_after", "replace", "delete"})
    _EDIT_KEYS = frozenset({"op", "content", "target", "support_count", "source_type",
                            "merge_level", "update_origin", "update_target"})

    def __init__(self, model: dict):
        if not isinstance(model, dict):
            raise SourceBridgeError("model must be an object")
        try:
            self._model = copy.deepcopy(model)
            self.source_hash = _hash(self._model)
        except (TypeError, ValueError) as exc:
            raise SourceBridgeError("model must be finite JSON") from exc
        self._fields: dict[str, tuple[int, str, str]] = {}
        policies = self._model.get("policies", [])
        if not isinstance(policies, list):
            raise SourceBridgeError("policies must be a list")
        ids: set[str] = set()
        for index, policy in enumerate(policies):
            if not isinstance(policy, dict):
                raise SourceBridgeError("policy must be an object")
            policy_id = policy.get("id")
            if not isinstance(policy_id, str) or not policy_id or "/" in policy_id or policy_id in ids:
                raise SourceBridgeError("policy IDs must be nonempty, unique, and contain no slash")
            ids.add(policy_id)
            for field in sorted(self.EDITABLE_FIELDS):
                text = policy.get(field)
                if isinstance(text, str) and text.strip():
                    self._fields[f"policies/{policy_id}/{field}"] = (index, field, text)

    @property
    def model(self) -> dict:
        return copy.deepcopy(self._model)

    def export_view(self) -> str:
        """Return prose with explicit rule IDs, field paths, and original hashes."""
        lines = ["# UPG editable policy text", f"Source SHA-256: {self.source_hash}",
                 "Only the existing statement and closure fields below are editable.",
                 "Set update_target to the exact field path and update_origin to its SHA-256.",
                 "Never change a header, rule ID, structural property, or an unexposed field."]
        for path, (_, _, text) in self._fields.items():
            lines.extend(["", f"## {path} sha256={_text_hash(text)}", text])
        return "\n".join(lines) + "\n"

    def _patch_dict(self, patch: Any) -> dict:
        raw = patch.to_dict() if hasattr(patch, "to_dict") else patch
        if not isinstance(raw, dict) or set(raw) - {"edits", "reasoning", "ranking_details"}:
            raise SourceBridgeError("unexpected patch fields")
        if not isinstance(raw.get("edits"), list):
            raise SourceBridgeError("patch edits must be a list")
        result = copy.deepcopy(raw)
        for edit in result["edits"]:
            if not isinstance(edit, dict) or set(edit) - self._EDIT_KEYS:
                raise SourceBridgeError("unexpected edit fields")
            if edit.get("op") not in self._OPS:
                raise SourceBridgeError("unsupported edit operation")
            if not isinstance(edit.get("target", ""), str) or not isinstance(edit.get("content", ""), str):
                raise SourceBridgeError("target and content must be strings")
            if not isinstance(edit.get("update_target", ""), str) or not isinstance(edit.get("update_origin", ""), str):
                raise SourceBridgeError("edit field and original hash must be strings")
        return result

    def bind_patch(self, patch: Any):
        """Resolve unbound upstream text edits, rejecting ambiguous field targets.

        Already supplied bindings must match; this method never repairs stale
        hashes. Append requires an explicit field path because it has no anchor.
        """
        from .skillopt_adapter import Patch

        raw = self._patch_dict(patch)
        details = raw.get("ranking_details") or {}
        if not isinstance(details, dict):
            raise SourceBridgeError("ranking_details must be an object")
        if details.get("source_hash", self.source_hash) != self.source_hash:
            raise SourceBridgeError("patch source hash mismatch")
        for edit in raw["edits"]:
            path = edit.get("update_target", "")
            if not path:
                target = edit.get("target", "")
                matches = [key for key, (_, _, text) in self._fields.items() if target and target in text]
                if len(matches) != 1:
                    raise SourceBridgeError("edit target does not resolve to one policy field")
                path = matches[0]
            if path not in self._fields:
                raise SourceBridgeError("edit field is not exposed")
            original = self._fields[path][2]
            original_hash = _text_hash(original)
            if edit.get("update_origin", original_hash) != original_hash:
                raise SourceBridgeError("edit original hash mismatch")
            edit["update_target"] = path
            edit["update_origin"] = original_hash
        details["source_hash"] = self.source_hash
        raw["ranking_details"] = details
        bound = Patch.from_dict(raw)
        self.apply(bound)
        return bound

    def apply(self, patch: Any) -> dict:
        """Apply every bound edit to a private copy or reject the entire patch."""
        from .skillopt_adapter import _upstream

        raw = self._patch_dict(patch)
        details = raw.get("ranking_details")
        if not isinstance(details, dict) or details.get("source_hash") != self.source_hash:
            raise SourceBridgeError("patch source hash is required and must match")
        result = copy.deepcopy(self._model)
        for edit in raw["edits"]:
            path = edit.get("update_target")
            if path not in self._fields:
                raise SourceBridgeError("edit field is not exposed")
            index, field, original = self._fields[path]
            if edit.get("update_origin") != _text_hash(original):
                raise SourceBridgeError("edit original hash is required and must match")
            current = result["policies"][index][field]
            target = edit.get("target", "")
            op = edit["op"]
            if op != "append" and (not target or current.count(target) != 1):
                raise SourceBridgeError("edit anchor must occur exactly once")
            if op == "append" and target:
                raise SourceBridgeError("append must not carry an anchor")
            content = edit.get("content", "")
            if any(marker in content for marker in ("<!-- SLOW_UPDATE", "<!-- APPENDIX")):
                raise SourceBridgeError("protected optimizer markers are not policy prose")
            updated, reports = _upstream("optimizer.skill").apply_patch_with_report(current, {"edits": [edit]})
            if len(reports) != 1 or not reports[0]["status"].startswith("applied_"):
                raise SourceBridgeError("upstream did not apply edit")
            if not updated.strip():
                raise SourceBridgeError("policy prose must remain nonempty")
            result["policies"][index][field] = updated
        # Only explicitly indexed scalar strings were changed. No patch path
        # is ever interpreted as a generic JSON pointer or executable command.
        return result
