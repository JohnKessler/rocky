#!/usr/bin/env python3
"""Draw Rocky's wiring diagrams, and the tables that go with them.

Everything comes from wiring_data.py, so the pictures and the tables in
docs/WIRING.md cannot disagree. Run it after changing anything electrical:

    python3 generate.py

Writes SVGs to hardware/img/ and markdown fragments to hardware/wiring/.
No third-party dependencies - the SVG is written by hand, which for diagrams
this regular is less code than configuring a library would be.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import wiring_data as W  # noqa: E402

OUT_IMG = Path(__file__).resolve().parents[1] / "img"
OUT_DOC = Path(__file__).resolve().parent

FONT = "ui-sans-serif, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"


# ---------------------------------------------------------------------------
# a very small SVG writer
# ---------------------------------------------------------------------------


class Svg:
    """Enough SVG to draw a wiring diagram and nothing more.

    Output is self-contained and carries its own light background: these get
    embedded as images (where `currentColor` would resolve to black on a dark
    page) and they get printed and pinned up next to the bench.
    """

    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        self.w, self.h = width, height
        self.title, self.desc = title, desc
        self.body: list[str] = []

    # -- primitives --------------------------------------------------------

    def rect(self, x, y, w, h, fill=W.PAPER, stroke=W.RULE, rx=6, sw=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def line(self, x1, y1, x2, y2, stroke=W.RULE, sw=1.5, dash=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="{cap}"{d}/>'
        )

    def path(self, points, stroke, sw=3.0, dash=None, arrow=False):
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mk = ' marker-end="url(#tip)"' if arrow else ""
        self.body.append(
            f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}" '
            f'stroke-linejoin="round" stroke-linecap="round"{da}{mk}/>'
        )

    def text(self, x, y, s, size=13, anchor="start", fill=W.INK, weight="500",
             font=FONT, opacity=1.0):
        self.body.append(
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'opacity="{opacity}">{html.escape(s)}</text>'
        )

    def dot(self, x, y, r=4, fill=W.INK):
        self.body.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>')

    # -- composites --------------------------------------------------------

    def block(self, x, y, w, h, name, sub="", accent=W.ACCENT):
        """A component box with a coloured spine on its left edge."""
        self.rect(x, y, w, h, fill=W.PANEL, stroke=W.RULE, rx=8)
        self.body.append(
            f'<path d="M {x} {y+8} L {x} {y+h-8}" stroke="{accent}" '
            f'stroke-width="4" stroke-linecap="round"/>'
        )
        ty = y + h / 2 + (0 if not sub else -6)
        self.text(x + 14, ty + 5, name, 14, weight="650")
        if sub:
            self.text(x + 14, ty + 22, sub, 11.5, fill=W.INK_SOFT, weight="400")

    def wire(self, points, net, label="", label_at=0.5, side="above", sw=3.4):
        """A run of wire, drawn in its real insulation colour."""
        colour = W.WIRE[net]
        self.path(points, colour, sw=sw)
        if label:
            i = max(0, min(len(points) - 2, int((len(points) - 1) * label_at)))
            (x1, y1), (x2, y2) = points[i], points[i + 1]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            dy = -9 if side == "above" else 17
            anchor = "middle"
            if x1 == x2:                       # vertical run: label beside it
                mx, my, dy, anchor = x1 + 9, (y1 + y2) / 2, 4, "start"
            self.text(mx, my + dy, label, 11.5, anchor=anchor, fill=W.INK_SOFT,
                      weight="500", font=MONO)

    def legend(self, x, y, entries, columns=1, gap=22, swatch=26):
        for i, (net, label) in enumerate(entries):
            col, row = i % columns, i // columns
            cx = x + col * 240
            cy = y + row * gap
            self.line(cx, cy, cx + swatch, cy, stroke=W.WIRE[net], sw=4)
            self.text(cx + swatch + 10, cy + 4, label, 11.5, fill=W.INK_SOFT, weight="500")

    # -- output ------------------------------------------------------------

    def render(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'width="{self.w}" height="{self.h}" role="img" '
            f'aria-label="{html.escape(self.desc)}">\n'
            f"  <title>{html.escape(self.title)}</title>\n"
            f"  <desc>{html.escape(self.desc)}</desc>\n"
            '  <defs><marker id="tip" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{W.INK}"/></marker></defs>\n'
            f'  <rect width="{self.w}" height="{self.h}" fill="{W.PAPER}"/>\n  '
            + "\n  ".join(self.body)
            + "\n</svg>\n"
        )

    def save(self, path: Path) -> Path:
        path.write_text(self.render())
        return path


# ---------------------------------------------------------------------------
# 1. the power tree
# ---------------------------------------------------------------------------


def diagram_power() -> Svg:
    s = Svg(1270, 610, "Rocky power distribution",
            "One 12V supply feeds a fuse and switch, then splits into a 5.1V "
            "regulator for the Raspberry Pi and a 6.0V regulator for the servo "
            "rail, with a common ground.")

    s.text(40, 44, "Power distribution", 21, weight="700")
    s.text(40, 68, "One cable to the desk. Everything else is made inside Rocky.",
           13, fill=W.INK_SOFT, weight="400")

    y_hi, y_lo = 150, 268
    s.block(40, y_hi - 30, 150, 60, "12V 5A supply", "2.1mm barrel", W.WIRE["12v"])
    s.block(250, y_hi - 26, 96, 52, "3A fuse", "", W.WIRE["12v"])
    s.block(400, y_hi - 26, 118, 52, "switch", "", W.WIRE["12v"])

    s.wire([(190, y_hi), (250, y_hi)], "12v")
    s.wire([(346, y_hi), (400, y_hi)], "12v")
    s.wire([(518, y_hi), (570, y_hi)], "12v", "12V", side="above")

    # the split: one branch stays high for the Pi, one drops for the servos
    s.dot(570, y_hi, 5, W.WIRE["12v"])
    s.wire([(570, y_hi), (570, y_lo), (630, y_lo)], "12v")
    s.wire([(570, y_hi), (630, y_hi)], "12v")

    # --- 5.1V branch, feeding the head -----------------------------------
    s.block(630, y_hi - 34, 190, 68, "5.1V regulator", "5A, set it before wiring",
            W.WIRE["5v"])
    s.wire([(820, y_hi), (900, y_hi)], "5v", "5.1V", side="above")
    s.block(900, y_hi - 34, 170, 68, "Raspberry Pi 5", "via USB-C", W.WIRE["5v"])

    # --- 6.0V branch, feeding the servo rail -----------------------------
    s.block(630, y_lo - 34, 190, 68, "6.0V regulator", "3A, set it before wiring",
            W.WIRE["6v"])
    s.wire([(820, y_lo), (900, y_lo)], "6v", "6.0V", side="above")
    s.block(900, y_lo - 34, 170, 68, "PCA9685 V+", "servo rail", W.WIRE["6v"])

    # smoothing capacitor, hung off the rail to the right of the driver
    cap_x = 1128
    s.wire([(1070, y_lo), (cap_x, y_lo), (cap_x, 330)], "6v", sw=3.0)
    s.line(cap_x - 26, 330, cap_x + 26, 330, W.INK, 3)
    s.line(cap_x - 26, 342, cap_x + 26, 342, W.INK, 3)
    s.text(cap_x + 34, 372, "470uF", 11.5, fill=W.INK_SOFT, font=MONO)
    s.text(cap_x + 34, 388, "polarity!", 10.5, fill=W.INK_SOFT, font=MONO)
    s.wire([(cap_x, 342), (cap_x, 470)], "gnd", sw=3.0)

    # --- servos hang off the driver's channels ---------------------------
    # Both servos sit above the ground rail; a block straddling it reads as
    # a short circuit even though it is only a drawing.
    s.block(900, 340, 170, 44, "pan servo", "", W.WIRE["signal"])
    s.block(900, 398, 170, 44, "tilt servo", "", W.WIRE["signal"])
    s.wire([(880, y_lo + 34), (880, 362), (900, 362)], "signal", sw=2.6)
    s.wire([(858, y_lo + 34), (858, 420), (900, 420)], "signal", sw=2.6)
    s.text(892, 336, "ch 0", 11, anchor="end", fill=W.INK_SOFT, font=MONO)
    s.text(892, 394, "ch 1", 11, anchor="end", fill=W.INK_SOFT, font=MONO)

    # --- common ground ----------------------------------------------------
    gy = 470
    s.line(40, gy, 1230, gy, W.WIRE["gnd"], 3.5)
    s.text(40, gy + 26, "Common ground", 13, weight="650")
    s.text(40, gy + 44,
           "The Pi's ground and the servo ground must be joined, or the PWM",
           12, fill=W.INK_SOFT, weight="400")
    s.text(40, gy + 62,
           "signal has no reference and the servos twitch continuously.",
           12, fill=W.INK_SOFT, weight="400")
    for x in (115, 480, 725, cap_x):
        s.dot(x, gy, 5, W.WIRE["gnd"])
    s.wire([(115, 180), (115, gy)], "gnd", sw=3.0)
    s.wire([(480, 176), (480, gy)], "gnd", sw=3.0)
    s.wire([(725, 302), (725, gy)], "gnd", sw=3.0)

    # --- the warning that matters ----------------------------------------
    s.rect(640, 528, 590, 62, fill="#fff7ed", stroke="#fdba74", rx=8)
    s.text(660, 552, "Set both regulator outputs before connecting anything", 12.5,
           weight="650", fill="#9a3412")
    s.text(660, 574, "5.05-5.15V and 5.9-6.1V. A module left set to 12V kills a Pi instantly.",
           11.5, weight="400", fill="#9a3412")

    s.legend(40, 552, [("12v", "12V input"), ("5v", "5.1V, Pi"),
                       ("6v", "6.0V, servos"), ("gnd", "ground")], columns=2)
    return s


# ---------------------------------------------------------------------------
# 2. the GPIO header
# ---------------------------------------------------------------------------


def diagram_gpio() -> Svg:
    rows = 20
    pitch = 34
    top = 150
    cx = 540                       # centre line of the header
    pin_w, pin_h = 74, 24

    s = Svg(1080, top + rows * pitch + 150, "Raspberry Pi 5 GPIO header",
            "The forty-pin header with the nine pins Rocky uses highlighted: "
            "four to the Qwiic SHIM and five to the I2S amplifier.")

    s.text(40, 44, "GPIO header", 21, weight="700")
    s.text(40, 68,
           "Nine pins used. Everything else stays free, which is why Rocky uses "
           "a Qwiic SHIM rather than a HAT.", 13, fill=W.INK_SOFT, weight="400")

    s.text(cx - pin_w - 10, top - 26, "odd", 11.5, anchor="end",
           fill=W.INK_SOFT, font=MONO)
    s.text(cx + pin_w + 10, top - 26, "even", 11.5, fill=W.INK_SOFT, font=MONO)
    s.rect(cx - pin_w - 14, top - 16, (pin_w + 14) * 2, rows * pitch + 4,
           fill="#eef2f7", stroke=W.RULE, rx=10)

    for row in range(rows):
        y = top + row * pitch
        for side in (-1, 1):
            pin = W.GPIO_HEADER[row * 2 + (0 if side < 0 else 1)]
            x = cx - pin_w if side < 0 else cx
            used = bool(pin.use)
            colour = W.WIRE.get(pin.net, W.RULE) if used else W.RULE
            s.rect(x + (2 if side < 0 else 0), y, pin_w - 2, pin_h,
                   fill=colour if used else "#ffffff",
                   stroke=colour if used else "#dbe2ec", rx=5, sw=1.4)
            s.text(x + pin_w / 2, y + 17, str(pin.number), 12.5,
                   anchor="middle", weight="700",
                   fill="#ffffff" if used else W.INK_SOFT)

            # the name, just outside the header body
            nx = cx - pin_w - 24 if side < 0 else cx + pin_w + 24
            s.text(nx, y + 17, pin.name, 12, anchor="end" if side < 0 else "start",
                   fill=W.INK if used else "#9aa7b8",
                   weight="600" if used else "400", font=MONO)

            if used:
                # Leader out to whatever the pin connects to. It has to start
                # clear of the pin name or it draws a line through the text;
                # the name is monospaced, so its width is predictable.
                name_w = len(pin.name) * 7.25
                lx = 250 if side < 0 else 836
                if side < 0:
                    s.line(nx - name_w - 14, y + 12, lx, y + 12, colour, 2.0)
                    s.text(lx - 12, y + 16, pin.use, 12, anchor="end",
                           weight="600", fill=colour)
                else:
                    s.line(nx + name_w + 14, y + 12, lx, y + 12, colour, 2.0)
                    s.text(lx + 12, y + 16, pin.use, 12, weight="600", fill=colour)

    bottom = top + rows * pitch + 40
    s.legend(40, bottom, [("3v3", "3V3 logic"), ("5v", "5V"),
                          ("gnd", "ground"), ("i2c_sda", "I2C SDA / I2S clocks"),
                          ("i2c_scl", "I2C SCL")], columns=2)
    s.text(600, bottom - 2, "Pin 1 is the corner nearest the microSD slot.",
           12, fill=W.INK_SOFT, weight="400")
    s.text(600, bottom + 20,
           "Leave the amplifier's GAIN and SD pins unconnected: floating gives",
           12, fill=W.INK_SOFT, weight="400")
    s.text(600, bottom + 38,
           "9dB and mono (L+R)/2, which is what one speaker wants.",
           12, fill=W.INK_SOFT, weight="400")
    return s


# ---------------------------------------------------------------------------
# 3. what connects to what, and what crosses the rotating joint
# ---------------------------------------------------------------------------


def diagram_interconnect() -> Svg:
    """Every board and every wire, split by which half of the robot it is in.

    The layout is arranged so no run passes through a block: the two halves
    each keep clear vertical channels at x = 90 and x = 1150/1190, and the I2C
    trio drops through the gap between the left column and the Pi.
    """
    s = Svg(1260, 900, "Rocky interconnect",
            "Every board in Rocky and the wires between them, split into the "
            "head and the base, with the eleven-conductor harness that crosses "
            "the rotating pan joint.")

    s.text(40, 44, "What connects to what", 21, weight="700")
    s.text(40, 68,
           "The head turns. Every wire between the two halves has to survive "
           "that, thousands of times a week.", 13, fill=W.INK_SOFT, weight="400")

    # --- the two halves ---------------------------------------------------
    s.rect(40, 100, 1180, 296, fill="#f7f9fc", stroke=W.RULE, rx=12)
    s.text(60, 126, "HEAD", 12, fill=W.INK_SOFT, weight="700")
    s.text(60, 144, "turns with the pan servo", 11, fill=W.INK_SOFT, weight="400")

    s.rect(40, 560, 1180, 290, fill="#f7f9fc", stroke=W.RULE, rx=12)
    s.text(60, 586, "BASE", 12, fill=W.INK_SOFT, weight="700")
    s.text(60, 604, "fixed to the desk", 11, fill=W.INK_SOFT, weight="400")

    # --- head -------------------------------------------------------------
    s.block(150, 166, 190, 58, "round display", "DSI ribbon", W.WIRE["data"])
    s.block(150, 252, 190, 58, "Camera Module 3", "CSI ribbon", W.WIRE["data"])
    s.block(150, 330, 190, 52, "USB microphone", "", W.WIRE["data"])
    s.block(480, 196, 220, 96, "Raspberry Pi 5", "the only computer", W.ACCENT)
    s.block(850, 166, 200, 58, "MAX98357A amp", "I2S in, 3W out", W.WIRE["signal"])
    s.block(850, 252, 200, 58, "Qwiic SHIM", "I2C off the header", W.WIRE["i2c_sda"])
    s.block(850, 330, 200, 52, "tilt servo", "channel 1", W.WIRE["signal"])

    # --- base -------------------------------------------------------------
    s.block(150, 640, 190, 58, "pan servo", "channel 0", W.WIRE["signal"])
    s.block(480, 620, 220, 96, "PCA9685", "16 channels, 2 used", W.ACCENT)
    s.block(850, 640, 200, 58, "40mm speaker", "fires down", W.WIRE["audio"])
    s.block(150, 752, 190, 52, "5.1V regulator", "feeds the Pi", W.WIRE["5v"])
    s.block(480, 752, 220, 52, "6.0V regulator", "feeds the servos", W.WIRE["6v"])

    # --- inside the head ---------------------------------------------------
    s.wire([(340, 195), (410, 195), (410, 228), (480, 228)], "data", "DSI", sw=2.6)
    s.wire([(340, 281), (410, 281), (410, 260), (480, 260)], "data", "CSI", sw=2.6)
    s.wire([(340, 356), (440, 356), (440, 284), (480, 284)], "data", "USB", sw=2.6)
    s.wire([(700, 216), (780, 216), (780, 195), (850, 195)], "signal",
           "I2S + 5V", sw=2.6)
    s.wire([(700, 260), (790, 260), (790, 281), (850, 281)], "i2c_sda", "I2C", sw=2.6)

    # --- inside the base ---------------------------------------------------
    s.wire([(480, 660), (340, 660)], "signal", "ch 0", sw=2.6)
    s.wire([(590, 752), (590, 716)], "6v", "V+", sw=2.6)

    # --- the joint ---------------------------------------------------------
    jy = 478
    s.line(40, jy, 1220, jy, W.INK_SOFT, 2.0, dash="10 7")
    s.rect(420, jy - 26, 420, 52, fill="#fff7ed", stroke="#fdba74", rx=9)
    s.text(630, jy - 5, "THE ROTATING PAN JOINT", 12.5, anchor="middle",
           weight="700", fill="#9a3412")
    s.text(630, jy + 14, "11 conductors cross here, all in silicone wire",
           11.5, anchor="middle", weight="400", fill="#9a3412")

    # --- the six runs that cross -------------------------------------------
    # No inline label on the crossings; the caption under the joint names them.
    s.wire([(480, 240), (90, 240), (90, 778), (150, 778)], "5v", sw=3.2)
    for x, net in ((355, "i2c_sda"), (382, "i2c_scl"), (409, "3v3")):
        s.wire([(850, 300), (x, 300), (x, 600), (460, 600), (460, 646), (480, 646)],
               net, sw=2.4)
    s.wire([(1050, 356), (1150, 356), (1150, 730), (720, 730), (720, 700), (700, 700)],
           "signal", sw=3.2)
    s.wire([(1050, 195), (1190, 195), (1190, 669), (1050, 669)], "audio", sw=3.2)

    # Captions for the crossings. The two on the right are stacked because
    # their channels are only 40px apart and the text is wider than that.
    for x, dy, caption in ((90, 46, "5.1V + GND"), (382, 46, "SDA / SCL / 3V3"),
                           (1088, 46, "tilt x3"), (1088, 64, "speaker +/-")):
        s.text(x, jy + dy, caption, 10.5, anchor="middle", fill=W.INK_SOFT,
               weight="600", font=MONO)

    s.legend(40, 872, [("data", "ribbon and USB"), ("signal", "I2S and PWM"),
                       ("i2c_sda", "I2C"), ("audio", "speaker"),
                       ("5v", "5.1V"), ("6v", "6.0V")], columns=3)
    return s


# ---------------------------------------------------------------------------
# markdown fragments, so the tables cannot drift from the pictures
# ---------------------------------------------------------------------------


def markdown_tables() -> str:
    where = {d.key: d for d in W.DEVICES}
    lines = ["<!-- Generated by hardware/wiring/generate.py. Do not edit by hand. -->", ""]

    lines += ["### Every connection", "",
              "| From | To | Carries | Wire | Note |",
              "|------|-----|---------|------|------|"]
    for link in W.LINKS:
        lines.append(
            f"| {where[link.frm].name} | {where[link.to].name} | "
            f"{link.label or link.net} | {link.gauge or '—'} | {link.note or '—'} |"
        )

    lines += ["", f"### The pan-joint harness ({len(W.HARNESS)} conductors)", "",
              "| Conductor | Gauge | Purpose |", "|-----------|-------|---------|"]
    for name, gauge, purpose in W.HARNESS:
        lines.append(f"| {name} | {gauge} | {purpose} |")

    used = [p for p in W.GPIO_HEADER if p.use]
    lines += ["", f"### GPIO pins in use ({len(used)} of 40)", "",
              "| Pin | Signal | Goes to |", "|-----|--------|---------|"]
    for pin in used:
        lines.append(f"| {pin.number} | {pin.name} | {pin.use} |")

    return "\n".join(lines) + "\n"


def main() -> int:
    problems = W.validate()
    if problems:
        print("wiring data is inconsistent:")
        for p in problems:
            print(f"  - {p}")
        return 1

    OUT_IMG.mkdir(parents=True, exist_ok=True)
    for name, fn in (("power", diagram_power), ("gpio", diagram_gpio),
                     ("interconnect", diagram_interconnect)):
        path = fn().save(OUT_IMG / f"wiring-{name}.svg")
        print(f"  {path.name}  {path.stat().st_size:,} bytes")

    doc = OUT_DOC / "tables.md"
    doc.write_text(markdown_tables())
    print(f"  {doc.name}  {doc.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
