#!/usr/bin/env python3
"""Validate exported STLs: watertight, manifold, single-shell, sane size.

Usage:  python3 check_stl.py ../stl/*.stl
Exit code is non-zero if any file fails, so build_all.sh can gate on it.
"""
from __future__ import annotations
import struct
import sys
from collections import defaultdict


VERBOSE = False


def load(path):
    with open(path, "rb") as fh:
        head = fh.read(5)
        fh.seek(0)
        if head == b"solid":  # could still be binary with a lying header
            text = fh.read()
            if b"facet normal" in text[:2000]:
                return _load_ascii(text.decode("utf-8", "replace"))
            fh.seek(0)
        return _load_binary(fh)


def _load_binary(fh):
    fh.seek(80)
    (count,) = struct.unpack("<I", fh.read(4))
    tris = []
    for _ in range(count):
        data = fh.read(50)
        vals = struct.unpack("<12fH", data)
        tris.append((vals[3:6], vals[6:9], vals[9:12]))
    return tris


def _load_ascii(text):
    tris, cur = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            cur.append(tuple(float(v) for v in line.split()[1:4]))
            if len(cur) == 3:
                tris.append(tuple(cur))
                cur = []
    return tris


def quantize(v, q=1e-5):
    return tuple(round(c / q) for c in v)


def analyse(path):
    tris = load(path)
    if not tris:
        return path, ["empty mesh"], {}

    verts = {}
    faces = []
    for tri in tris:
        faces.append(tuple(verts.setdefault(quantize(p), len(verts)) for p in tri))

    # --- edge manifoldness -------------------------------------------------
    edges = defaultdict(int)
    directed = defaultdict(int)
    for a, b, c in faces:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(min(u, v), max(u, v))] += 1
            directed[(u, v)] += 1

    boundary = sum(1 for n in edges.values() if n == 1)
    nonmanifold = sum(1 for n in edges.values() if n > 2)
    # consistent winding: every directed edge appears once, its twin once
    flipped = sum(1 for (u, v), n in directed.items() if n > 1)

    # --- connected components ---------------------------------------------
    adj = defaultdict(set)
    for a, b, c in faces:
        adj[a].update((b, c))
        adj[b].update((a, c))
        adj[c].update((a, b))
    seen, comps, comp_verts = set(), 0, []
    for start in adj:
        if start in seen:
            continue
        comps += 1
        stack, members = [start], [start]
        seen.add(start)
        while stack:
            cur = stack.pop()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
                    members.append(nxt)
        comp_verts.append(members)

    # --- signed volume + bbox ---------------------------------------------
    pts = {i: p for p, i in ((k, v) for k, v in verts.items())}
    coords = [[c * 1e-5 for c in p] for p in verts]
    xs = [p[0] for p in coords]; ys = [p[1] for p in coords]; zs = [p[2] for p in coords]
    vol = 0.0
    inv = {i: [c * 1e-5 for c in p] for p, i in verts.items()}
    for a, b, c in faces:
        pa, pb, pc = inv[a], inv[b], inv[c]
        vol += (
            pa[0] * (pb[1] * pc[2] - pc[1] * pb[2])
            - pa[1] * (pb[0] * pc[2] - pc[0] * pb[2])
            + pa[2] * (pb[0] * pc[1] - pc[0] * pb[1])
        ) / 6.0

    stats = {
        "triangles": len(faces),
        "vertices": len(verts),
        "components": comps,
        "bbox": (
            round(max(xs) - min(xs), 2),
            round(max(ys) - min(ys), 2),
            round(max(zs) - min(zs), 2),
        ),
        "volume_cm3": round(abs(vol) / 1000.0, 2),
    }

    if comps != 1 and VERBOSE:
        inv2 = {i: [c * 1e-5 for c in p] for p, i in verts.items()}
        for n, members in enumerate(sorted(comp_verts, key=len, reverse=True)):
            pts3 = [inv2[m] for m in members]
            lo = [min(p[i] for p in pts3) for i in range(3)]
            hi = [max(p[i] for p in pts3) for i in range(3)]
            print(
                f"       shell {n}: {len(members):>6} verts  "
                f"x[{lo[0]:7.1f},{hi[0]:7.1f}] y[{lo[1]:7.1f},{hi[1]:7.1f}] "
                f"z[{lo[2]:7.1f},{hi[2]:7.1f}]"
            )

    problems = []
    if boundary:
        problems.append(f"{boundary} boundary edge(s) - mesh is not watertight")
    if nonmanifold:
        problems.append(f"{nonmanifold} non-manifold edge(s)")
    if flipped:
        problems.append(f"{flipped} inconsistently wound edge(s)")
    if comps != 1:
        problems.append(f"{comps} disconnected shells - part would print in pieces")
    if vol < 0:
        problems.append("inverted normals (negative volume)")
    return path, problems, stats


def main(argv):
    global VERBOSE
    paths = [a for a in argv[1:] if not a.startswith("-")]
    VERBOSE = "-v" in argv or "--components" in argv
    if not paths:
        print(__doc__)
        return 2
    bad = 0
    width = max(len(p.rsplit("/", 1)[-1]) for p in paths)
    for path in paths:
        name, problems, stats = analyse(path)
        short = name.rsplit("/", 1)[-1]
        if problems:
            bad += 1
            print(f"FAIL {short:<{width}}  " + "; ".join(problems))
        else:
            bb = stats["bbox"]
            print(
                f"ok   {short:<{width}}  {stats['triangles']:>7} tris  "
                f"{bb[0]:>6.1f} x {bb[1]:>6.1f} x {bb[2]:>6.1f} mm  "
                f"{stats['volume_cm3']:>7.1f} cm3"
            )
    if bad:
        print(f"\n{bad} of {len(paths)} file(s) failed validation")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
