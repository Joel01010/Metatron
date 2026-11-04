import tempfile
import unittest
from pathlib import Path
from metatron.db import Database
from metatron.events import EventBus
from metatron.kanban import Kanban


class KanbanTests(unittest.TestCase):
    def test_create_move_assign(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            k = Kanban(db, bus)
            db.execute("INSERT INTO agents(id,kind,label,transport,created_at,updated_at) VALUES(?,?,?,?,?,?)", ("codex","codex","Codex","local",0,0))
            t = k.create("Build telemetry", project="Metatron")
            self.assertEqual(t["status"], "backlog")
            t = k.assign(t["id"], "codex")
            self.assertEqual(t["agent_id"], "codex")
            t = k.move(t["id"], "running", actor="codex")
            self.assertEqual(t["status"], "running")
            events = db.query("SELECT topic FROM events ORDER BY seq")
            self.assertEqual([e["topic"] for e in events], ["task.created", "task.assigned", "task.moved"])
            db.close()


if __name__ == "__main__":
    unittest.main()
