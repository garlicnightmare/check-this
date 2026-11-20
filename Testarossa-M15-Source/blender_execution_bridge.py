#!/usr/bin/env python3
"""Authenticated, typed-plan-only Windows Blender execution bridge."""
from __future__ import annotations
import hashlib, hmac, json, os, re, secrets, subprocess, tempfile, threading, time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BIND_HOST = "172.30.50.1"
BIND_PORT = 8768
ALLOWED_CLIENT = "172.30.50.10"
MAX_BODY = 80 * 1024
MAX_CLOCK_SKEW = 60
NONCE_TTL = 120
MAX_NONCES = 10000
EXECUTION_TIMEOUT = 180
HEX_NONCE = re.compile(r"^[0-9a-f]{32,128}$")
HEX_KEY = re.compile(r"^[0-9a-f]{64}$")

ROOT = Path(r"C:\AI\JARVIS\Testarossa")
PROJECTS = ROOT / "Projects"
RUNTIME = ROOT / "Runtime"
KEY_PATH = Path(r"C:\AI\JARVIS\ComputerAwareness\blender-execution.key")
BLENDER_EXE = Path(r"D:\blender\blender.exe")
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "blender_executor.py"
ENABLE_FLAG = ROOT / "execution.enabled"

class BridgeError(Exception):
    pass


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON number: {value}")


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def strict_json_loads(raw: bytes):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_reject_constant)


class BridgeCore:
    def __init__(self, key: bytes, protocol_module, blender_exe=BLENDER_EXE,
                 runner=RUNNER, projects=PROJECTS, runtime=RUNTIME,
                 allowed_client=ALLOWED_CLIENT, clock=time.time, enabled_flag=ENABLE_FLAG):
        if len(key) != 32:
            raise ValueError("HMAC key must be exactly 32 bytes")
        self.key = key
        self.protocol = protocol_module
        self.blender_exe = Path(blender_exe)
        self.runner = Path(runner)
        self.projects = Path(projects)
        self.runtime = Path(runtime)
        self.allowed_client = allowed_client
        self.enabled_flag = Path(enabled_flag)
        self.clock = clock
        self._nonce_lock = threading.Lock()
        self._nonces = OrderedDict()
        self._execution_lock = threading.Lock()

    def authenticate(self, body: bytes, headers: dict, remote_ip: str):
        if remote_ip != self.allowed_client:
            raise BridgeError("client_not_allowed")
        timestamp = headers.get("X-Jarvis-Timestamp", "")
        nonce = headers.get("X-Jarvis-Nonce", "")
        signature = headers.get("X-Jarvis-Signature", "")
        if not timestamp.isdigit() or not HEX_NONCE.fullmatch(nonce):
            raise BridgeError("invalid_auth_headers")
        if abs(self.clock() - int(timestamp)) > MAX_CLOCK_SKEW:
            raise BridgeError("timestamp_out_of_range")
        if not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise BridgeError("invalid_signature_format")
        signed = timestamp.encode() + b"\n" + nonce.encode() + b"\n" + body
        expected = hmac.new(self.key, signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise BridgeError("authentication_failed")
        now = self.clock()
        with self._nonce_lock:
            expired = [n for n, expiry in self._nonces.items() if expiry < now]
            for n in expired:
                self._nonces.pop(n, None)
            if nonce in self._nonces:
                raise BridgeError("replay_detected")
            self._nonces[nonce] = now + NONCE_TTL
            while len(self._nonces) > MAX_NONCES:
                self._nonces.popitem(last=False)

    def handle(self, body: bytes, headers: dict, remote_ip: str):
        if len(body) > MAX_BODY:
            raise BridgeError("request_too_large")
        self.authenticate(body, headers, remote_ip)
        if not self.enabled_flag.is_file():
            raise BridgeError("execution_disabled_until_approval_workflow_is_installed")
        payload = strict_json_loads(body)
        if not isinstance(payload, dict) or set(payload) != {"plan"}:
            raise BridgeError("request_schema_invalid")
        plan = payload["plan"]
        if not isinstance(plan, dict):
            raise BridgeError("plan_must_be_object")
        try:
            self.protocol.validate_plan(plan)
            preview = self.protocol.summarize_plan(plan)
        except (ValueError, TypeError, KeyError) as exc:
            raise BridgeError(f"plan_rejected: {exc}") from exc
        if not self._execution_lock.acquire(blocking=False):
            raise BridgeError("execution_busy")
        try:
            return self._execute(plan, preview)
        finally:
            self._execution_lock.release()

    def _execute(self, plan: dict, preview):
        slug = plan["project_slug"]
        # slug is validated by the shared protocol; still enforce path-safe form locally.
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", slug):
            raise BridgeError("project_slug_rejected")
        project_dir = self.projects / slug
        project_path = project_dir / f"{slug}.blend"
        # This bridge is create-new-only. Never silently overwrite an existing
        # project or follow a project-directory symlink.
        if project_dir.is_symlink():
            raise BridgeError("project_directory_symlink_rejected")
        if project_path.exists() or project_path.is_symlink():
            raise BridgeError("project_already_exists_choose_a_new_slug")
        if not self.blender_exe.is_file() or not self.runner.is_file():
            raise BridgeError("blender_runtime_missing")
        self.projects.mkdir(parents=True, exist_ok=True)
        project_dir.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="exec-", dir=str(self.runtime)) as td:
            work = Path(td)
            plan_path = work / "plan.json"
            result_path = work / "result.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            cmd = [str(self.blender_exe), "--background", "--factory-startup",
                   "--python-exit-code", "17", "--python", str(self.runner), "--",
                   str(plan_path), str(result_path), str(project_path)]
            try:
                completed = subprocess.run(cmd, capture_output=True, text=True,
                                           timeout=EXECUTION_TIMEOUT, check=False,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired as exc:
                raise BridgeError("blender_execution_timeout") from exc
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "")[-3000:]
                raise BridgeError(f"blender_execution_failed: {tail}")
            if not result_path.is_file() or not project_path.is_file():
                raise BridgeError("execution_result_missing")
            try:
                result = strict_json_loads(result_path.read_bytes())
            except Exception as exc:
                raise BridgeError("execution_result_invalid") from exc
        return {"ok": True, "operation": "execute_plan", "project_slug": slug,
                "project_path": str(project_path), "preview": str(preview),
                "result": result}


def load_key(path=KEY_PATH):
    raw = Path(path).read_text(encoding="ascii").strip()
    if not HEX_KEY.fullmatch(raw):
        raise RuntimeError("Execution key file must contain exactly 64 lowercase hex characters")
    return bytes.fromhex(raw)


def make_handler(core: BridgeCore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "JARVIS-Blender-Bridge/1.0"
        sys_version = ""
        def log_message(self, fmt, *args):
            # No request bodies, signatures, keys, or plan contents in logs.
            print("[bridge] " + (fmt % args), flush=True)
        def _send(self, code, obj):
            data = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path != "/health" or self.client_address[0] not in ("127.0.0.1", BIND_HOST):
                self._send(404, {"ok": False, "error": "not_found"}); return
            self._send(200, {"ok": True, "service": "jarvis-blender-execution", "port": BIND_PORT})
        def do_POST(self):
            if self.path != "/v1/execute":
                self._send(404, {"ok": False, "error": "not_found"}); return
            try:
                length = self.headers.get("Content-Length", "")
                if not length.isdigit() or int(length) < 1 or int(length) > MAX_BODY:
                    raise BridgeError("invalid_content_length")
                body = self.rfile.read(int(length))
                if len(body) != int(length):
                    raise BridgeError("truncated_body")
                headers = {k: self.headers.get(k, "") for k in
                           ("X-Jarvis-Timestamp", "X-Jarvis-Nonce", "X-Jarvis-Signature")}
                result = core.handle(body, headers, self.client_address[0])
                self._send(200, result)
            except BridgeError as exc:
                self._send(400, {"ok": False, "error": str(exc)[:512]})
            except Exception:
                self._send(500, {"ok": False, "error": "internal_error"})
    return Handler


def main():
    import blender_protocol
    ROOT.mkdir(parents=True, exist_ok=True)
    log = open(ROOT / "bridge.log", "a", encoding="utf-8", buffering=1)
    import sys
    sys.stdout = log
    sys.stderr = log
    key = load_key()
    core = BridgeCore(key, blender_protocol)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), make_handler(core))
    server.daemon_threads = True
    print(f"JARVIS Blender execution bridge listening on {BIND_HOST}:{BIND_PORT}", flush=True)
    server.serve_forever(poll_interval=0.5)

if __name__ == "__main__":
    main()
