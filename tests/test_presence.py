import tempfile
import unittest
from pathlib import Path

from metatron.db import Database
from metatron.events import EventBus
from metatron.presence import PresenceController


class PresenceTests(unittest.TestCase):
    def test_audio_levels_are_live_not_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db, live_capacity=128)
            p = PresenceController(bus)
            p.user_started()
            p.user_level(0.72)
            p.user_level(0.44)
            persisted = bus.tail(0, 50)
            topics = [x["topic"] for x in persisted]
            self.assertIn("speech.user.started", topics)
            self.assertNotIn("speech.user.level", topics)
            live = bus.live_tail(0, 50)
            live_topics = [x["topic"] for x in live]
            self.assertIn("speech.user.level", live_topics)
            self.assertIn("presence.level", live_topics)
            db.close()

    def test_user_inward_ai_outward_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            p = PresenceController(bus)
            p.user_started()
            u = p.user_level(0.5)
            self.assertEqual(u["direction"], "inward")
            p.tts_started("fake", "male", 100)
            a = p.tts_level(0.5, 10)
            self.assertEqual(a["direction"], "outward")
            self.assertEqual(p.snapshot()["state"], "speaking")
            db.close()

    def test_renderer_packet_is_compact_and_stable(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            p = PresenceController(bus)
            p.thinking_started()
            packet = p.renderer_packet()
            self.assertEqual(packet["schema"], 1)
            self.assertEqual(packet["state"], "thinking")
            self.assertEqual(packet["state_id"], 4)
            self.assertEqual(packet["quality"], "balanced")
            db.close()


if __name__ == "__main__":
    unittest.main()
