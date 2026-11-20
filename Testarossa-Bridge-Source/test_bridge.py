import hashlib, hmac, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import blender_execution_bridge as bridge

class FakeProtocol:
    def validate_plan(self, plan):
        if plan.get("schema_version") != 1 or not plan.get("steps") or plan["steps"][-1]["operation"] != "save_project":
            raise ValueError("invalid plan")
    def summarize_plan(self, plan): return "safe typed preview"

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.key = b"k" * 32
        self.clock = lambda: 1700000000
        self.enable_dir = tempfile.TemporaryDirectory()
        self.enable_flag = Path(self.enable_dir.name) / "execution.enabled"
        self.core = bridge.BridgeCore(self.key, FakeProtocol(), blender_exe="blender.exe",
            runner="runner.py", projects="projects", runtime="runtime", clock=self.clock,
            enabled_flag=self.enable_flag)
        self.plan = {"schema_version":1,"plan_id":"00000000-0000-4000-8000-000000000001",
            "project_slug":"test-project","steps":[{"step_id":"s1","operation":"save_project","args":{}}]}
    def tearDown(self): self.enable_dir.cleanup()
    def signed(self, body, nonce="a"*32, timestamp="1700000000"):
        sig = hmac.new(self.key, timestamp.encode()+b"\n"+nonce.encode()+b"\n"+body, hashlib.sha256).hexdigest()
        return {"X-Jarvis-Timestamp":timestamp,"X-Jarvis-Nonce":nonce,"X-Jarvis-Signature":sig}
    def test_auth_valid(self):
        body=b'{"plan":{}}'; self.core.authenticate(body,self.signed(body),"172.30.50.10")
    def test_wrong_ip_rejected(self):
        body=b'{}'
        with self.assertRaises(bridge.BridgeError): self.core.authenticate(body,self.signed(body),"127.0.0.1")
    def test_bad_signature_rejected(self):
        body=b'{}'; h=self.signed(body); h["X-Jarvis-Signature"]="0"*64
        with self.assertRaises(bridge.BridgeError): self.core.authenticate(body,h,"172.30.50.10")
    def test_replay_rejected(self):
        body=b'{}'; h=self.signed(body); self.core.authenticate(body,h,"172.30.50.10")
        with self.assertRaises(bridge.BridgeError): self.core.authenticate(body,h,"172.30.50.10")
    def test_old_timestamp_rejected(self):
        body=b'{}'; h=self.signed(body,timestamp="1699999800")
        with self.assertRaises(bridge.BridgeError): self.core.authenticate(body,h,"172.30.50.10")
    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError): bridge.strict_json_loads(b'{"plan":1,"plan":2}')
    def test_nan_rejected(self):
        with self.assertRaises(ValueError): bridge.strict_json_loads(b'{"x":NaN}')
    def test_bad_outer_shape_rejected(self):
        body=b'{"plan":{},"extra":1}'; h=self.signed(body)
        with self.assertRaises(bridge.BridgeError): self.core.handle(body,h,"172.30.50.10")
    def test_invalid_plan_rejected(self):
        body=json.dumps({"plan":{"schema_version":1,"steps":[]}}).encode(); h=self.signed(body)
        with self.assertRaises(bridge.BridgeError): self.core.handle(body,h,"172.30.50.10")
    def test_slug_path_traversal_rejected(self):
        self.plan["project_slug"]="../escape"
        body=json.dumps({"plan":self.plan}).encode(); h=self.signed(body)
        with self.assertRaises(bridge.BridgeError): self.core.handle(body,h,"172.30.50.10")
    def test_body_limit(self):
        with self.assertRaises(bridge.BridgeError): self.core.handle(b"x"*(bridge.MAX_BODY+1),{},"172.30.50.10")
    def test_disabled_until_approval_flag(self):
        body=json.dumps({"plan":self.plan}).encode(); h=self.signed(body)
        with self.assertRaisesRegex(bridge.BridgeError, "execution_disabled"):
            self.core.handle(body,h,"172.30.50.10")
    def test_execution_invoked_after_validation(self):
        self.enable_flag.write_text("enabled\n", encoding="ascii")
        body=json.dumps({"plan":self.plan}).encode(); h=self.signed(body)
        with patch.object(self.core,"_execute",return_value={"ok":True}) as run:
            result=self.core.handle(body,h,"172.30.50.10")
        self.assertTrue(result["ok"]); run.assert_called_once()

if __name__ == "__main__": unittest.main(verbosity=2)
