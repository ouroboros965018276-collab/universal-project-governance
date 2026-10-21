"""Shared public-diagnostic redaction for qualification adapters."""
import re


_PATTERNS = (
    (r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@", r"\1[REDACTED]@"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}={0,2}", "Bearer [REDACTED]"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED_TOKEN]"),
    (r"(?i)\bAKIA[0-9A-Z]{16}\b", "[REDACTED_TOKEN]"),
    (r'''(?i)(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie)["']?\s*[:=]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|(?:Basic|Bearer)\s+[^,;\s}\]]+|[^,;\s}\]]+)''', "[REDACTED_SECRET]"),
    (r"(?:(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/]|\\\\[^\\\s]+\\|/(?:Users|home|private|tmp|var/tmp)/)[^\r\n\"<>|:,;]*", "[REDACTED_PATH]"),
)

_SENSITIVE_KEY = re.compile(r"(?i)(?:^|[_-])(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie)$")

def sensitive_key(key):
    return isinstance(key,str) and _SENSITIVE_KEY.search(re.sub(r"([a-z0-9])([A-Z])",r"\1_\2",key))


def redact_text(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return value
    for pattern, replacement in _PATTERNS:
        value = re.sub(pattern, replacement, value)
    return value


def redact_public(value):
    if isinstance(value, dict):
        return {redact_text(key): "[REDACTED_SECRET]" if sensitive_key(key) else redact_public(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_public(item) for item in value]
    return redact_text(value)
