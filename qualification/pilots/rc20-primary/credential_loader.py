"""Local RC20 credentials: current Windows user DPAPI, never repository plaintext.

Provision accepts one JSON line only on stdin. No API credentials in arguments,
environment, stdout, metadata, or exception text. This file is ignored tooling.
"""
from __future__ import annotations
import base64
import ctypes
from ctypes import wintypes
import datetime as dt
import json
from pathlib import Path
import re
import sys
import urllib.request
import urllib.error

VAULT = Path(r"C:\Users\96501\.agent-environment\credentials\upg-rc20-providers.dpapi.json")
BASES = {"deepseek": "https://api.deepseek.com", "mimo": "https://api.xiaomimimo.com/v1"}

class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

def crypt(raw, decrypt=False):
    buf = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        ok = api.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = api.CryptProtectData(ctypes.byref(source), "UPG RC20 provider experiment", None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise RuntimeError("current-user credential encryption failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)

def load_key(provider):
    if provider not in BASES:
        raise ValueError("unregistered provider")
    data = json.loads(VAULT.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("protection") != "Windows-DPAPI-CurrentUser":
        raise ValueError("invalid credential store")
    return crypt(base64.b64decode(data["encrypted"][provider], validate=True), True).decode("ascii")

def provision():
    if VAULT.exists():
        raise RuntimeError("credential store exists; no overwrite")
    incoming = json.loads(sys.stdin.readline(4096))
    if set(incoming) != set(BASES) or any(not isinstance(v, str) or not re.fullmatch(r"sk-[A-Za-z0-9]{20,128}", v) for v in incoming.values()):
        raise ValueError("invalid credential input")
    encrypted = {name: base64.b64encode(crypt(value.encode("ascii"))).decode("ascii") for name, value in incoming.items()}
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": 1, "protection": "Windows-DPAPI-CurrentUser", "purpose": "UPG RC20 authorized provider experiments", "created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "encrypted": encrypted}
    with VAULT.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True)
    assert all(load_key(name) == value for name, value in incoming.items())
    print(json.dumps({"stored": sorted(encrypted), "protection": payload["protection"], "readback": "passed", "plaintext_files": 0}))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("redirect refused")

def discover(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(NoRedirect())
    results = []
    for provider, base in BASES.items():
        destination = out / (provider + "-models.json")
        if destination.exists():
            raise RuntimeError("discovery receipt exists; no overwrite")
        start = dt.datetime.now(dt.timezone.utc).isoformat()
        key = load_key(provider)
        request = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576 or key.encode() in raw:
                    raise RuntimeError("unsafe discovery response")
                body = json.loads(raw)
                record = {"provider": provider, "endpoint": base + "/models", "started_at": start, "http_status": response.status, "body": body, "inference_dispatches": 0}
        except urllib.error.HTTPError as exc:
            record = {"provider": provider, "endpoint": base + "/models", "started_at": start, "http_status": exc.code, "failure": "official-endpoint-http-error", "inference_dispatches": 0}
        except Exception as exc:
            record = {"provider": provider, "endpoint": base + "/models", "started_at": start, "failure": type(exc).__name__, "inference_dispatches": 0}
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=2)
        results.append({"provider": provider, "status": record.get("http_status"), "models": [row["id"] for row in record.get("body", {}).get("data", []) if isinstance(row, dict) and isinstance(row.get("id"), str)], "failure": record.get("failure"), "inference_dispatches": 0})
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["provision"]:
            provision()
        elif len(sys.argv) == 3 and sys.argv[1] == "discover":
            discover(sys.argv[2])
        else:
            raise ValueError("unsupported local credential operation")
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "operation": "failed", "credential_text": "suppressed"}))
        sys.exit(1)
