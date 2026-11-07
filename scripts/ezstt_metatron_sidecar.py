#!/usr/bin/env python3
"""Metatron compatibility entrypoint for the pinned EZSTT engine.

Single-process adapter around the pinned EZSTT Python engine.  It preserves
EZSTT's protocol/runtime while adding the product contracts Metatron needs:

* truthful OpenVINO placement evidence from EXECUTION_DEVICES;
* foreground-application events for per-app policy;
* pause-before-capture privacy enforcement;
* local dictionary replacement before text injection;
* context-profile/app metadata on final transcript events.

The adapter does not spawn a second STT process and does not treat a requested
accelerator name as proof of actual placement.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any

PINNED_EZSTT_REVISION = "5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a"
METATRON_ONLY_CONFIG_KEYS = {
    "active_app",
    "privacy_runtime_supported",
    "personalization_runtime_supported",
    "context_awareness",
    "dictionary_enabled",
    "default_context_profile",
}


def _device_class(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    for kind in ("NPU", "GPU", "CPU"):
        if raw == kind or raw.startswith(kind + ".") or raw.startswith(kind + ":"):
            return kind
    return raw


def _execution_devices(transcriber: Any) -> list[str]:
    """Return execution devices from compiled OpenVINO models."""
    if transcriber is None:
        return []
    values: list[str] = []
    for name in ("_enc", "compiled_model", "_compiled_model"):
        compiled = getattr(transcriber, name, None)
        getter = getattr(compiled, "get_property", None)
        if not callable(getter):
            continue
        try:
            raw = getter("EXECUTION_DEVICES")
        except Exception:
            continue
        if isinstance(raw, str):
            raw = [raw]
        try:
            for item in raw or []:
                text = str(item).strip()
                if text and text not in values:
                    values.append(text)
        except TypeError:
            pass
    return values


def _placement_payload(transcriber: Any, requested: str) -> dict[str, Any]:
    requested_class = _device_class(requested)
    reported_class = _device_class(getattr(transcriber, "device", ""))
    execution_devices = _execution_devices(transcriber)
    execution_classes = {_device_class(x) for x in execution_devices}
    verified = bool(
        requested_class in {"NPU", "GPU", "CPU"}
        and reported_class == requested_class
        and requested_class in execution_classes
    )
    return {
        "placement_verified": verified,
        "actual_device": reported_class if verified else "",
        "provider": "OpenVINO",
        "device_name": ", ".join(execution_devices) if execution_devices else reported_class,
        "execution_devices": execution_devices,
        "placement_evidence": "OpenVINO EXECUTION_DEVICES" if execution_devices else "unavailable",
    }


def _filtered_upstream_config(params: dict[str, Any], upstream_keys: set[str]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if k in upstream_keys}


def _compile_dictionary(entries: list[dict[str, Any]]) -> list[tuple[re.Pattern[str], str, str]]:
    """Compile bounded, deterministic replacements.

    Entries are applied longest-term first.  Alphanumeric phrases use word
    boundaries so a term such as ``art`` never rewrites ``partial``.
    """
    clean: list[tuple[str, str]] = []
    for item in entries[:1000]:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        replacement = str(item.get("replacement") or term).strip()
        if not term or len(term) > 256 or len(replacement) > 512:
            continue
        clean.append((term, replacement))
    clean.sort(key=lambda x: len(x[0]), reverse=True)
    out: list[tuple[re.Pattern[str], str, str]] = []
    for term, replacement in clean:
        escaped = re.escape(term)
        if term[0].isalnum() and term[-1].isalnum():
            escaped = rf"(?<!\w){escaped}(?!\w)"
        out.append((re.compile(escaped, re.IGNORECASE), replacement, term))
    return out


def _apply_dictionary(text: str, compiled: list[tuple[re.Pattern[str], str, str]]) -> tuple[str, list[str]]:
    result = str(text)
    matched: list[str] = []
    for pattern, replacement, term in compiled:
        result, count = pattern.subn(lambda _m, r=replacement: r, result)
        if count:
            matched.append(term)
    return result, matched


def _foreground_app() -> dict[str, str]:
    """Best-effort foreground application identity without third-party deps."""
    if os.name != "nt":
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {}
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title_buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buf, len(title_buf))
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        exe = ""
        if handle:
            try:
                size = wintypes.DWORD(32768)
                buf = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    exe = Path(buf.value).name
            finally:
                kernel32.CloseHandle(handle)
        app_id = exe or f"pid:{int(pid.value)}"
        return {"app_id": app_id, "app_name": title_buf.value, "process_id": str(int(pid.value))}
    except Exception:
        return {}


def _build_server(engine_root: Path):
    engine_dir = engine_root / "engine"
    if not (engine_dir / "ezstt" / "server.py").is_file():
        raise FileNotFoundError(f"EZSTT engine not found under {engine_root}")
    sys.path.insert(0, str(engine_dir))
    # Force the pinned engine to use the intended root.  Do not inherit a stale
    # EZSTT_DIR from the shell because that can silently redirect model/config.
    os.environ["EZSTT_DIR"] = str(engine_root)

    from ezstt.config import DEFAULTS
    from ezstt.server import ProtocolError, Server
    from ezstt.app import App

    # Patch activation once at class level before Server._boot constructs App.
    # HotkeyListener therefore receives the privacy-aware callback from the
    # beginning, allowing policy to block capture before audio/transcription.
    native_on_activate = App._on_activate

    def metatron_on_activate(app_self):
        if bool(getattr(app_self, "_metatron_privacy_paused", False)):
            app_self._emit("PRIVACY_PAUSED", "dictation paused for the active application")
            return
        return native_on_activate(app_self)

    App._on_activate = metatron_on_activate

    class MetatronServer(Server):
        def _cmd_list_ov_devices(self, params):
            # Pinned EZSTT supports NPU and CPU. Do not advertise GPU merely
            # because OpenVINO sees one; a truthful fallback list is better.
            try:
                import openvino
                available = [str(x) for x in openvino.Core().available_devices]
                classes = {_device_class(x) for x in available}
                devices = [kind for kind in ("NPU", "CPU") if kind in classes]
                if not devices:
                    devices = ["CPU"]
            except Exception:
                available = []
                devices = ["NPU", "CPU"]
            return {"devices": devices, "raw_devices": available}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._dictionary: list[tuple[re.Pattern[str], str, str]] = []
            self._context_awareness = True
            self._default_context_profile = "general"
            self._policy = {
                "app_id": "",
                "paused": False,
                "allow_context": True,
                "context_profile": "general",
            }
            self._active_app: dict[str, str] = {}
            self._app_thread: threading.Thread | None = None

            from ezstt import inject as inject_module
            self._inject_module = inject_module
            self._native_inject_text = inject_module.inject_text

            def metatron_inject_text(text, *iargs, **ikwargs):
                raw_text = str(text)
                active = dict(self._active_app)
                policy = dict(self._policy)
                policy_matches = bool(
                    active.get("app_id")
                    and str(active.get("app_id")).casefold() == str(policy.get("app_id") or "").casefold()
                )
                # Re-check at injection to close the race where focus changes
                # after capture started but before transcription finished.
                if policy_matches and policy.get("paused"):
                    app = self.app
                    if app is not None:
                        setattr(app, "_metatron_suppress_next_injected", True)
                    self._send({
                        "event": "transcript",
                        "text": raw_text,
                        "raw_text": raw_text,
                        "final": True,
                        "status": "privacy_paused",
                        **active,
                        "context_profile": (policy.get("context_profile") if policy_matches else self._default_context_profile) or self._default_context_profile,
                    })
                    return None
                final_text, matched = _apply_dictionary(raw_text, self._dictionary)
                result = self._native_inject_text(final_text, *iargs, **ikwargs)
                self._send({
                    "event": "transcript",
                    "text": final_text,
                    "raw_text": raw_text if final_text != raw_text else "",
                    "final": True,
                    "status": "completed",
                    **active,
                    "context_profile": (policy.get("context_profile") if policy_matches else self._default_context_profile) or self._default_context_profile,
                    "dictionary_matches": matched,
                })
                return result

            inject_module.inject_text = metatron_inject_text

            native_emit = App._emit

            def metatron_emit(app_self, state, detail=""):
                if state == "INJECTED" and bool(getattr(app_self, "_metatron_suppress_next_injected", False)):
                    setattr(app_self, "_metatron_suppress_next_injected", False)
                    return native_emit(app_self, "PRIVACY_PAUSED", "text injection suppressed by active-app privacy policy")
                return native_emit(app_self, state, detail)

            self._native_app_emit = native_emit
            App._emit = metatron_emit

        def _boot(self):
            # Server.run sends protocol hello/config before _boot is started, so
            # launching active-app monitoring here preserves the upstream rule
            # that hello is always the first JSONL line.
            super()._boot()
            if self._app_thread is None:
                self._app_thread = threading.Thread(target=self._active_app_loop, name="metatron-active-app", daemon=True)
                self._app_thread.start()

        def run(self):
            try:
                return super().run()
            finally:
                self._inject_module.inject_text = self._native_inject_text
                App._on_activate = native_on_activate
                App._emit = self._native_app_emit

        def _active_app_loop(self):
            last_app_id = ""
            while not self._shutdown.wait(0.35):
                app = _foreground_app()
                if not app:
                    continue
                app_id = str(app.get("app_id") or "")
                if app_id.casefold() == last_app_id.casefold():
                    continue
                last_app_id = app_id
                self._active_app = app
                # Fail open until Metatron answers with the rule for this exact
                # app.  A pause rule from the previous app must never bleed into
                # the newly focused process during the policy round-trip.
                if self.app is not None:
                    setattr(self.app, "_metatron_privacy_paused", False)
                self._send({"event": "active_app", **app})

        def _wait_for_placement(self, requested: str, timeout_s: float = 180.0) -> dict[str, Any]:
            deadline = time.monotonic() + timeout_s
            last = "engine has not created the application yet"
            while time.monotonic() < deadline:
                app = self.app
                if app is None:
                    time.sleep(0.05)
                    continue
                if app.is_loading:
                    last = "model is still loading"
                    time.sleep(0.1)
                    continue
                transcriber = app.transcriber
                if transcriber is None:
                    raise ProtocolError("no_model", "no EZSTT model is loaded")
                proof = _placement_payload(transcriber, requested)
                if proof["placement_verified"]:
                    return proof
                reported = _device_class(getattr(transcriber, "device", ""))
                last = (
                    f"requested={requested!r}, transcriber={getattr(transcriber, 'device', '')!r}, "
                    f"execution_devices={proof['execution_devices']!r}"
                )
                if reported != _device_class(requested):
                    time.sleep(0.1)
                    continue
                if proof["execution_devices"]:
                    break
                time.sleep(0.1)
            raise ProtocolError("placement_unverified", f"could not verify STT placement: {last}")

        def _cmd_set_config(self, params):
            if not isinstance(params, dict) or not params:
                raise ProtocolError("bad_request", "set_config needs a non-empty object")
            upstream = _filtered_upstream_config(params, set(DEFAULTS))
            unknown = sorted(set(params) - set(upstream) - METATRON_ONLY_CONFIG_KEYS)
            if unknown:
                raise ProtocolError("unknown_key", f"unknown config keys: {', '.join(unknown)}")
            self._context_awareness = bool(params.get("context_awareness", self._context_awareness))
            self._default_context_profile = str(params.get("default_context_profile") or self._default_context_profile)
            result = super()._cmd_set_config(upstream) if upstream else self._config_payload()
            requested = str(upstream.get("device") or self.cfg.device).upper()
            proof = self._wait_for_placement(requested)
            return {
                **result,
                **proof,
                "metatron_compat": 2,
                "ezstt_revision": PINNED_EZSTT_REVISION,
                "capabilities": {
                    "active_app": os.name == "nt",
                    "app_policy": True,
                    "personalization": True,
                },
            }

        def _cmd_set_personalization(self, params):
            if not isinstance(params, dict):
                raise ProtocolError("bad_request", "set_personalization needs an object")
            entries = params.get("dictionary") or []
            if not isinstance(entries, list):
                raise ProtocolError("bad_request", "dictionary must be a list")
            self._dictionary = _compile_dictionary(entries)
            self._context_awareness = bool(params.get("context_awareness", True))
            self._default_context_profile = str(params.get("default_context_profile") or "general")[:64]
            return {
                "supported": True,
                "dictionary_count": len(self._dictionary),
                "context_awareness": self._context_awareness,
                "default_context_profile": self._default_context_profile,
            }

        def _cmd_set_app_policy(self, params):
            if not isinstance(params, dict):
                raise ProtocolError("bad_request", "set_app_policy needs an object")
            app_id = str(params.get("app_id") or "").strip()
            if not app_id:
                raise ProtocolError("bad_request", "set_app_policy needs app_id")
            self._policy = {
                "app_id": app_id,
                "paused": bool(params.get("paused", False)),
                "allow_context": bool(params.get("allow_context", True)),
                "context_profile": str(params.get("context_profile") or self._default_context_profile)[:64],
            }
            current_id = str(self._active_app.get("app_id") or "")
            applied = bool(current_id and current_id.casefold() == app_id.casefold())
            if self.app is not None:
                setattr(self.app, "_metatron_privacy_paused", bool(applied and self._policy["paused"]))
            return {"supported": True, "applied": applied, **self._policy}

    return MetatronServer


def main() -> int:
    parser = argparse.ArgumentParser(description="Metatron-compatible EZSTT JSONL sidecar")
    parser.add_argument("--engine-root", required=True)
    parser.add_argument("--config", default="")
    parser.add_argument("--wav", default="", help="test-only WAV source instead of microphone")
    args = parser.parse_args()

    engine_root = Path(args.engine_root).expanduser().resolve()
    server_cls = _build_server(engine_root)

    try:
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass
    proto_out = sys.stdout
    sys.stdout = sys.stderr

    from ezstt import audio, paths
    from ezstt.config import load_config

    config_path = args.config or str(paths.config_path())
    cfg = load_config(config_path)
    if args.wav:
        wav = str(Path(args.wav).resolve())
        make_source = lambda: audio.WavSource(wav, cfg.sample_rate)
    else:
        make_source = lambda: audio.MicSource.from_config(cfg)

    server_cls(cfg, make_source, proto_out).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
