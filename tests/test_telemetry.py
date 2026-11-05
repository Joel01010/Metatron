import os
import subprocess
import sys
import time
import unittest
from unittest import mock

from metatron import telemetry as telemetry_module
from metatron.telemetry import process_rss_mib, process_tree_charge_mib, process_tree_rss_mib, process_tree_pids


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


    def test_tree_memory_refuses_partial_coverage(self):
        with mock.patch.object(telemetry_module, 'process_tree_pids', return_value=[101,102]), \
             mock.patch.object(telemetry_module, 'process_rss_mib', side_effect=[20.0,None]):
            self.assertIsNone(telemetry_module.process_tree_rss_mib(101))

    def test_charge_prefers_private_commit(self):
        with mock.patch.object(telemetry_module, 'process_tree_private_commit_mib', return_value=120.0), \
             mock.patch.object(telemetry_module, 'process_tree_rss_mib', return_value=90.0):
            value,kind=process_tree_charge_mib(101)
            self.assertEqual(value,120.0)
            self.assertEqual(kind,'private_commit')



if __name__ == '__main__':
    unittest.main()
