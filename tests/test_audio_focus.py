import tempfile
import time
import unittest
from pathlib import Path

from metatron.audio_focus import AudioFocusController
from metatron.db import Database
from metatron.events import EventBus


class AudioFocusTests(unittest.TestCase):
    def test_tts_suppresses_then_releases_capture(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            focus = AudioFocusController(bus, tail_ms=30)
            st = focus.tts_started()
            self.assertTrue(st["capture_suppressed"])
            self.assertFalse(st["capture_allowed"])
            focus.tts_finished()
            time.sleep(0.08)
            st = focus.status()
            self.assertTrue(st["capture_allowed"])
            topics = [e["topic"] for e in bus.tail(0, 50)]
            self.assertIn("speech.capture.suspended", topics)
            self.assertIn("speech.capture.resumed", topics)
            focus.close(); db.close()

    def test_barge_in_immediately_restores_capture(self):
        with tempfile.TemporaryDirectory() as td:
            db = Database(Path(td) / "m.db")
            bus = EventBus(db)
            focus = AudioFocusController(bus, tail_ms=1000, barge_in=True)
            focus.tts_started()
            st = focus.user_barge_in()
            self.assertTrue(st["capture_allowed"])
            self.assertFalse(st["tts_active"])
            focus.close(); db.close()


if __name__ == "__main__":
    unittest.main()
