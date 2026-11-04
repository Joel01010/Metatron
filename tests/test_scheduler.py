import tempfile
import unittest
from pathlib import Path
from metatron.db import Database
from metatron.events import EventBus
from metatron.scheduler import Scheduler


class SchedulerTests(unittest.TestCase):
    def test_due_advances_without_drift(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            s = Scheduler(db, EventBus(db))
            item = s.create_interval("scan", {"title": "scan"}, 60, first_run=100)
            due = s.due(221)
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0]["missed_intervals"], 2)
            self.assertEqual(s.get(item["id"])["next_run"], 280)
            db.close()


if __name__ == "__main__":
    unittest.main()
