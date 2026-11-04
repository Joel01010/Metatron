import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from metatron.agents.opencode import OpenCodeAdapter


class Handler(BaseHTTPRequestHandler):
    prompt = None
    def log_message(self, *args):
        pass
    def _json(self, code, obj=None):
        raw = b"" if obj is None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw: self.wfile.write(raw)
    def do_GET(self):
        if self.path == "/session/status": self._json(200, {})
        else: self._json(404, {})
    def do_POST(self):
        n = int(self.headers.get("content-length", 0)); body = self.rfile.read(n)
        data = json.loads(body or b"{}")
        if self.path == "/session": self._json(200, {"id": "s1"})
        elif self.path == "/session/s1/prompt_async":
            Handler.prompt = data
            self._json(204)
        elif self.path == "/session/s1/abort": self._json(200, True)
        else: self._json(404, {})


class OpenCodeTests(unittest.TestCase):
    def test_async_submit_over_http(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
        try:
            a = OpenCodeAdapter(port=srv.server_address[1])
            result = a.submit({"title": "Fix", "prompt": "Fix the test"})
            self.assertTrue(result["accepted"])
            self.assertEqual(result["session_id"], "s1")
            self.assertEqual(Handler.prompt["parts"][0]["text"], "Fix the test")
            self.assertTrue(a.abort("s1"))
        finally:
            srv.shutdown(); srv.server_close(); t.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
