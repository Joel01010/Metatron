from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class MemoryProfile:
    name: str
    hard_limit_mib: int
    backend_target_mib: int
    ui_target_mib: int
    pet_target_mib: int
    reserve_headroom_mib: int
    max_local_agents: int
    min_system_available_mib: int
    description: str


MEMORY_PROFILES: dict[str, MemoryProfile] = {
    "strict": MemoryProfile(
        name="strict",
        hard_limit_mib=2816,
        backend_target_mib=160,
        ui_target_mib=260,
        pet_target_mib=64,
        reserve_headroom_mib=224,
        max_local_agents=1,
        min_system_available_mib=1024,
        description="Default 2-3 GiB whole-platform mode; large local assistants are refused.",
    ),
    "voice": MemoryProfile(
        name="voice",
        hard_limit_mib=2560,
        backend_target_mib=150,
        ui_target_mib=0,
        pet_target_mib=48,
        reserve_headroom_mib=224,
        max_local_agents=1,
        min_system_available_mib=1024,
        description="Dictation-first mode; dashboard should be closed and optional workers evict quickly.",
    ),
    "agent": MemoryProfile(
        name="agent",
        hard_limit_mib=3072,
        backend_target_mib=170,
        ui_target_mib=260,
        pet_target_mib=64,
        reserve_headroom_mib=192,
        max_local_agents=2,
        min_system_available_mib=768,
        description="Upper edge of the user's ceiling; permits more agent tooling, not a resident 9B model.",
    ),
}


@dataclass(slots=True)
class AppConfig:
    data_dir: Path
    memory_profile: str = "strict"
    # E.O.P./Hermes is controlled through its existing FastAPI surface rather
    # than embedding another orchestration runtime inside Metatron.  Secrets
    # come from environment variables and are never written to Metatron DB.
    eop_url: str = "http://127.0.0.1:9200"
    eop_workspace: str | None = None
    eop_start_command: str = ""
    eop_api_key: str | None = None
    ezra_host: str = ""
    ezra_url: str = ""
    ezra_api_key: str | None = None
    telemetry_interval_s: float = 10.0
    telemetry_retention_h: int = 72
    event_retention: int = 10_000
    scheduler_tick_s: float = 2.0
    enable_background_maintenance: bool = True

    # Voice output. Important system replies are spoken by default; ordinary
    # chat/agent streams stay silent unless explicitly requested.
    tts_enabled: bool = True
    tts_mode: str = "premium"  # premium | light | off
    tts_priority_threshold: int = 3
    tts_voice: str = "am_fenrir"
    tts_speed: float = 0.96
    tts_idle_unload_s: float = 45.0
    tts_playback: bool = True
    tts_echo_guard: bool = True
    tts_barge_in: bool = True
    tts_capture_tail_ms: int = 280
    kokoro_python: str = ""
    kokoro_model_path: str = ""
    kokoro_voices_path: str = ""
    piper_bin: str = ""
    piper_model_path: str = ""
    winml_python: str = ""
    speech_command: str = ""
    speech_enabled: bool = True
    speech_auto_start: bool = False
    speech_model: str = "parakeet-unified-en-0.6b"
    speech_hotkey: str = "right ctrl"
    speech_mode: str = "hold"
    speech_injection_method: str = "paste"
    s1_command: str = ""

    # Presence/orb backend state. Rendering is intentionally a separate Tauri
    # concern; the backend emits a stable high-frequency live event contract.
    presence_enabled: bool = True
    presence_quality: str = "balanced"

    @property
    def memory(self) -> MemoryProfile:
        try:
            return MEMORY_PROFILES[self.memory_profile]
        except KeyError as exc:
            raise ValueError(f"unknown memory profile {self.memory_profile!r}") from exc

    @classmethod
    def default(cls) -> "AppConfig":
        raw = os.environ.get("METATRON_DATA_DIR")
        if raw:
            data_dir = Path(raw)
        elif os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            data_dir = Path(local) / "Metatron" if local else Path.home() / "AppData" / "Local" / "Metatron"
        else:
            data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "metatron"
        profile = os.environ.get("METATRON_MEMORY_PROFILE", "strict").strip().lower() or "strict"
        if profile not in MEMORY_PROFILES:
            profile = "strict"
        return cls(
            data_dir=data_dir,
            memory_profile=profile,
            eop_url=os.environ.get("METATRON_EOP_URL", "http://127.0.0.1:9200").rstrip("/"),
            eop_workspace=os.environ.get("METATRON_EOP_WORKSPACE") or None,
            eop_start_command=os.environ.get("METATRON_EOP_START_COMMAND", ""),
            eop_api_key=(os.environ.get("METATRON_EOP_API_KEY")
                         or os.environ.get("EZEROS_API_KEY") or None),
            ezra_host=os.environ.get("METATRON_EZRA_HOST", ""),
            ezra_url=os.environ.get("METATRON_EZRA_URL", "").rstrip("/"),
            ezra_api_key=os.environ.get("METATRON_EZRA_API_KEY") or None,
            tts_enabled=os.environ.get("METATRON_TTS_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"},
            tts_mode=(os.environ.get("METATRON_TTS_MODE", "premium").strip().lower() or "premium"),
            tts_priority_threshold=max(0, min(4, int(os.environ.get("METATRON_TTS_PRIORITY", "3")))),
            tts_voice=os.environ.get("METATRON_TTS_VOICE", "am_fenrir"),
            tts_speed=float(os.environ.get("METATRON_TTS_SPEED", "0.96")),
            tts_idle_unload_s=float(os.environ.get("METATRON_TTS_IDLE_UNLOAD_S", "45")),
            tts_playback=os.environ.get("METATRON_TTS_PLAYBACK", "1").strip().lower() not in {"0", "false", "off", "no"},
            tts_echo_guard=os.environ.get("METATRON_TTS_ECHO_GUARD", "1").strip().lower() not in {"0", "false", "off", "no"},
            tts_barge_in=os.environ.get("METATRON_TTS_BARGE_IN", "1").strip().lower() not in {"0", "false", "off", "no"},
            tts_capture_tail_ms=max(0, min(2000, int(os.environ.get("METATRON_TTS_CAPTURE_TAIL_MS", "280")))),
            kokoro_python=os.environ.get("METATRON_KOKORO_PYTHON", ""),
            kokoro_model_path=os.environ.get("METATRON_KOKORO_MODEL", ""),
            kokoro_voices_path=os.environ.get("METATRON_KOKORO_VOICES", ""),
            piper_bin=os.environ.get("METATRON_PIPER_BIN", ""),
            piper_model_path=os.environ.get("METATRON_PIPER_MODEL", ""),
            winml_python=os.environ.get("METATRON_WINML_PYTHON", ""),
            speech_command=os.environ.get("METATRON_SPEECH_CMD", ""),
            speech_enabled=os.environ.get("METATRON_SPEECH_ENABLED", "1").strip().lower() not in {"0","false","off","no"},
            speech_auto_start=os.environ.get("METATRON_SPEECH_AUTO_START", "0").strip().lower() in {"1","true","on","yes"},
            speech_model=os.environ.get("METATRON_SPEECH_MODEL", "parakeet-unified-en-0.6b"),
            speech_hotkey=os.environ.get("METATRON_SPEECH_HOTKEY", "right ctrl"),
            speech_mode=os.environ.get("METATRON_SPEECH_MODE", "hold"),
            speech_injection_method=os.environ.get("METATRON_SPEECH_INJECTION", "paste"),
            s1_command=os.environ.get("METATRON_S1_CMD", ""),
            presence_enabled=os.environ.get("METATRON_PRESENCE_ENABLED", "1").strip().lower() not in {"0", "false", "off", "no"},
            presence_quality=(os.environ.get("METATRON_PRESENCE_QUALITY", "balanced").strip().lower() or "balanced"),
        )
