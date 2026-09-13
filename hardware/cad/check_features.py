#!/usr/bin/env python3
"""Assert that every named feature actually changes the mesh.

check_stl.py answers "is this mesh valid?" - watertight, manifold, one piece.
It cannot answer "does this part have the holes it is supposed to have?", and
the difference matters: a cut positioned in mid-air removes nothing, leaves the
part perfectly valid, and ships a shell with no mounting provision in it.

That is not hypothetical. `mic_inserts()` in head_back.scad sat at y = 11.8..16
at the microphone's height, which is open space inside the brow cavity rather
than wall, so it cut nothing at all. `tilt_stop_slots()` in the same file was
anchored 9.4 mm outside the shell and swept all 41 of its cuts through fresh
air, which left the mechanical tilt end stop simply absent. Both parts
validated cleanly, the assembly guide told you to press two M2 inserts into
holes that did not exist and to trust a stop that was not there, and nothing in
the build caught either one.

This script renders each part twice - once whole, once with one module call
commented out - and compares the two meshes. A feature that makes no difference
is either cutting air or adding nothing, and either way it is a bug.

It measures VOLUME as well as triangle count, because triangles are a poor
proxy in both directions, and measurably so. yoke's cable_channel moves the
count by 16 triangles and removes 1610 mm3 - that is simply what a clean
rectangular groove in a flat face costs in triangles. head_back's mic_cradle
moves it by 70 and adds 3114 mm3. Meanwhile a cut that merely clips a corner
can add dozens of triangles while removing almost nothing. Volume is what "does
this feature change the part" actually means, so that is what the pass/fail
turns on, and a feature whose volume barely moves is flagged even when it
technically changes the mesh.

What this cannot tell you is whether a feature is in the RIGHT place - only
that it is in material at all. turntable's stop_slot always cut a real slot;
the slot was just 50 degrees too short, so the pan servo stalled into its own
end stop. For that kind of thing there is no substitute for measuring the mesh.

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
        "pod_window_screws",
        "mic_cradle",
        "mic_port",
        "cam_aperture",
        "brow_cable_slot",
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
    "pod_window": ["camera_aperture", "mic_rosette", "screw_holes"],
    "yoke": ["cable_channel", "tilt_stop_pin"],
}


# A feature whose volume moves by less than this is reported even though it is
# not strictly a no-op. The smallest deliberate feature in this design is a
# single M2 insert bore, 3.2 mm across and 4.4 deep - 35 mm3 - so anything under
# 25 mm3 is smaller than one screw hole and worth a second look.
SUSPICIOUS_MM3 = 25.0
# Features that really are that small, with the reason. Keeping them here means
# a newly-tiny feature still gets flagged instead of being lost in known noise.
SMALL_BY_DESIGN = {
    "head_back:pod_window_screws": "two 2.1 mm pilot bores through 2.4 mm of "
    "brow wall is 16.6 mm3, and that wall cannot be thickened from inside",
}
# Two renders of geometrically identical solids agree on volume to far better
# than this; CGAL only varies the order it walks the facets in.
SAME_MM3 = 0.01


def measure(stl: Path) -> tuple[int, float]:
    """Triangle count and enclosed volume (mm3) of a binary STL."""
    import struct

    with stl.open("rb") as fh:
        fh.seek(80)
        (count,) = struct.unpack("<I", fh.read(4))
        vol = 0.0
        for _ in range(count):
            v = struct.unpack("<12fH", fh.read(50))
            ax, ay, az, bx, by, bz, cx, cy, cz = v[3:12]
            # six times the signed volume of the tetrahedron on the origin
            vol += (
                ax * (by * cz - cy * bz)
                - ay * (bx * cz - cx * bz)
                + az * (bx * cy - cx * by)
            )
    return count, abs(vol) / 6.0


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


warnings: list[str] = []
notes: list[str] = []


def check(part: str, features: list[str], work: Path) -> list[str]:
    src_path = HERE / f"{part}.scad"
    if not src_path.exists():
        return [f"{part}.scad not found"]
    src = src_path.read_text()

    whole = work / f"{part}.stl"
    if not render(src, whole, work):
        return [f"{part}: base render failed"]
    base_t, base_v = measure(whole)

    problems = []
    for feature in features:
        # Match every call on its own line, however it is indented and
        # whatever it is passed: a module like tilt_stop_pin(side) is called
        # once per side, and all of them have to go for the comparison to mean
        # anything.
        pattern = re.compile(rf"^([ \t]*){feature}\([^()]*\);[ \t]*$", re.M)
        if not pattern.search(src):
            problems.append(f"{part}: no call to {feature}() found")
            continue

        stripped = pattern.sub(r"\1// removed for the feature check", src)
        out = work / f"{part}-no-{feature}.stl"
        if not render(stripped, out, work):
            problems.append(f"{part}: render failed without {feature}()")
            continue

        out_t, out_v = measure(out)
        dt, dv = base_t - out_t, base_v - out_v
        if abs(dv) < SAME_MM3:
            detail = (
                "it is cutting air"
                if dt == 0
                else f"only {dt:+d} triangles moved - it grazes a surface"
            )
            problems.append(
                f"{part}: {feature}() changes no volume "
                f"({base_v:.1f} mm3 with and without) - {detail}"
            )
        elif abs(dv) < SUSPICIOUS_MM3:
            why = SMALL_BY_DESIGN.get(f"{part}:{feature}")
            if why:
                notes.append(f"{part}: {feature}() moves {dv:+.2f} mm3 - {why}")
            else:
                warnings.append(
                    f"{part}: {feature}() moves only {dv:+.2f} mm3 "
                    f"(smaller than one M2 insert bore) - check it lands where "
                    f"it is meant to"
                )
        print(f"    {feature:<22} {dt:+6d} tris  {dv:+10.2f} mm3")
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
    for n in notes:
        print(f"note  {n}")
    for w in warnings:
        print(f"WARN  {w}")
    if problems:
        if warnings or notes:
            print()
        for p in problems:
            print(f"FAIL  {p}")
        print(f"\n{len(problems)} feature problem(s)")
        return 1
    if warnings:
        print(f"\n{len(warnings)} feature(s) worth a look, none of them no-ops")
    print(f"every listed feature in {len(wanted)} part(s) removes or adds volume")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
