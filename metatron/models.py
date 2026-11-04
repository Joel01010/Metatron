from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    role: str
    runtime: str
    preferred_devices: tuple[str, ...]
    estimated_ram_mib: int
    resident_default: bool = False
    priority: int = 50
    idle_unload_s: float | None = None
    exclusive_group: str | None = None
    notes: str = ""


DEFAULT_MODELS = (
    ModelSpec(
        id="parakeet-unified-en-0.6b",
        role="stt",
        runtime="openvino",
        preferred_devices=("NPU", "GPU", "CPU"),
        estimated_ram_mib=1050,
        resident_default=True,
        priority=100,
        idle_unload_s=None,
        exclusive_group="voice-stt",
        notes="Production English STT baseline. Reservation is intentionally conservative until Windows RSS is measured.",
    ),
    ModelSpec(
        id="orukeet-int8",
        role="stt-experimental",
        runtime="openvino",
        preferred_devices=("NPU", "GPU", "CPU"),
        estimated_ram_mib=900,
        resident_default=False,
        priority=95,
        idle_unload_s=90,
        exclusive_group="voice-stt",
        notes="Experimental English NPU challenger; never load alongside Parakeet in strict mode.",
    ),
    ModelSpec(
        id="s1-mini-by-superwhisper",
        role="cleanup",
        runtime="openvino-or-gguf",
        preferred_devices=("NPU", "GPU", "CPU"),
        estimated_ram_mib=560,
        resident_default=False,
        priority=70,
        idle_unload_s=45,
        exclusive_group="cleanup",
        notes="English-only transcript cleanup; lazy-load and unload quickly after use.",
    ),
    ModelSpec(
        id="kokoro-82m-tts",
        role="tts-premium",
        runtime="kokoro-onnx-worker",
        preferred_devices=("CPU", "GPU"),
        estimated_ram_mib=360,
        resident_default=False,
        priority=75,
        idle_unload_s=45,
        exclusive_group="voice-tts",
        notes="Premium local male TTS. FP16 is the preferred quality/memory balance; lazy worker unloads after speech idle.",
    ),
    ModelSpec(
        id="piper-en-tts",
        role="tts-light",
        runtime="piper-cli",
        preferred_devices=("CPU",),
        estimated_ram_mib=150,
        resident_default=False,
        priority=72,
        idle_unload_s=15,
        exclusive_group="voice-tts",
        notes="Low-memory local TTS fallback; one-shot process releases RAM after synthesis.",
    ),
    ModelSpec(
        id="windows-sapi-tts",
        role="tts-system",
        runtime="windows-sapi",
        preferred_devices=("CPU",),
        estimated_ram_mib=90,
        resident_default=False,
        priority=71,
        idle_unload_s=5,
        exclusive_group="voice-tts",
        notes="Zero-download emergency fallback on Windows; male installed voice preferred.",
    ),
    ModelSpec(
        id="ternary-bonsai-2-9b",
        role="assistant",
        runtime="prism-llama.cpp",
        preferred_devices=("GPU",),
        estimated_ram_mib=3200,
        resident_default=False,
        priority=10,
        idle_unload_s=30,
        exclusive_group="large-assistant",
        notes="Deliberately inadmissible under strict/voice/agent profiles; use cloud or a raised-budget override.",
    ),
)


def model_catalog() -> list[dict]:
    return [asdict(x) for x in DEFAULT_MODELS]
