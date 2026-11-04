from __future__ import annotations
import sys
from pathlib import Path

from metatron.cleanup import CleanupManager, RuleCleaner, S1MiniWorkerProvider
from metatron.memory import ModelBroker, Reservation
from metatron.workers import JsonlWorkerSupervisor


def test_cleanup_manager_uses_disposable_worker_for_semantic_case(tmp_path: Path):
    broker=ModelBroker(1500)
    broker.register(Reservation('s1-mini-by-superwhisper',560,True,idle_unload_s=1))
    worker=JsonlWorkerSupervisor(
        's1-mini-by-superwhisper',
        [sys.executable, str(Path(__file__).resolve().parents[1]/'scripts'/'cleanup_standin_worker.py')],
        broker, request_timeout_s=3,
    )
    provider=S1MiniWorkerProvider(worker)
    mgr=CleanupManager(RuleCleaner(),provider)
    try:
        out=mgr.cleanup('um i mean send the report',context='general')
        assert out['semantic_used'] is True
        assert str(out['text']).startswith('I mean')
        assert worker.running
    finally:
        provider.stop()
    assert not worker.running


def test_cleanup_manager_keeps_model_cold_for_simple_text():
    mgr=CleanupManager(RuleCleaner(),None)
    out=mgr.cleanup('um hello comma world')
    assert out['semantic_used'] is False
    assert out['text']=='hello, world'
