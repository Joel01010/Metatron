import math
import struct
import tempfile
import time
import unittest
import wave
from pathlib import Path

from metatron.db import Database
from metatron.events import EventBus
from metatron.memory import ModelBroker
from metatron.presence import PresenceController
from metatron.telemetry import Telemetry
from metatron.tts import TTSManager, TTSSettings


class FakeProvider:
    id = "fake"
    resource_name = "fake-tts"

    def available(self):
        return True

    def synthesize(self, text, output_path, voice, speed):
        rate = 8000
        duration = 0.08
        frames = int(rate * duration)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
            buf = bytearray()
            for i in range(frames):
                v = int(8000 * math.sin(2 * math.pi * 220 * i / rate))
                buf += struct.pack("<h", v)
            wf.writeframes(bytes(buf))
        return output_path

    def stop(self):
        pass


class TTSManagerTests(unittest.TestCase):
    def make(self, td):
        db = Database(Path(td) / "m.db")
        bus = EventBus(db)
        broker = ModelBroker(2048)
        presence = PresenceController(bus)
        telemetry = Telemetry(db, 1)
        tts = TTSManager(
            bus=bus, broker=broker, presence=presence, telemetry=telemetry, db=db,
            data_dir=Path(td), settings=TTSSettings(enabled=True, mode="premium", priority_threshold=3, playback=False),
            providers=[FakeProvider()],
        )
        return db, bus, tts

    def test_priority_gate(self):
        with tempfile.TemporaryDirectory() as td:
            db, bus, tts = self.make(td)
            self.assertFalse(tts.enqueue("routine", priority=2)["queued"])
            self.assertTrue(tts.enqueue("important", priority=3)["queued"])
            deadline = time.time() + 2
            while time.time() < deadline:
                if any(x["topic"] == "tts.finished" for x in bus.tail(0, 100)):
                    break
                time.sleep(0.02)
            topics = [x["topic"] for x in bus.tail(0, 100)]
            self.assertIn("tts.started", topics)
            self.assertIn("tts.finished", topics)
            live = bus.live_tail(0, 200)
            self.assertTrue(any(x["topic"] == "tts.level" for x in live))
            tts.close(); telemetry = None; db.close()

    def test_switch_off_drops_speech(self):
        with tempfile.TemporaryDirectory() as td:
            db, bus, tts = self.make(td)
            tts.set_enabled(False)
            self.assertEqual(tts.enqueue("do not speak", priority=4)["reason"], "disabled")
            tts.close(); db.close()

    def test_settings_persist(self):
        with tempfile.TemporaryDirectory() as td:
            db, bus, tts = self.make(td)
            tts.set_voice("am_michael", 0.9)
            tts.set_threshold(4)
            tts.set_enabled(False)
            tts.close()
            broker = ModelBroker(2048)
            presence = PresenceController(bus)
            telemetry = Telemetry(db, 1)
            again = TTSManager(
                bus=bus, broker=broker, presence=presence, telemetry=telemetry, db=db,
                data_dir=Path(td), settings=TTSSettings(), providers=[FakeProvider()],
            )
            st = again.status()
            self.assertEqual(st["voice"], "am_michael")
            self.assertEqual(st["priority_threshold"], 4)
            self.assertFalse(st["enabled"])
            again.close(); db.close()


if __name__ == "__main__":
    unittest.main()
