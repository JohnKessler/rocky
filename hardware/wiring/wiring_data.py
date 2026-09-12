"""Rocky's electrical connections, as data.

Both the diagrams and the tables in docs/WIRING.md are generated from this
file. A wire that exists here appears in both; one that does not, in neither.
That is the whole point - a wiring table and a wiring diagram that disagree
are worse than either alone, because you cannot tell which one lied.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- palette ---------------------------------------------------------------
# Wire colours are the real insulation colours, so the picture matches the
# bench. Everything structural is ink on paper, because build guides get
# printed and pinned up.

INK = "#1b2430"
INK_SOFT = "#5b6878"
PAPER = "#ffffff"
PANEL = "#f2f5f9"
RULE = "#c9d3e0"
ACCENT = "#0f7b8a"

WIRE = {
    "12v": "#c2410c",      # orange - the raw supply
    "5v": "#dc2626",       # red
    "6v": "#b91c1c",       # dark red - servo rail
    "3v3": "#f59e0b",      # amber
    "gnd": "#111827",      # black
    "signal": "#2563eb",   # blue - I2S and PWM
    "i2c_sda": "#2563eb",
    "i2c_scl": "#eab308",
    "audio": "#16a34a",    # green - speaker
    "data": "#7c3aed",     # violet - ribbon cables
}


@dataclass(frozen=True)
class Pin:
    number: int
    name: str
    use: str = ""          # empty means Rocky does not use this pin
    net: str = ""


@dataclass(frozen=True)
class Link:
    """One connection, from somewhere to somewhere."""

    frm: str
    to: str
    net: str
    label: str = ""
    gauge: str = ""
    note: str = ""


@dataclass(frozen=True)
class Device:
    key: str
    name: str
    where: str             # "base" or "head"
    note: str = ""


# --- the 40-pin header -----------------------------------------------------
# Physical pin order: odd numbers down the left, even down the right.
# Only the pins Rocky actually uses carry a `use`.

GPIO_HEADER: list[Pin] = [
    Pin(1, "3V3", "Qwiic SHIM", "3v3"),
    Pin(2, "5V"),
    Pin(3, "GPIO2 / SDA1", "Qwiic SHIM", "i2c_sda"),
    Pin(4, "5V", "amplifier Vin", "5v"),
    Pin(5, "GPIO3 / SCL1", "Qwiic SHIM", "i2c_scl"),
    Pin(6, "GND", "amplifier GND", "gnd"),
    Pin(7, "GPIO4"),
    Pin(8, "GPIO14 / TXD"),
    Pin(9, "GND", "Qwiic SHIM", "gnd"),
    Pin(10, "GPIO15 / RXD"),
    Pin(11, "GPIO17"),
    Pin(12, "GPIO18 / PCM_CLK", "amplifier BCLK", "signal"),
    Pin(13, "GPIO27"),
    Pin(14, "GND"),
    Pin(15, "GPIO22"),
    Pin(16, "GPIO23"),
    Pin(17, "3V3"),
    Pin(18, "GPIO24"),
    Pin(19, "GPIO10 / MOSI"),
    Pin(20, "GND"),
    Pin(21, "GPIO9 / MISO"),
    Pin(22, "GPIO25"),
    Pin(23, "GPIO11 / SCLK"),
    Pin(24, "GPIO8 / CE0"),
    Pin(25, "GND"),
    Pin(26, "GPIO7 / CE1"),
    Pin(27, "GPIO0 / ID_SD"),
    Pin(28, "GPIO1 / ID_SC"),
    Pin(29, "GPIO5"),
    Pin(30, "GND"),
    Pin(31, "GPIO6"),
    Pin(32, "GPIO12"),
    Pin(33, "GPIO13"),
    Pin(34, "GND"),
    Pin(35, "GPIO19 / PCM_FS", "amplifier LRC", "signal"),
    Pin(36, "GPIO16"),
    Pin(37, "GPIO26"),
    Pin(38, "GPIO20"),
    Pin(39, "GND"),
    Pin(40, "GPIO21 / PCM_DOUT", "amplifier DIN", "signal"),
]

# --- devices ---------------------------------------------------------------

DEVICES: list[Device] = [
    Device("psu", "12V 5A supply", "base", "one cable to the desk"),
    Device("fuse", "3A fuse", "base"),
    Device("switch", "power switch", "base"),
    Device("buck_a", "5.1V 5A regulator", "base", "set before connecting"),
    Device("buck_b", "6.0V 3A regulator", "base", "set before connecting"),
    Device("pi", "Raspberry Pi 5", "head"),
    Device("shim", "Qwiic SHIM", "head"),
    Device("amp", "MAX98357A amplifier", "head", "beside the Pi"),
    Device("speaker", "40mm speaker", "base"),
    Device("pca", "PCA9685 servo driver", "base"),
    Device("cap", "470uF capacitor", "base", "across the servo rail"),
    Device("pan", "pan servo", "base", "channel 0"),
    Device("tilt", "tilt servo", "head", "channel 1"),
    Device("display", "round display", "head"),
    Device("camera", "Camera Module 3", "head"),
    Device("mic", "USB microphone", "head"),
]

DEVICE_BY_KEY = {d.key: d for d in DEVICES}

# --- connections -----------------------------------------------------------

LINKS: list[Link] = [
    # power distribution
    Link("psu", "fuse", "12v", "12V", "18 AWG"),
    Link("fuse", "switch", "12v", "12V", "18 AWG"),
    Link("switch", "buck_a", "12v", "12V", "18 AWG"),
    Link("switch", "buck_b", "12v", "12V", "18 AWG"),
    Link("buck_a", "pi", "5v", "5.1V to USB-C", "20 AWG",
         "crosses the pan joint"),
    Link("buck_b", "pca", "6v", "6.0V to V+", "20 AWG"),
    Link("buck_b", "cap", "6v", "across V+", ""),
    # I2C, down from the head to the base
    Link("pi", "shim", "i2c_sda", "GPIO2 / SDA", ""),
    Link("shim", "pca", "i2c_sda", "SDA", "26 AWG", "crosses the pan joint"),
    Link("shim", "pca", "i2c_scl", "SCL", "26 AWG", "crosses the pan joint"),
    Link("shim", "pca", "3v3", "3V3 logic", "26 AWG", "crosses the pan joint"),
    # audio
    Link("pi", "amp", "signal", "I2S: BCLK, LRC, DIN", "26 AWG"),
    Link("pi", "amp", "5v", "5V + GND", "26 AWG"),
    Link("amp", "speaker", "audio", "4 ohm, 3W", "22 AWG", "crosses the pan joint"),
    # servos
    Link("pca", "pan", "signal", "channel 0", ""),
    Link("pca", "tilt", "signal", "channel 1", "26 AWG", "crosses the pan joint"),
    # ribbon cables, entirely inside the head
    Link("pi", "display", "data", "DSI, 22 to 15 pin", "", "CAM/DISP 1"),
    Link("pi", "camera", "data", "CSI, 22 to 15 pin", "", "CAM/DISP 0"),
    Link("pi", "mic", "data", "USB", ""),
]

# --- the harness that crosses the rotating joint ---------------------------

HARNESS: list[tuple[str, str, str]] = [
    ("5.1V", "20 AWG", "Pi supply"),
    ("GND", "20 AWG", "Pi supply return"),
    ("GND", "20 AWG", "signal ground"),
    ("SDA", "26 AWG", "I2C to the servo driver"),
    ("SCL", "26 AWG", "I2C to the servo driver"),
    ("3V3", "26 AWG", "I2C logic level"),
    ("Tilt signal", "26 AWG", "PWM to the tilt servo"),
    ("Tilt V+", "26 AWG", "6V to the tilt servo"),
    ("Tilt GND", "26 AWG", "tilt servo return"),
    ("Speaker +", "22 AWG", "amplifier output, head to base"),
    ("Speaker -", "22 AWG", "amplifier output return"),
]

# --- checks the generator runs before drawing anything ---------------------

def validate() -> list[str]:
    """Catch the mistakes that would otherwise be drawn confidently."""
    problems: list[str] = []
    keys = {d.key for d in DEVICES}

    for link in LINKS:
        for end in (link.frm, link.to):
            if end not in keys:
                problems.append(f"link {link.frm}->{link.to} names unknown device {end!r}")
        if link.net not in WIRE:
            problems.append(f"link {link.frm}->{link.to} uses unknown net {link.net!r}")

    numbers = [p.number for p in GPIO_HEADER]
    if numbers != list(range(1, 41)):
        problems.append("GPIO header is not 40 pins in order")

    # Anything with one end in the head and the other in the base physically
    # has to cross the rotating joint, whether or not anyone remembered to say
    # so. This check exists because the first draft put the amplifier in the
    # base while the Pi was in the head, which quietly sent I2S across a
    # flexing harness that the documentation said carried nine conductors.
    where = {d.key: d.where for d in DEVICES}
    for link in LINKS:
        if where.get(link.frm) != where.get(link.to):
            if "pan joint" not in link.note:
                problems.append(
                    f"link {link.frm}->{link.to} ({link.label}) spans head and base "
                    "but is not marked as crossing the pan joint"
                )
    crossing = [l for l in LINKS if "pan joint" in l.note]
    if len(crossing) != 6:
        problems.append(f"expected 6 links across the joint, found {len(crossing)}")
    if len(HARNESS) != 11:
        problems.append(f"harness should carry 11 conductors, lists {len(HARNESS)}")

    # Four pins to the Qwiic SHIM, five to the amplifier.
    used = [p for p in GPIO_HEADER if p.use]
    if len(used) != 9:
        problems.append(f"expected 9 used header pins, found {len(used)}")

    return problems
