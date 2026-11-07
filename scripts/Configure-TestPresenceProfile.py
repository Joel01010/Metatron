#!/usr/bin/env python3
"""Create an isolated Metatron data directory for Presence qualification.

The native Presence test sets METATRON_DATA_DIR to this directory before it
launches the built Tauri app, so release testing never mutates the user's real
settings/database merely to capture renderer variants.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument(
        "--profile",
        required=True,
        choices=("solar", "lattice", "reactor", "pets", "both"),
    )
    args = ap.parse_args()
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["METATRON_DATA_DIR"] = str(data_dir)
    os.environ["METATRON_TTS_ENABLED"] = "0"

    from metatron.core import Metatron

    app = Metatron()
    try:
        app.settings.set("onboarding", {"completed": True, "show_tips": False})
        app.settings.set("appearance", {"reduce_motion": False, "motion_style": "balanced"})
        pets = app.settings.get("companions")["pets"]
        if args.profile in {"pets", "both"}:
            pets = [{**pet, "enabled": True} for pet in pets]
            app.settings.set(
                "companions",
                {
                    "enabled": True,
                    "reaction_gain": 1.0,
                    "pointer_interaction": True,
                    "performance_policy": "full",
                    "pets": pets,
                },
            )
        else:
            app.settings.set("companions", {"enabled": False})

        if args.profile in {"solar", "lattice", "reactor"}:
            mode = "orb"
            style = args.profile
        elif args.profile == "pets":
            mode = "pet"
            style = "solar"
        else:
            mode = "both"
            style = "reactor"
        app.settings.set(
            "presence",
            {
                "enabled": True,
                "quality": "balanced",
                "desktop_orb": True,
                "desktop_pets": True,
                "always_on_top": True,
                "click_through": True,
                "mode": mode,
                "core_style": style,
                "orb_scale": 1.0,
                "orb_opacity": 0.96,
                "core_pulse": 0.9,
                "core_rotation": 0.7,
                "core_complexity": 0.9,
                "core_shell": 0.8,
                "trail_strength": 0.5,
                "parallax_strength": 0.7,
            },
        )
        print(data_dir)
        return 0
    finally:
        app.close()


if __name__ == "__main__":
    raise SystemExit(main())
