"""Download and verify the official Orukeet INT8 ONNX release.

Constants are taken from Oruk-AI/orukeet examples/download_onnx.py.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from huggingface_hub import hf_hub_download

REPO_ID = "oruk/orukeet"
REVISION = "55a984d46f68323301837194ce647c702f55facc"
MANIFEST_PATH = "onnx/manifest.json"
MANIFEST_SHA256 = "7e80f93f0e9b923c392424b0f85d28a717feee0a4d2a6aa9bfa723693868e727"

def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("orukeet-model"))
    ap.add_argument("--cache", type=Path, default=Path("orukeet-cache"))
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    opts = dict(revision=REVISION, local_dir=args.cache / "hub")
    manifest_path = Path(hf_hub_download(REPO_ID, MANIFEST_PATH, **opts))
    got = sha256(manifest_path)
    if got != MANIFEST_SHA256:
        raise RuntimeError(f"manifest SHA256 mismatch: {got}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_rel = "onnx/" + manifest["archive"]
    archive = Path(hf_hub_download(REPO_ID, archive_rel, **opts))

    if archive.stat().st_size != manifest["archive_bytes"]:
        raise RuntimeError("archive size mismatch")
    got = sha256(archive)
    if got != manifest["archive_sha256"]:
        raise RuntimeError(f"archive SHA256 mismatch: {got}")

    with tarfile.open(archive, "r:bz2") as tf:
        tf.extractall(args.out)

    # Flatten one top-level directory if the archive contains one.
    children = [p for p in args.out.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        inner = children[0]
        for p in list(inner.iterdir()):
            p.rename(args.out / p.name)
        inner.rmdir()

    print("Downloaded and verified official Orukeet INT8 ONNX release.")
    print("Model dir:", args.out.resolve())
    for name in ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"):
        p = args.out / name
        print(f"{name}: {'OK' if p.exists() else 'MISSING'}")

if __name__ == "__main__":
    main()
