import unittest
from metatron.memory import ModelBroker, Reservation, MemoryBudgetError


class MemoryTests(unittest.TestCase):
    def test_evicts_low_priority_lru(self):
        b = ModelBroker(1000, fixed_mib=100, headroom_mib=100)
        b.register(Reservation("low", 500, True, priority=10))
        b.register(Reservation("high", 500, True, priority=90))
        b.load("low")
        b.load("high")
        self.assertFalse(next(x for x in b.status()["resources"] if x["name"] == "low")["loaded"])
        self.assertTrue(next(x for x in b.status()["resources"] if x["name"] == "high")["loaded"])

    def test_refuses_too_large(self):
        b = ModelBroker(1000, fixed_mib=100, headroom_mib=100)
        b.register(Reservation("big", 900, True))
        with self.assertRaises(MemoryBudgetError):
            b.load("big")

    def test_exclusive_group_replaces_peer(self):
        b = ModelBroker(2000)
        b.register(Reservation("stt-a", 500, True, exclusive_group="stt"))
        b.register(Reservation("stt-b", 500, True, exclusive_group="stt"))
        b.load("stt-a")
        b.load("stt-b")
        items = {x["name"]: x for x in b.status()["resources"]}
        self.assertFalse(items["stt-a"]["loaded"])
        self.assertTrue(items["stt-b"]["loaded"])

    def test_idle_sweep(self):
        b = ModelBroker(1000)
        b.register(Reservation("cleanup", 100, True, idle_unload_s=10))
        b.load("cleanup")
        b.touch("cleanup", now=5)
        self.assertEqual(b.sweep_idle(now=14), [])
        self.assertEqual(b.sweep_idle(now=15), ["cleanup"])

    def test_measured_charge_has_cushion(self):
        b = ModelBroker(2000)
        b.register(Reservation("m", 500))
        b.set_measured_mib("m", 600)
        item = next(x for x in b.status()["resources"] if x["name"] == "m")
        self.assertEqual(item["charge_mib"], 660)

    def test_low_priority_cannot_evict_high_priority(self):
        b = ModelBroker(1000, fixed_mib=100, headroom_mib=100)
        b.register(Reservation("stt", 700, True, priority=100))
        b.register(Reservation("ui", 200, True, priority=20))
        b.load("stt")
        with self.assertRaises(MemoryBudgetError):
            b.load("ui")
        self.assertTrue(next(x for x in b.status()["resources"] if x["name"] == "stt")["loaded"])

    def test_reconcile_real_measurement_evicts_low_priority(self):
        b = ModelBroker(1200, fixed_mib=100, headroom_mib=100)
        b.register(Reservation("stt", 500, True, priority=100))
        b.register(Reservation("cleanup", 300, True, priority=70))
        b.register(Reservation("ui", 150, True, priority=20))
        b.load("stt"); b.load("cleanup"); b.load("ui")
        b.set_measured_mib("stt", 720)
        evicted = b.reconcile()
        self.assertIn("ui", evicted)
        self.assertTrue(b.status()["within_budget"])

    def test_eviction_calls_real_unload_hook(self):
        calls = []
        b = ModelBroker(800, fixed_mib=100, headroom_mib=100)
        b.register(Reservation("agent", 400, True, priority=10, unload=lambda: calls.append("stopped")))
        b.register(Reservation("stt", 500, True, priority=100))
        b.load("agent")
        b.load("stt")
        self.assertEqual(calls, ["stopped"])
        items = {x["name"]: x for x in b.status()["resources"]}
        self.assertFalse(items["agent"]["loaded"])
        self.assertTrue(items["stt"]["loaded"])



if __name__ == "__main__":
    unittest.main()
