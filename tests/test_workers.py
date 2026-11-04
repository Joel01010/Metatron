import sys
import unittest
from pathlib import Path
from metatron.memory import ModelBroker, Reservation
from metatron.workers import JsonlWorkerSupervisor


class WorkerTests(unittest.TestCase):
    def test_lazy_worker_loads_and_fully_unloads(self):
        b = ModelBroker(1000)
        b.register(Reservation("cleanup", 100, True))
        script = str(Path(__file__).with_name("echo_worker.py"))
        w = JsonlWorkerSupervisor("cleanup", [sys.executable, script], b)
        self.assertFalse(w.running)
        result = w.request("ping", {"x": 1})
        self.assertEqual(result, {"x": 1})
        self.assertTrue(w.running)
        self.assertTrue(next(x for x in b.status()["resources"] if x["name"] == "cleanup")["loaded"])
        w.stop()
        self.assertFalse(w.running)
        self.assertFalse(next(x for x in b.status()["resources"] if x["name"] == "cleanup")["loaded"])


if __name__ == "__main__":
    unittest.main()
