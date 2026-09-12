#!/usr/bin/env python3
"""Fold the generated figures and tables into the documentation.

Both the assembly figures and the wiring diagrams carry their captions with
them - the figures echo their callout text at render time, and the wiring
tables come straight out of the wiring data. This script drops both into the
markdown between marker comments, so the pictures, their legends and the
tables can never drift from each other or from the design.

    python3 hardware/update_docs.py

Markers look like:  <!-- figure:stage4 -->  ...  <!-- /figure -->
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "hardware" / "img"
DOCS = ROOT / "docs"

TITLES = {
    "exploded": "Rocky, exploded",
    "assembled": "Assembled",
    "stage2": "Stage 2 — the base electronics",
    "stage3": "Stage 3 — the pan servo hangs from the deck",
    "stage4": "Stage 4 — the slew ring",
    "stage5": "Stage 5 — the yoke",
    "stage6": "Stage 6 — inside the head",
    "stage7": "Stage 7 — display and faceplate",
    "harness": "The pan-joint harness",
}


def figure_block(view: str, rel_prefix: str = "../hardware/img") -> str:
    """An image plus the legend the figure itself emitted."""
    png = IMG / f"assembly-{view}.png"
    if not png.exists():
        raise SystemExit(f"missing render: {png} - run hardware/cad/render_figures.sh")

    lines = [f"![{TITLES.get(view, view)}]({rel_prefix}/assembly-{view}.png)", ""]

    legend = IMG / f"assembly-{view}.legend"
    if legend.exists() and legend.read_text().strip():
        for row in legend.read_text().strip().split("\n"):
            number, _, caption = row.partition("|")
            lines.append(f"**{number}.** {caption}  ")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def wiring_block(name: str, rel_prefix: str = "../hardware/img") -> str:
    svg = IMG / f"wiring-{name}.svg"
    if not svg.exists():
        raise SystemExit(f"missing diagram: {svg} - run hardware/wiring/generate.py")
    return f"![{name} diagram]({rel_prefix}/wiring-{name}.svg)\n"


# Which heading in tables.md each marker name pulls in. A marker asking for
# one table must not paste all three.
TABLE_SECTIONS = {
    "connections": "Every connection",
    "harness": "The pan-joint harness",
    "gpio": "GPIO pins in use",
}


def tables_block(name: str) -> str:
    path = ROOT / "hardware" / "wiring" / "tables.md"
    if not path.exists():
        raise SystemExit("missing tables.md - run hardware/wiring/generate.py")
    if name not in TABLE_SECTIONS:
        raise SystemExit(f"unknown table {name!r}; expected one of {sorted(TABLE_SECTIONS)}")

    wanted = TABLE_SECTIONS[name]
    collecting, rows = False, []
    for line in path.read_text().split("\n"):
        if line.startswith("### "):
            collecting = wanted in line
            continue                       # the surrounding doc supplies headings
        if collecting:
            rows.append(line)
    body = "\n".join(rows).strip()
    if not body:
        raise SystemExit(f"table {name!r} not found in tables.md")
    return body + "\n"


BUILDERS = {
    "figure": figure_block,
    "wiring": wiring_block,
    "tables": tables_block,
}


def fill(path: Path) -> int:
    """Replace everything between each marker pair. Returns how many."""
    text = path.read_text()
    pattern = re.compile(
        r"(<!-- (figure|wiring|tables):([a-z0-9_]+) -->\n).*?(<!-- /\2 -->)",
        re.DOTALL,
    )

    count = 0

    def swap(m: re.Match) -> str:
        nonlocal count
        count += 1
        opener, kind, name, closer = m.groups()
        return opener + BUILDERS[kind](name) + closer

    new = pattern.sub(swap, text)
    if new != text:
        path.write_text(new)
    return count


def main() -> int:
    total = 0
    for doc in sorted(DOCS.glob("*.md")):
        n = fill(doc)
        if n:
            print(f"  {doc.name}: filled {n} block(s)")
            total += n
    if total == 0:
        print("  no markers found - nothing to fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
