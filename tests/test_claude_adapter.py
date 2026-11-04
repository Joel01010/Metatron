import os
import tempfile
import unittest
from pathlib import Path
from metatron.agents.claude import ClaudeCodeAdapter


class ClaudeTests(unittest.TestCase):
    def test_builds_bounded_headless_command(self):
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / ("claude.cmd" if os.name == "nt" else "claude")
            exe.write_text("", encoding="utf-8")
            if os.name != "nt": exe.chmod(0o755)
            a = ClaudeCodeAdapter(executable=str(exe))
            cmd = a.build_command({"prompt":"fix it", "max_turns":999, "session_id":"abc", "model":"sonnet"})
            self.assertIn("-p", cmd)
            self.assertIn("json", cmd)
            self.assertIn("50", cmd)
            self.assertIn("--resume", cmd)
            self.assertIn("abc", cmd)


if __name__ == "__main__": unittest.main()
