import tempfile
import unittest
from pathlib import Path
from metatron.config import AppConfig
from metatron.core import Metatron


class CoreTests(unittest.TestCase):
    def test_status(self):
        with tempfile.TemporaryDirectory() as td:
            app = Metatron(AppConfig(data_dir=Path(td)))
            status = app.status()
            self.assertEqual(status["memory"]["hard_limit_mib"], 2816)
            ids = {a["id"] for a in status["agents"]}
            self.assertTrue({"eop", "ezra", "codex", "claude-code", "opencode"}.issubset(ids))
            app.close()

    def test_profile_switch_keeps_real_eviction_hooks(self):
        with tempfile.TemporaryDirectory() as td:
            app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False))
            app.set_memory_profile("voice")
            resources = {x["name"]: x for x in app.memory.status()["resources"]}
            self.assertTrue(resources["agent:codex"]["unload_hook"])
            self.assertEqual(resources["agent:eop"]["metadata"]["role"], "local-service")
            self.assertEqual(resources["agent:codex"]["metadata"]["role"], "coding-agent")
            app.close()

    def test_strict_tts_prefers_evicting_cleanup_over_dashboard_or_orb(self):
        with tempfile.TemporaryDirectory() as td:
            app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False, tts_enabled=False))
            app.memory.load("parakeet-unified-en-0.6b")
            app.memory.load("s1-mini-by-superwhisper")
            app.memory.load("dashboard-webview")
            plan = app.memory.plan_load("kokoro-82m-tts")
            self.assertTrue(plan["allowed"])
            self.assertEqual(plan["evict"], ["s1-mini-by-superwhisper"])
            resources = {x["name"]: x for x in app.memory.status()["resources"]}
            self.assertTrue(resources["presence-orb-renderer"]["loaded"])
            app.close()

    def test_presence_quality_and_dashboard_are_budgeted(self):
        with tempfile.TemporaryDirectory() as td:
            app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False, tts_enabled=False))
            r = app.set_presence_quality("spectacle")
            orb = next(x for x in r["memory"]["resources"] if x["name"] == "presence-orb-renderer")
            self.assertEqual(orb["estimated_mib"], 280)
            app.set_dashboard_open(True)
            dash = next(x for x in app.memory.status()["resources"] if x["name"] == "dashboard-webview")
            self.assertTrue(dash["loaded"])
            app.set_dashboard_open(False)
            dash = next(x for x in app.memory.status()["resources"] if x["name"] == "dashboard-webview")
            self.assertFalse(dash["loaded"])
            app.close()

    def test_system_pressure_unloads_cleanup_and_downgrades_orb(self):
        with tempfile.TemporaryDirectory() as td:
            app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False))
            try:
                app.memory.load("s1-mini-by-superwhisper")
                app.set_presence_quality("spectacle")
                result = app.apply_system_pressure(available_mib=256)
                self.assertTrue(result["pressure"])
                self.assertIn("s1-mini-by-superwhisper", result["evicted"])
                self.assertEqual(app.presence.snapshot()["quality"], "eco")
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
