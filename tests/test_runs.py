import tempfile
import unittest
from pathlib import Path
from metatron.db import Database
from metatron.events import EventBus
from metatron.kanban import Kanban
from metatron.runs import RunStore


class RunTests(unittest.TestCase):
    def test_lease_prevents_duplicate_worker(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            task = Kanban(db, bus).create("x")
            runs = RunStore(db, bus)
            r = runs.create(task["id"])
            runs.acquire(r["id"], "worker-a", 60)
            with self.assertRaises(RuntimeError):
                runs.acquire(r["id"], "worker-b", 60)
            db.close()


if __name__ == "__main__":
    unittest.main()
