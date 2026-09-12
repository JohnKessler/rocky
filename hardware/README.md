# Regenerating the graphics

Every picture in the guides is generated from the same source as the thing it
depicts, so a figure cannot quietly go stale. Nothing here is hand-drawn and
nothing needs to be redrawn when a dimension changes.

```
rocky_params.scad ──► part .scad ──► .stl ──────────┐
                                                     ├─► assembly_guide.scad ──► .png + .legend
                      components.scad ──────────────┘

wiring_data.py ──► generate.py ──► wiring-*.svg
               └─────────────────► tables.md

                                   update_docs.py ──► docs/ASSEMBLY.md, docs/WIRING.md
```

## The whole chain

```bash
cd hardware/cad && ./build_all.sh        # 11 parts, each mesh validated
./render_figures.sh                      # 9 figures + their legends
cd .. && python3 wiring/generate.py      # 3 diagrams + the tables
python3 update_docs.py                   # fold both into the markdown
```

`build_all.sh` and `render_figures.sh` need OpenSCAD on `PATH`. `generate.py`
and `update_docs.py` are plain Python with no dependencies.

## Assembly figures

`cad/assembly_guide.scad` imports the exported STLs and the stand-in components
in `cad/components.scad`, then draws one figure per assembly stage. Which
figures exist, and the camera for each, is the `FIGURES` list at the top of
`cad/render_figures.sh`:

```
"stage4|1800 1250|0,0,70,54,0,205,470|1.0|80"
 view   size       camera                explode  label distance
```

Callouts are numbered discs with leaders, not text in the model — text at model
scale is unreadable at some camera distances and illegible at others. Each
`callout()` echoes its own caption, `render_figures.sh` captures those into
`img/assembly-<view>.legend`, and `update_docs.py` writes them under the image
as a numbered key. The numbers in the picture and the words in the document
therefore come from one place and cannot disagree.

## Wiring diagrams

`wiring/wiring_data.py` is the single description of Rocky's electrics: the
devices, which half of the robot each lives in, every link between them, and
the conductors that cross the pan joint. `generate.py` renders it three ways
(power, GPIO header, interconnect) as hand-built SVG, and writes the same data
out as markdown tables.

`validate()` runs before anything is drawn and refuses to generate on a
contradiction. It checks that every link's endpoints exist, that no GPIO pin is
claimed twice, and — the rule that earns its keep — that any link joining a
device in the head to a device in the base is marked as crossing the pan joint.
That last check caught a real design error: the amplifier sat in the base while
the Pi sat in the head, which quietly put a 3 MHz I²S clock across a harness
that flexes every time Rocky turns. The amplifier moved into the head.

## Markers

`update_docs.py` fills the region between marker pairs in `docs/*.md`:

```markdown
<!-- figure:stage4 -->
<!-- /figure -->

<!-- wiring:power -->
<!-- /wiring -->

<!-- tables:harness -->
<!-- /tables -->
```

Anything between a pair is overwritten. Edit the source, re-run the chain, and
never edit inside the markers by hand.
