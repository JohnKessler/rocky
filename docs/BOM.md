# Bill of materials

Everything needed to build one Rocky. Roughly **£330–£420 / $420–$530**
depending on which display and speech engine you choose and what you already
have in a drawer.

> **Check part numbers before you order.** SKUs and prices move, and vendors
> revise boards without renaming them. The **Specification** column is the part
> that actually matters — anything meeting it will work, and the code and the
> printed parts are parameterised so substitutions are a number change rather
> than a redesign. Where a dimension feeds the CAD, the parameter name is given
> so you know what to edit.
>
> Vendor SKUs were last checked on **12 September 2026**. Three were wrong at
> that point and are corrected below: the Qwiic cable had been retired, the
> speaker had been relabelled and had lost its colour-coded leads, and the
> microphone that was suggested does not fit the printed mount.

Vendor shorthand: **SF** SparkFun · **AF** Adafruit · **RPi** Raspberry Pi (or
any approved reseller) · **WS** Waveshare · **\*** generic, buy anywhere.

---

## 1. Brain

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 1.1 | Raspberry Pi 5, 8 GB | 8 GB matters: the face renderer, the detector and local speech all want headroom. 4 GB works if you use cloud speech. | RPi | £75 |
| 1.2 | Active Cooler for Pi 5 | The official one. Rocky's head is a closed box and the Pi will throttle without it. Its height sets `pi_stack_h`. | RPi | £5 |
| 1.3 | microSD card, 64 GB, A2 | A2 rating, not just "class 10". Cheap cards make boot and model loading miserable. | \* | £10 |
| 1.4 | *(optional)* NVMe HAT + 256 GB SSD | Only if you want local Whisper models to load quickly. Adds height in the head — check clearance first. | RPi | £45 |

## 2. Face

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 2.1 | **Option A —** 4″ round DSI display, 720×720 | Round IPS, MIPI-DSI, 60 Hz. This is the one the faceplate is drawn for. Measure the glass diameter and the carrier PCB and set `disp_glass_d`, `disp_pcb_w`, `disp_hole_dx/dy` before printing. | WS | £45 |
| 2.2 | **Option B —** Raspberry Pi Touch Display 2 | 5″, 720×1280, officially supported so the driver situation is boring. Not round: reprint `faceplate.scad` with `circular_mask=false` and a rectangular window, or accept a letterboxed face. Pick this if Option A's overlay fights your kernel. | RPi | £55 |
| 2.3 | DSI FPC cable, 22-pin 0.5 mm → 15-pin 1 mm, 200 mm | **Pi 5 only.** The Pi 5's connectors are the smaller 22-pin format; a standard 15-pin ribbon will not fit. Must be the *display* cable — the camera one is not interchangeable. | AF 5821 / WS | £5 |

## 3. Eyes

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 3.1 | Raspberry Pi Camera Module 3 **Wide** | 12 MP IMX708, autofocus, 102° × 67° FOV. Vendors advertise this lens as **120°**, which is the *diagonal* figure; 102° × 67° is the same lens measured horizontally and vertically, and horizontal is what the tracking maths wants. The wide version is the right call: the standard lens's 66° is too narrow to find you when Rocky is looking somewhere else. FOV feeds `vision.h_fov_deg` / `v_fov_deg` — get these wrong and Rocky consistently mis-aims when it turns to look at you. | RPi / AF 5658 | £30 |
| 3.2 | Camera FPC cable, 22-pin → 15-pin, 200 mm | Again Pi 5 specific, and again *not* the display cable. | AF 5818 / WS | £5 |

## 4. Motion

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 4.1 | Pan servo — standard size, metal gear, digital | 40.6 × 20 × 37 mm, ≥ 5 kg·cm at 6 V, 180°. A quiet digital servo is worth the extra: this one sits 30 cm from your ear. Hitec HS-5485HB or Savöx SH-0255MG are pleasant; MG996R works and is noticeably louder. Dimensions feed `sv_*`. | SF / \* | £18 |
| 4.2 | Tilt servo — micro, metal gear | 23 × 12.2 × 22.5 mm, ≥ 2 kg·cm. MG90S or Hitec HS-5065MG. **A standard servo will not fit** beside the Pi in the head — the head is sized around a micro here. Dimensions feed `msv_*`. | SF / \* | £8 |
| 4.3 | PCA9685 16-channel PWM/servo driver | I²C, 12-bit, external servo supply via screw terminal. Only two channels are used; the rest are there when you want to add something. | AF 815 / SF | £12 |
| 4.4 | Qwiic SHIM for Raspberry Pi | Slips over the GPIO header and gives you I²C on a connector **without covering the header**, which is what leaves GPIO 18/19/21 free for the amplifier. | SF DEV-15794 | £2 |
| 4.5 | Qwiic cable, 4-pin → female jumpers | Connects the SHIM to the PCA9685's I²C header. Wires are red/black/blue/yellow, matching the table in [WIRING.md](WIRING.md). **CAB-14988 (150 mm) is retired** — the current equivalent is the *Flexible Qwiic Cable – Female Jumper (4-pin)*, CAB-17261. Check the length suits; anything from 100–200 mm is fine. | SF CAB-17261 | £2 |
| 4.6 | Chrome steel balls, 6 mm × 30 | The slew ring. Buy 30 for 24 positions — you will lose some. 6 mm airsoft BBs work but wear faster and are noisier. | \* | £4 |
| 4.7 | 623ZZ bearing (3 × 10 × 4 mm) | The tilt idler pivot. | \* | £1 |
| 4.8 | 470 µF 10 V electrolytic capacitor | Across the servo rail at the PCA9685. Not optional — servo inrush browns out the I²C bus without it, and the symptom is Rocky freezing mid-move for no visible reason. | \* | £1 |

## 5. Voice

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 5.1 | MAX98357A I²S class-D amplifier | 3 W into 4 Ω, I²S in. The Pi 5 has no headphone jack, so this is required rather than optional. Mounts in the **head**, beside the Pi — that way the pan joint carries two analogue speaker conductors instead of five digital ones. | AF 3006 / SF | £6 |
| 5.2 | Speaker, 40 mm, 4 Ω, 3–5 W | Mounts in the **base** floor, firing down into the gap the legs hold open. Frame diameter feeds `spk_d`; the body is about 20 mm deep. Adafruit now lists 3968 as **5 W** where distributors still print 3 W — same part, and the extra headroom is harmless since the amplifier only delivers 3.2 W. The January 2024 revision has a concave cone and **no longer ships red/black leads**, so identify polarity yourself rather than by colour. | AF 3968 / \* | £4 |
| 5.3 | USB microphone, **cylindrical body ~14 mm** | Anything that enumerates as a USB audio input, but `mic_mount.scad` is a round saddle: the body must be a cylinder, and its diameter feeds `usb_mic_d`. A gooseneck or stick mic suits. **A flat USB-stick mic will not fit** — Adafruit's Mini USB Microphone (3367) is 22.2 × 18.3 × 7.0 mm and has no round body to clamp; use one only if you redraw the saddle as a rectangular pocket. A small far-field array (ReSpeaker USB Mic Array, or similar) is a large improvement over a single capsule if Rocky sits more than a metre away, and is a separate mounting problem again. | \* | £8–£55 |
| 5.4 | USB-A right-angle adapter or short extension | The Pi's ports face sideways inside the head; a straight plug fouls the shell. | \* | £3 |

## 6. Power

Rocky takes **one 12 V input** and makes its own rails. Two wall warts on a desk
is an unforced ugliness, and feeding the Pi 5 from a bare 5 V supply makes it
throttle USB current and complain.

| # | Part | Specification | Where | ~Cost |
|---|------|---------------|-------|-------|
| 6.1 | 12 V 5 A PSU, 2.1 mm centre-positive barrel | 60 W. 3 A is enough in practice; 5 A means the servos never sag the rail. | \* | £12 |
| 6.2 | Step-down regulator, 5.1 V ≥ 5 A | For the Pi. Pololu D36V50F5 or equivalent. **5.1 V, not 5.0** — cable drop at 4 A is real and the Pi 5 is fussy about it. Hole spacing feeds `buck_hole_dx`. | Pololu / \* | £18 |
| 6.3 | Step-down regulator, 6 V ≥ 3 A | For the servo rail. 6 V gets meaningfully more torque and speed than 5 V out of the same servos. | Pololu / \* | £10 |
| 6.4 | USB-C breakout or a sacrificial USB-C cable | To feed the Pi's USB-C input from the 5.1 V rail. A cut-down cable is fine; solder to the 5 V and GND pairs. | \* | £4 |
| 6.5 | Panel-mount 2.1 mm DC jack | Base wall, cutout is `barrel_d`. | \* | £2 |
| 6.6 | 12 mm panel-mount latching switch | Base wall, cutout is `switch_d`. | \* | £3 |
| 6.7 | Inline fuse holder + 3 A fuse | On the 12 V input. A shorted servo lead behind a 5 A supply is a fire, not a fault. | \* | £2 |

## 7. Fasteners

Buy an M2/M2.5/M3 assortment and a heat-set insert kit; it is cheaper than
buying each length and you will use the rest.

| # | Part | Quantity | Notes |
|---|------|----------|-------|
| 7.1 | M3 heat-set inserts, 5.0 mm OD × 4.0 mm | 20 | Pilot bores are `m3_insert_d`. |
| 7.2 | M2.5 heat-set inserts, 3.5 mm OD × 4.0 mm | 16 | Display, Pi, camera, brow window. |
| 7.3 | M3 socket cap screws, 8 / 12 / 16 / 20 mm | 10 each | |
| 7.4 | M2.5 screws, 6 / 10 / 16 mm | 10 each | |
| 7.5 | M2 self-tapping screws, 8 mm | 10 | Tilt servo ears, into printed bosses. |
| 7.6 | M3 × 20 socket cap screw | 1 | The tilt pivot — it passes through the 623ZZ bearing. |
| 7.7 | M8 washers | 10–20 | Head trim weights. How many is a balance question, not a fixed number. |
| 7.8 | Self-adhesive felt pads, 12 mm | 5 | Under the legs. |
| 7.9 | Silicone wire, 20 AWG and 26 AWG | 2 m each | 20 AWG for power, 26 AWG for signals. Silicone, not PVC — the pan joint flexes this wire thousands of times. |
| 7.10 | Heat-shrink, JST-XH connectors, cable ties | assorted | |

## 8. Printing and consumables

| # | Item | Notes |
|---|------|-------|
| 8.1 | PETG filament, ~600 g | Preferred. The parts hold heat-set inserts better than PLA and will not sag in a warm room or a car. |
| 8.2 | PLA, ~600 g | Fine, prints easier, but do not leave Rocky on a sunny windowsill. |
| 8.3 | TPU 95A, a few grams | The speaker gasket only. Skip it and use a smear of neutral-cure silicone instead. |
| 8.4 | PTFE or lithium grease | The slew ring. A little, on the balls. |

## 9. Tools

Soldering iron with a heat-set insert tip (a cheap conical tip works), side
cutters, hex drivers, a small screwdriver set, digital calipers, multimeter.
**Calipers are the one you should not skip** — three groups of numbers in
`rocky_params.scad` are marked MEASURE because vendors ship revisions, and
measuring them takes two minutes against an afternoon of reprinting.

---

## What matters and what does not

**Worth the money**

- *A quiet pan servo.* You will hear this one every time Rocky turns. It is the
  difference between a robot you keep on your desk and one you move to a shelf.
- *The wide camera lens.* A narrow lens means Rocky loses you constantly.
- *A decent microphone.* Speech recognition quality is dominated by the
  microphone, not the model. A far-field array is the single biggest upgrade
  available to this build.

**Do not bother**

- *An expensive display.* Rocky's face is flat colour on black; panel quality is
  invisible at this content. Buy on size and driver support.
- *Servos above about 8 kg·cm.* The head is light and balanced on its tilt axis.
  Extra torque buys noise and current draw, not capability.
- *NVMe*, unless you are running local Whisper and impatient.

**Sensible substitutions**

- **Pi 4 instead of Pi 5.** Works. Use the plain 15-pin camera and display
  cables (items 2.3 and 3.2 become unnecessary), and expect the face to run
  closer to 25 fps than 45. Set `face.fps` down to match.
- **Cloud speech instead of local.** Set `audio.stt.backend` and
  `audio.tts.backend` and skip the Whisper and Piper installs. Lower latency,
  better voices, but Rocky stops working when your internet does.
- **Any I²C servo driver.** Nothing depends on the PCA9685 specifically beyond
  `rocky/motion/servo.py`, which is about forty lines.

**Do not substitute**

- **The tilt servo for a standard-size one.** It will not fit. The head is
  dimensioned around a micro servo sitting beside the Pi, and that is what makes
  the head small enough to balance on its own tilt axis.
