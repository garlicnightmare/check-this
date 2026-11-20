#!/usr/bin/env python3
"""Authenticated network smoke test; expects execution to remain disabled."""
import hashlib, hmac, json, secrets, time, urllib.error, urllib.request
KEY_PATH = "/etc/jarvis-baby/windows-blender-execution.key"
URL = "http://172.30.50.1:8768/v1/execute"
key_text = open(KEY_PATH, "r", encoding="ascii").read().strip()
if len(key_text) != 64: raise SystemExit("FAIL: key length")
key = bytes.fromhex(key_text)
body = b'{"plan":{}}'
timestamp = str(int(time.time()))
nonce = secrets.token_hex(16)
sig = hmac.new(key, timestamp.encode()+b"\n"+nonce.encode()+b"\n"+body, hashlib.sha256).hexdigest()
req = urllib.request.Request(URL, data=body, method="POST", headers={
    "Content-Type":"application/json", "X-Jarvis-Timestamp":timestamp,
    "X-Jarvis-Nonce":nonce, "X-Jarvis-Signature":sig})
try:
    with urllib.request.urlopen(req, timeout=8) as response:
        status, payload = response.status, response.read()
except urllib.error.HTTPError as exc:
    status, payload = exc.code, exc.read()
obj = json.loads(payload.decode("utf-8"))
expected = "execution_disabled_until_approval_workflow_is_installed"
if status != 400 or obj.get("error") != expected:
    raise SystemExit(f"FAIL: unexpected response status={status} body={obj}")
print("PASS: Ubuntu reached Windows bridge, HMAC authenticated, and execution remains safely disabled.")
