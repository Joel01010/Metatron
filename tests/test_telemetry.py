import os
import subprocess
import sys
import time
import unittest

from metatron.telemetry import process_rss_mib, process_tree_rss_mib, process_tree_pids


class TelemetryProcessTests(unittest.TestCase):
    def test_tree_contains_root(self):
        self.assertIn(os.getpid(), process_tree_pids(os.getpid()))
        own = process_rss_mib()
        tree = process_tree_rss_mib(os.getpid())
        self.assertIsNotNone(own)
        self.assertIsNotNone(tree)
        self.assertGreaterEqual(tree, own)

    @unittest.skipUnless(os.path.isdir('/proc'), 'process-tree allocation check uses /proc')
    def test_tree_counts_child_rss(self):
        before = process_tree_rss_mib(os.getpid()) or 0.0
        p = subprocess.Popen([
            sys.executable, '-c',
            'import time; x=bytearray(24*1024*1024); time.sleep(4)'
        ])
        try:
            deadline = time.time() + 2
            after = before
            while time.time() < deadline:
                after = process_tree_rss_mib(os.getpid()) or 0.0
                if after > before + 12:
                    break
                time.sleep(0.05)
            self.assertGreater(after, before + 12)
        finally:
            p.terminate()
            try: p.wait(timeout=1)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait(timeout=1)


if __name__ == '__main__':
    unittest.main()
