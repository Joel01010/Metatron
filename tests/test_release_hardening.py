from pathlib import Path
import json
import pytest

from metatron.agents.hermes import EzerHTTPAdapter
from metatron.settings import SettingsStore
from metatron.db import Database


def test_managed_eop_launch_requires_loopback(tmp_path):
    a = EzerHTTPAdapter(
        id='eop', label='EOP', kind='eop', base_url='http://192.168.1.50:9200',
        start_command='python -c "print(1)"', cwd=str(tmp_path),
    )
    with pytest.raises(RuntimeError, match='loopback'):
        a._launch_local()


def test_ui_exposes_speech_voice_and_orb_customization_controls():
    js = Path('ui/app.js').read_text(encoding='utf-8')
    for token in [
        'set-speech-model', 'set-speech-hotkey', 'set-speech-injection',
        'set-tts-echo', 'set-tts-barge', 'set-plasma', 'set-particles',
        'presence.customization', 'Experimental integrations',
    ]:
        assert token in js


def test_csp_is_not_disabled_and_capabilities_are_window_scoped():
    cfg = json.loads(Path('src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
    csp = cfg['app']['security']['csp']
    assert csp and "default-src 'self'" in csp
    caps = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in Path('src-tauri/capabilities').glob('*.json')}
    assert caps['orb']['windows'] == ['orb']
    assert caps['main']['windows'] == ['main']


def test_settings_round_trip_speech_and_presence(tmp_path):
    db = Database(tmp_path / 'settings.sqlite3')
    try:
        store = SettingsStore(db)
        speech = store.set('speech', {
            'enabled': True, 'auto_start': False, 'model': 'parakeet-x',
            'hotkey': 'f8', 'mode': 'hold', 'injection_method': 'paste',
            'cleanup_enabled': True,
        })
        presence = store.set('presence', {
            **store.get('presence'), 'plasma': 1.1, 'particles': 1.2,
            'interaction_gain': 1.4,
        })
        assert speech['model'] == 'parakeet-x'
        assert presence['plasma'] == 1.1
        assert presence['particles'] == 1.2
        assert presence['interaction_gain'] == 1.4
    finally:
        db.close()
