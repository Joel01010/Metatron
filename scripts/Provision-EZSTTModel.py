#!/usr/bin/env python3
"""Idempotently install and verify the pinned EZSTT Parakeet model.

Uses EZSTT's own JSONL first-run protocol against the real EngineRoot so the
installed model follows the same download, hash verification, OpenVINO compile,
and READY transition as the application.  Existing healthy installs are kept.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-root", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--model", default="parakeet-unified-en-0.6b")
    ap.add_argument("--device", default="NPU")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    root = Path(args.engine_root).resolve()
    py = Path(args.python).resolve()
    main_py = root / "engine" / "main.py"
    wav = root / "tests" / "test_phrase.wav"
    if not main_py.is_file() or not wav.is_file() or not py.is_file():
        raise SystemExit("EZSTT engine/python/test WAV is incomplete")

    model_dir = root / "models" / args.model
    env = dict(os.environ)
    env["EZSTT_DIR"] = str(root)
    cmd = [str(py), str(main_py), "--serve", "--wav", str(wav), "--device", args.device]
    proc = subprocess.Popen(
        cmd,
        cwd=root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    events: queue.Queue[dict] = queue.Queue()
    responses: dict[int, dict] = {}
    cv = threading.Condition()

    def pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if "event" in obj:
                events.put(obj)
            else:
                with cv:
                    responses[int(obj.get("id", -1))] = obj
                    cv.notify_all()

    threading.Thread(target=pump, daemon=True).start()
    next_id = 0

    def request(command: str, params: dict | None = None, timeout: float = 20) -> dict:
        nonlocal next_id
        next_id += 1
        rid = next_id
        payload = {"id": rid, "cmd": command, "params": params or {}}
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        deadline = time.monotonic() + timeout
        with cv:
            while rid not in responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"no response to {command}")
                cv.wait(remaining)
            out = responses.pop(rid)
        if not out.get("ok"):
            raise RuntimeError((out.get("error") or {}).get("message") or f"{command} failed")
        return out.get("result") or {}

    def wait_event(pred, timeout: float, label: str) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"EZSTT exited while waiting for {label} (code {proc.returncode})")
            try:
                ev = events.get(timeout=min(0.5, max(0.05, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if pred(ev):
                return ev
        raise TimeoutError(f"timed out waiting for {label}")

    try:
        hello = wait_event(lambda e: e.get("event") == "hello", 20, "protocol hello")
        if int(hello.get("protocol", 0)) != 1:
            raise RuntimeError(f"unexpected protocol: {hello}")

        models = request("list_models", timeout=20).get("models", [])
        entry = next((m for m in models if m.get("id") == args.model), None)
        if entry is None:
            raise RuntimeError(f"model {args.model!r} is absent from pinned manifest")

        if entry.get("status") == "installed" and model_dir.is_dir():
            request("select_model", {"id": args.model, "device": args.device}, timeout=20)
            wait_event(lambda e: e.get("state") == "READY", min(args.timeout, 900), "READY after existing model load")
            print(f"PASS: existing {args.model} verified/loaded on {args.device}")
            return 0

        print(f"Installing {args.model} through EZSTT first-run protocol...", flush=True)
        request("download_model", {"id": args.model}, timeout=20)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            ev = wait_event(lambda e: e.get("event") == "download", min(60, deadline - time.monotonic()), "download progress")
            phase = ev.get("phase")
            if phase == "downloading":
                total = float(ev.get("total") or 0) / 1e6
                done = float(ev.get("downloaded") or 0) / 1e6
                print(f"  download {done:.0f}/{total:.0f} MB", flush=True)
            elif phase == "verifying":
                print(f"  verifying/compiling on {ev.get('device') or args.device}...", flush=True)
            elif phase == "done":
                break
            elif phase in {"error", "cancelled"}:
                raise RuntimeError(f"model install {phase}: {ev.get('error') or ev}")
        else:
            raise TimeoutError("model installation timed out")

        wait_event(lambda e: e.get("state") == "READY", min(600, args.timeout), "READY after model install")
        cfg = request("get_config", timeout=20)
        if not cfg.get("resolved", {}).get("model_installed"):
            raise RuntimeError("EZSTT did not report the installed model")
        print(f"PASS: installed and verified {args.model} on {args.device}")
        return 0
    finally:
        if proc.poll() is None:
            try:
                request("shutdown", timeout=5)
            except Exception:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
