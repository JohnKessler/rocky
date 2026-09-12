# Printing

Eleven parts, about **625 cm³** of plastic — roughly 780 g in PETG. Budget two
days of printer time. Nothing needs supports except the sensor brow, and only a
little there.

## Settings

Sensible defaults for a 0.4 mm nozzle:

| Setting | Value | Why |
|---------|-------|-----|
| Layer height | 0.2 mm | 0.16 on the faceplate if you want a crisper bezel. |
| Perimeters | 3 (**4** on structural parts) | Marked per part below. |
| Infill | 20% (**40%** on structural parts) | Gyroid or cubic. |
| Top/bottom layers | 4 / 4 | |
| Material | **PETG** | Holds heat-set inserts far better than PLA and will not sag in a warm room. PLA is fine if Rocky lives somewhere cool. |
| Nozzle | 240 °C PETG / 210 °C PLA | |
| Bed | 80 °C PETG / 60 °C PLA | |
| Supports | Off, except `head_back` | |
| Seam | Rear / aligned | Keeps the seam off Rocky's face. |

## The parts

| Part | Orientation | Size (mm) | Volume | Settings |
|------|-------------|-----------|--------|----------|
| `base_shell` | As modelled, floor down | 178 × 174 × 62 | 165 cm³ | 3 perim / 20% |
| `base_deck` | Flat, **race groove up** | 156 × 156 × 11 | 104 cm³ | **4 perim / 40%** — the whole head's weight passes through this plate |
| `turntable` | Flat, **race groove down**, hub up | 150 × 150 × 15 | 99 cm³ | **4 perim / 40%** |
| `yoke` | **Lay it on its back** — rotate 90° about X so the U sits flat | 157 × 108 × 26 | 82 cm³ | **4 perim / 40%** — layers must run across the arms, not along them |
| `head_back` | Rear face down, open side up | 142 × 171 × 57 | 117 cm³ | 3 perim / 20% · **light supports under the brow only** |
| `faceplate` | **Front face down** | 142 × 142 × 10 | 40 cm³ | 3 perim / 25% · the part people look at, so print it well |
| `pod_window` | Outside face down | 46 × 26 × 5 | 4 cm³ | 3 perim / 20% |
| `mic_mount` | Flat back down | 29 × 12 × 10 | 2 cm³ | 3 perim / 20% |
| `cable_clip` | Flat, as modelled — **print 4** | 26 × 21 × 7 | 1 cm³ ea | 3 perim / 20% |
| `ball_cage` | Flat | 139 × 139 × 3 | 11 cm³ | 3 perim / 30% — thin, so let it cool |
| `speaker_gasket` | Flat | 54 × 54 × 2 | 2 cm³ | **TPU 95A, 100% infill** — or skip it and use silicone |

Everything fits a 180 × 180 mm bed except `base_shell` (178 × 174, so it *just*
fits) and `yoke` (157 × 108). A 220 mm bed is comfortable.

## Orientation matters in three places

**`yoke` — lay it on its back.** Printed standing up, the layer lines run across
the arms at exactly the plane where the head's weight tries to snap them off.
Lying down, the layers run along the arms and the part is several times
stronger in the direction it is loaded. This is the one orientation mistake that
will actually break your robot.

**`turntable` — race groove down.** The ball race is a 90° V, which is
self-supporting printed either way, but this orientation puts the race on the
build plate where it comes out smoothest, and the ring runs quieter for it.

**`faceplate` — front face down.** The bezel's outer chamfer is the only
overhang, it is 45°, and printing this way puts the visible surface against the
build plate.

## Supports

Only `head_back`, and only under the sensor brow — the part that carries the
camera and microphone above the face. It projects past the head's outer diameter
and its underside is a 45° ramp, which is self-supporting in principle, but the
tip of the ramp benefits from a little help.

In PrusaSlicer or OrcaSlicer, use **support enforcers** or *support on build
plate only* rather than everywhere. Support inside the head shell is a
half-hour of picking plastic out of boss holes for no benefit.

## Heat-set inserts

Nineteen printed bosses take brass inserts. They are worth the small extra
effort — they turn "you get about three assemblies before the threads strip"
into "this will outlast the robot".

1. Fit the insert tip to your iron, set it to **240 °C** for PETG (**220 °C**
   for PLA).
2. Rest the insert on the boss, square.
3. Press slowly, letting the plastic melt rather than forcing it. Two or three
   seconds.
4. Stop flush with the surface. Push in too far and you get a raised ring of
   displaced plastic around the hole; too shallow and the mating part rocks.
5. Let it cool before threading anything into it.

If an insert goes in crooked, heat it back out and try again rather than living
with it — a crooked insert cross-threads the screw and you will find out about
it at final assembly.

## Changing something

The model is parametric, so a dimension change is a rebuild rather than a
redesign:

```bash
cd hardware/cad
$EDITOR rocky_params.scad     # change what you need
./build_all.sh                # re-render everything and validate the meshes
./build_all.sh faceplate      # or just one part
```

The exports are **binary STL** — every slicer reads them, and they are about a
third the size of the ASCII form for the same geometry. Binary STL stores
float32 coordinates, which resolves to well under a micron at the size of these
parts; the printer's own resolution is four orders of magnitude coarser.

`build_all.sh` runs `check_stl.py` over every export and fails the build if any
mesh is not watertight, is non-manifold, has inconsistent winding, or has come
out in more than one piece. Several of those conditions produce a slice that
looks fine and prints wrong, so the check is worth reading rather than skipping.

The three groups of numbers marked **MEASURE** in `rocky_params.scad` are the
ones that depend on which revision of a part you were shipped:

- `disp_*` — the display's glass diameter, carrier size and hole pattern
- `sv_*` — the pan servo's body and mounting dimensions
- `msv_*` — the tilt servo's

Put calipers on yours before printing. Two minutes there against an afternoon of
reprinting a faceplate that does not fit.

## Checking your prints

Before assembly:

- **Ball race:** drop a 6 mm ball into the groove on both `base_deck` and
  `turntable`. It should sit in the V and roll freely, not bind and not rattle.
- **Heat-set bosses:** thread a screw into each one by hand. All nineteen.
- **Yoke:** hold it by the crossbar and flex the arms gently. They should feel
  stiff. If an arm flexes visibly, it was printed in the wrong orientation.
- **Faceplate:** offer the display up to the pocket. It should drop in with a
  little clearance. If it fouls, correct `disp_glass_d` rather than filing.
