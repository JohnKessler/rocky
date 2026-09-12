#!/usr/bin/env bash
# ---------------------------------------------------------------------
# Render every figure used in the documentation.
#
#   ./render_figures.sh              all of them
#   ./render_figures.sh stage4       just one
#
# Needs openscad and, on a headless machine, xvfb-run.
# ---------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "$0")"
OUT=../img
mkdir -p "$OUT"

RUN=(openscad)
command -v xvfb-run >/dev/null && RUN=(xvfb-run -a openscad)

# view | width height | camera tx,ty,tz,rx,ry,rz,dist | explode | label length
# Label length is in model millimetres and is set to about a sixth of the
# camera distance, which keeps callouts inside the frame at every scale.
FIGURES=(
  "exploded|2100 1750|0,0,215,62,0,205,1290|1.0|165"
  "assembled|1200 1400|0,0,130,68,0,215,780|0|0"
  "stage2|1800 1320|0,0,26,34,0,205,560|0|118"
  "stage3|1700 1200|0,0,40,62,0,205,430|0|72"
  "stage4|1800 1250|0,0,70,54,0,205,470|1.0|80"
  "stage5|1500 1500|0,0,118,62,0,205,600|0|95"
  "stage6|1800 1350|0,4,16,56,0,195,505|0|78"
  "stage7|1800 1420|0,10,0,60,0,212,495|1.0|68"
  "harness|1700 1250|0,0,46,52,0,205,430|0|72"
)

want=${1:-}
fail=0
for row in "${FIGURES[@]}"; do
    IFS='|' read -r view size cam explode label <<<"$row"
    [ -n "$want" ] && [ "$want" != "$view" ] && continue
    read -r w h <<<"$size"
    printf '%-12s ' "$view"
    if "${RUN[@]}" -o "$OUT/assembly-$view.png" \
         --imgsize="$w,$h" --camera="$cam" --colorscheme=Tomorrow \
         -D "VIEW=\"$view\"" -D "EXPLODE=$explode" -D "LABEL_D=$label" \
         assembly_guide.scad >/tmp/fig.out 2>/tmp/fig.err; then
        # Capture the callout captions the figure echoed, so the legend in the
        # documentation is generated from the same source as the numbers.
        # OpenSCAD writes echo() to stdout and progress to stderr.
        grep -ho 'LEGEND|[^"]*' /tmp/fig.out /tmp/fig.err | sed 's/^LEGEND|//' \
            > "$OUT/assembly-$view.legend"
        printf '%s  (%s callouts)\n' \
            "$(du -h "$OUT/assembly-$view.png" | cut -f1)" \
            "$(wc -l < "$OUT/assembly-$view.legend" | tr -d ' ')"
    else
        echo "FAILED"; sed 's/^/    /' /tmp/fig.err | head -5; fail=1
    fi
done
exit $fail
