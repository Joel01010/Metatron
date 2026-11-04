import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from metatron.agents.hermes import HermesLocalAdapter, HermesCloudAdapter
from metatron.agents.base import AgentState


class Handler(BaseHTTPRequestHandler):
    auth = None
    submitted = None
    cancelled = None

    def log_message(self, *args):
        pass

    def _json(self, code, obj=None):
        raw = b"" if obj is None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def _protected(self):
        Handler.auth = self.headers.get("Authorization")
        if Handler.auth != "Bearer secret":
            self._json(401, {"detail": "Invalid or missing API key"})
            return False
        return True

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "components": {"router": "ok"}})
        elif self.path == "/stats":
            if self._protected(): self._json(200, {"routing": {"total_routed": 7}})
        elif self.path == "/jobs/job_123":
            if self._protected():
                self._json(200, {"id": "job_123", "state": "running", "task_type": "code_write", "progress": []})
        elif self.path.startswith("/jobs?limit="):
            if self._protected(): self._json(200, {"jobs": [], "count": 0})
        else:
            self._json(404, {})

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        body = self.rfile.read(n)
        data = json.loads(body or b"{}")
        if self.path == "/jobs":
            if not self._protected(): return
            Handler.submitted = data
            self._json(200, {"job": {"id": "job_123", "state": "queued", "task_type": data["task_type"], "progress": [], "created_at": "now"}})
        elif self.path == "/jobs/job_123/cancel":
            if not self._protected(): return
            Handler.cancelled = True
            self._json(200, {"status": "cancelled", "job_id": "job_123"})
        else:
            self._json(404, {})


class HermesHTTPTests(unittest.TestCase):
    def setUp(self):
        Handler.auth = Handler.submitted = Handler.cancelled = None
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.thread.join(timeout=1)

    def test_local_submit_status_cancel_stats(self):
        a = HermesLocalAdapter(
            id="eop", label="E.O.P. / Hermes Local", kind="hermes-local",
            base_url=self.url, api_key="secret",
        )
        self.assertEqual(a.status().state, AgentState.IDLE)
        result = a.submit({"task_type": "code_write", "prompt": "Fix it", "project_dir": "C:/repo"})
        self.assertTrue(result["accepted"])
        self.assertEqual(result["job_id"], "job_123")
        self.assertEqual(Handler.submitted["params"]["prompt"], "Fix it")
        self.assertEqual(Handler.auth, "Bearer secret")
        self.assertEqual(a.job_status()["state"], "running")
        self.assertEqual(a.stats()["routing"]["total_routed"], 7)
        self.assertEqual(a.cancel_job()["status"], "cancelled")
        self.assertTrue(Handler.cancelled)

    def test_cloud_uses_same_protocol_without_local_process(self):
        a = HermesCloudAdapter(
            id="ezra", label="Ezra / Hermes Cloud", kind="hermes-cloud",
            base_url=self.url, api_key="secret", remote=True,
        )
        self.assertTrue(a.detect()["remote"])
        self.assertEqual(a.start().state, AgentState.IDLE)
        self.assertIsNone(a.status().pid)

    def test_missing_url_is_immediate_offline(self):
        a = HermesCloudAdapter(
            id="ezra", label="Ezra", kind="hermes-cloud", base_url="", remote=True,
        )
        self.assertFalse(a.detect()["available"])
        self.assertEqual(a.status().state, AgentState.OFFLINE)


if __name__ == "__main__":
    unittest.main()
