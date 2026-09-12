#!/usr/bin/env bash
# ---------------------------------------------------------------------
# Render every printable part to hardware/stl/ and validate each mesh.
#
#   ./build_all.sh            render everything
#   ./build_all.sh yoke       render one part
#
# Requires openscad (>= 2021.01) and python3 on PATH.
# ---------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")"
OUT=../stl
mkdir -p "$OUT"

PARTS=(base_shell base_deck turntable yoke head_back faceplate
       pod_window mic_mount cable_clip ball_cage speaker_gasket)

if [ $# -gt 0 ]; then PARTS=("$@"); fi

fail=0
for p in "${PARTS[@]}"; do
    printf '%-16s ' "$p"
    if ! err=$(openscad -o "$OUT/$p.stl" "$p.scad" 2>&1 | grep -E '^(ERROR|WARNING)'); then :; fi
    if [ ! -s "$OUT/$p.stl" ]; then
        echo "RENDER FAILED"; echo "$err"; fail=1; continue
    fi
    echo "rendered"
    if [ -n "$err" ]; then echo "$err" | sed 's/^/    /'; fi
done

echo
echo "--- mesh validation ---"
python3 check_stl.py "$OUT"/*.stl || fail=1
exit $fail
