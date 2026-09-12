#!/usr/bin/env python3
"""Assert that every named feature actually changes the mesh.

check_stl.py answers "is this mesh valid?" - watertight, manifold, one piece.
It cannot answer "does this part have the holes it is supposed to have?", and
the difference matters: a cut positioned in mid-air removes nothing, leaves the
part perfectly valid, and ships a shell with no mounting provision in it.

That is not hypothetical. `mic_inserts()` in head_back.scad sat at y = 11.8..16
at the microphone's height, which is open space inside the brow cavity rather
than wall, so it cut nothing at all. The part validated cleanly, the assembly
guide told you to press two M2 inserts into holes that did not exist, and
nothing in the build caught it.

This script renders each part twice - once whole, once with one module call
commented out - and asserts the triangle count changes. A feature that makes no
difference to the mesh is either cutting air or adding nothing, and either way
it is a bug.

    python3 check_features.py            # every part listed below
    python3 check_features.py head_back  # just one

Needs openscad on PATH. Roughly one render per feature, so it is slower than
check_stl.py; CI runs it alongside the CAD rebuild rather than on every push.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# part -> the module calls that must each leave a mark on the mesh.
# Only load-bearing features are listed; cosmetics are free to be no-ops.
FEATURES: dict[str, list[str]] = {
    "head_back": [
        "tilt_servo_pad",
        "tilt_pivot_pad",
        "pi_posts",
        "faceplate_posts",
        "trim_post",
        "camera_posts",
        "amp_pads",
        "tilt_servo_negatives",
        "tilt_pivot_negative",
        "tilt_stop_slots",
        "pod_window_inserts",
        "mic_inserts",
        "rear_vents",
    ],
    "base_shell": [
        "legs",
        "deck_bosses",
        "speaker_mount",
        "pca_pads",
        "buck_pads",
        "panel_cutouts",
    ],
    "base_deck": ["pan_stop"],
    "turntable": ["stop_slot"],
    "faceplate": ["pockets", "panel_screw_bosses", "frame_screws"],
    "yoke": ["cable_channel"],
}


def triangles(stl: Path) -> int:
    """Triangle count from a binary STL header."""
    import struct

    with stl.open("rb") as fh:
        fh.seek(80)
        return struct.unpack("<I", fh.read(4))[0]


def render(scad_text: str, out: Path, work: Path) -> bool:
    """Render scad_text to out. False if OpenSCAD refused it.

    The variant is written outside the repository and OPENSCADPATH points the
    `include <rocky_params.scad>` at hardware/cad, so a run - or an interrupted
    run - never drops scratch .scad files into the working tree.
    """
    tmp = work / "variant.scad"
    tmp.write_text(scad_text)
    env = {**os.environ, "OPENSCADPATH": str(HERE)}
    r = subprocess.run(
        ["openscad", "-o", str(out), "--export-format", "binstl", str(tmp)],
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode == 0 and out.exists() and out.stat().st_size > 84


def check(part: str, features: list[str], work: Path) -> list[str]:
    src_path = HERE / f"{part}.scad"
    if not src_path.exists():
        return [f"{part}.scad not found"]
    src = src_path.read_text()

    whole = work / f"{part}.stl"
    if not render(src, whole, work):
        return [f"{part}: base render failed"]
    base = triangles(whole)

    problems = []
    for feature in features:
        # match the call on its own line, however it is indented
        pattern = re.compile(rf"^([ \t]*){feature}\(\);[ \t]*$", re.M)
        hits = len(pattern.findall(src))
        if hits == 0:
            problems.append(f"{part}: no call to {feature}() found")
            continue
        if hits > 1:
            problems.append(f"{part}: {feature}() called {hits} times, expected once")
            continue

        stripped = pattern.sub(r"\1// removed for the feature check", src)
        out = work / f"{part}-no-{feature}.stl"
        if not render(stripped, out, work):
            problems.append(f"{part}: render failed without {feature}()")
            continue

        without = triangles(out)
        if without == base:
            problems.append(
                f"{part}: {feature}() changes nothing "
                f"({base} triangles with and without) - it is cutting air"
            )
        print(f"    {feature:<22} {base - without:+6d} tris")
    return problems


def main(argv: list[str]) -> int:
    wanted = argv[1:] or list(FEATURES)
    unknown = [p for p in wanted if p not in FEATURES]
    if unknown:
        print(f"unknown part(s): {', '.join(unknown)}")
        return 2

    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for part in wanted:
            print(f"{part}:")
            problems += check(part, FEATURES[part], work)

    print()
    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        print(f"\n{len(problems)} feature problem(s)")
        return 1
    print(f"every listed feature in {len(wanted)} part(s) changes its mesh")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
