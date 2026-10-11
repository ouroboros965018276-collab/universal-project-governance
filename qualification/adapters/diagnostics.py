"""Shared public-diagnostic redaction for qualification adapters."""
import re


_PATTERNS = (
    (r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@", r"\1[REDACTED]@"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}={0,2}", "Bearer [REDACTED]"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED_TOKEN]"),
    (r"(?i)\bAKIA[0-9A-Z]{16}\b", "[REDACTED_TOKEN]"),
    (r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*[^,;\s]{6,}", "[REDACTED_SECRET]"),
    (r"(?:(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|/(?:Users|home|private|tmp|var/tmp)/)[^\r\n\"<>|]*", "[REDACTED_PATH]"),
)


def redact_text(value):
    if not isinstance(value, str):
        return value
    for pattern, replacement in _PATTERNS:
        value = re.sub(pattern, replacement, value)
    return value


def redact_public(value):
    if isinstance(value, dict):
        return {key: redact_public(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_public(item) for item in value]
    return redact_text(value)
