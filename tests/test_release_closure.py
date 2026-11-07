from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import metatron.speech as speech

ROOT = Path(__file__).resolve().parents[1]


def _load_adapter():
    path = ROOT / "scripts" / "ezstt_metatron_sidecar.py"
    spec = importlib.util.spec_from_file_location("metatron_ezstt_adapter_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Compiled:
    def __init__(self, devices):
        self.devices = devices

    def get_property(self, name):
        assert name == "EXECUTION_DEVICES"
        return self.devices


class _Transcriber:
    def __init__(self, device, devices):
        self.device = device
        self._enc = _Compiled(devices)


def test_ezstt_adapter_requires_openvino_execution_device_proof():
    adapter = _load_adapter()
    ok = adapter._placement_payload(_Transcriber("NPU", ["NPU"]), "NPU")
    assert ok["placement_verified"] is True
    assert ok["actual_device"] == "NPU"
    assert ok["placement_evidence"] == "OpenVINO EXECUTION_DEVICES"

    mismatch = adapter._placement_payload(_Transcriber("NPU", ["NPU"]), "CPU")
    assert mismatch["placement_verified"] is False
    missing = adapter._placement_payload(_Transcriber("NPU", []), "NPU")
    assert missing["placement_verified"] is False


def test_ezstt_adapter_filters_only_metatron_owned_metadata():
    adapter = _load_adapter()
    params = {
        "device": "NPU",
        "hotkey": "right ctrl",
        "active_app": {"id": "demo"},
        "context_awareness": True,
        "unexpected": 1,
    }
    filtered = adapter._filtered_upstream_config(params, {"device", "hotkey"})
    assert filtered == {"device": "NPU", "hotkey": "right ctrl"}
    assert "active_app" in adapter.METATRON_ONLY_CONFIG_KEYS
    assert "unexpected" not in adapter.METATRON_ONLY_CONFIG_KEYS


def test_adapter_dictionary_replacement_is_bounded_and_case_insensitive():
    adapter = _load_adapter()
    compiled = adapter._compile_dictionary([
        {"term": "supabase", "replacement": "Supabase"},
        {"term": "C plus plus", "replacement": "C++"},
    ])
    text, matched = adapter._apply_dictionary("use SUPABASE with C plus plus", compiled)
    assert text == "use Supabase with C++"
    assert matched == ["C plus plus", "supabase"]


def test_adapter_dictionary_does_not_replace_inside_larger_words():
    adapter = _load_adapter()
    compiled = adapter._compile_dictionary([{"term": "art", "replacement": "ART"}])
    text, matched = adapter._apply_dictionary("art partial", compiled)
    assert text == "ART partial"
    assert matched == ["art"]


def test_speech_command_manifest_is_used_without_shell_inheritance(tmp_path, monkeypatch):
    manifest = tmp_path / "speech-command.json"
    command = [r"C:\\EZSTT\\python.exe", r"C:\\EZSTT\\metatron_sidecar.py", "--engine-root", r"C:\\EZSTT"]
    manifest.write_text(json.dumps({"schema": 1, "command": command}), encoding="utf-8")
    monkeypatch.delenv("METATRON_SPEECH_CMD", raising=False)
    monkeypatch.setattr(speech, "_speech_command_manifest_path", lambda: manifest)
    assert speech.speech_command_from_env() == command


def test_speech_environment_override_still_has_precedence(tmp_path, monkeypatch):
    manifest = tmp_path / "speech-command.json"
    manifest.write_text(json.dumps({"command": ["wrong"]}), encoding="utf-8")
    monkeypatch.setattr(speech, "_speech_command_manifest_path", lambda: manifest)
    monkeypatch.setenv("METATRON_SPEECH_CMD", 'python sidecar.py --engine-root runtime')
    assert speech.speech_command_from_env()[:2] == ["python", "sidecar.py"]


def test_release_closure_windows_contracts_are_canonicalized():
    rust = (ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    orb_probe = (ROOT / "scripts" / "Test-OrbWindow.ps1").read_text(encoding="utf-8")
    ezq = (ROOT / "scripts" / "Invoke-EZSTTQualification.ps1").read_text(encoding="utf-8")
    kokoro = (ROOT / "scripts" / "Setup-Kokoro-TTS.ps1").read_text(encoding="utf-8")
    full = (ROOT / "scripts" / "Invoke-MetatronFullValidation.ps1").read_text(encoding="utf-8")
    closure = (ROOT / "scripts" / "Invoke-MetatronReleaseClosure.ps1").read_text(encoding="utf-8")
    ui = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert "monitor.work_area()" in rust
    assert '"orb.scale"' in rust and "position_orb_on_primary(&orb)?;" in rust
    assert "deterministic_anchor=$anchored" in orb_probe
    assert "@('run','tauri','build','--','--debug','--no-bundle')" in ezq
    assert "test_focus.py" in ezq and "test_restart.py" in ezq and "test_e2e.py" in ezq
    assert "$env:METATRON_KOKORO_PYTHON" in kokoro
    assert "RequireKokoro" in full
    assert "speech-command.json" in full
    assert "SoakMinutes=60" in closure
    assert "RunEZSTTUpstream=$true" in closure
    assert "RequireSpeechRuntime=$true" in closure
    assert "RequireKokoro=$true" in closure
    setup_speech = (ROOT / "scripts" / "Setup-SpeechRuntime.ps1").read_text(encoding="utf-8")
    provision = (ROOT / "scripts" / "Provision-EZSTTModel.py").read_text(encoding="utf-8")
    metrics = (ROOT / "scripts" / "Collect-WindowsMetrics.ps1").read_text(encoding="utf-8")
    assert "Provision-EZSTTModel.py" in setup_speech
    assert "ErrorActionPreference='Continue'" in ezq or "ErrorActionPreference = 'Continue'" in ezq
    assert "parakeet-unified-en-0.6b" in provision
    assert "GetGuiResources" in metrics and "PROCESS_QUERY_INFORMATION=0x0400" in metrics
    assert "[['hold','Hold'],['toggle','Toggle']]" in ui
    assert "['always','Always']" not in ui


def test_adapter_is_single_process_and_emits_full_final_transcript_event():
    src = (ROOT / "scripts" / "ezstt_metatron_sidecar.py").read_text(encoding="utf-8")
    assert "subprocess.Popen" not in src
    assert '"event": "transcript"' in src
    assert '"text": final_text' in src
    assert '"final": True' in src
    assert 'os.environ["EZSTT_DIR"] = str(engine_root)' in src
    assert '("NPU", "CPU")' in src
    assert "_cmd_set_personalization" in src
    assert "_cmd_set_app_policy" in src
    assert "_metatron_privacy_paused" in src
    assert '"event": "active_app"' in src
