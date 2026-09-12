/* Rocky's face, drawn in the browser.
 *
 * This is a deliberate mirror of layout() in rocky/face/renderer.py. The
 * websocket sends the same eighteen-number parameter vector the on-device
 * renderer draws from, so what you see here is Rocky's actual face and not an
 * illustration of it. If you change the geometry in Python, change it here
 * too - the two are meant to stay in step.
 */

const VIEW = 720;

const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);

export const DEFAULT_PARAMS = {
  eye_open_l: 1, eye_open_r: 1, eye_arc: 0, eye_squint: 0, eye_width: 1,
  pupil_x: 0, pupil_y: 0, pupil_scale: 1,
  brow_lift: 0, brow_angle: 0, brow_show: 0.55,
  mouth_open: 0.05, mouth_curve: 0.25, mouth_width: 1,
  blush: 0, glow: 0.35, face_tilt: 0, shake: 0,
};

/* Geometry, matching renderer.layout(). */
function layout(p, opts, t) {
  const w = VIEW, h = VIEW, short = VIEW;
  const spacing = opts.eye_spacing * w;
  const eyeR = opts.eye_radius * short;
  const eyeY = opts.eye_y * h;
  const cx = w / 2;

  let jx = 0, jy = 0;
  if (p.shake > 0.01) {
    const amp = p.shake * short * 0.012;
    jx = Math.sin(t * 47) * amp;
    jy = Math.cos(t * 39) * amp * 0.6;
  }

  const eye = (sign, openness) => {
    const rx = eyeR * clamp(p.eye_width, 0.5, 1.6);
    const ry = eyeR * clamp(openness, 0, 1.6);
    const ex = cx + (sign * spacing) / 2;
    const pupilR = eyeR * 0.44 * clamp(p.pupil_scale, 0.35, 1.8);
    const travelX = Math.max(0, rx - pupilR - short * 0.006);
    const travelY = Math.max(0, ry - pupilR - short * 0.006);
    return {
      cx: ex, cy: eyeY, rx, ry,
      lidBottom: ry * clamp(p.eye_squint, 0, 1) * 0.55,
      arc: p.eye_arc,
      px: ex + clamp(p.pupil_x, -1, 1) * travelX,
      py: eyeY + clamp(p.pupil_y, -1, 1) * travelY,
      pr: pupilR,
    };
  };

  const left = eye(-1, p.eye_open_l);
  const right = eye(1, p.eye_open_r);

  const browGap = eyeR * (1.35 - p.brow_lift * 0.42);
  const browLen = eyeR * 1.5;
  const browDy = eyeR * 0.34;
  const brow = (e, sign) => {
    const y = e.cy - browGap;
    return {
      x1: e.cx - (sign * browLen) / 2, y1: y + p.brow_angle * browDy,
      x2: e.cx + (sign * browLen) / 2, y2: y - p.brow_angle * browDy * 0.55,
    };
  };

  return {
    left, right,
    browLeft: brow(left, -1), browRight: brow(right, 1),
    browAlpha: clamp(p.brow_show, 0, 1),
    browWidth: Math.max(2, eyeR * 0.16),
    mouthCx: cx,
    mouthCy: eyeY + short * 0.27,
    mouthW: short * 0.22 * clamp(p.mouth_width, 0.4, 1.8),
    mouthH: short * 0.075 * clamp(p.mouth_open, 0, 1.2) + short * 0.008,
    mouthCurve: clamp(p.mouth_curve, -1, 1),
    blush: clamp(p.blush, 0, 1),
    glow: clamp(p.glow, 0, 1),
    tilt: clamp(p.face_tilt, -1, 1) * 9,
    jx, jy,
  };
}

/* The visible region of one eye, as a clip path.
 *
 * Clipping rather than overpainting: a lid drawn in the background colour
 * looks right on a flat backdrop and stamps a visible block out of the glow
 * the moment there is one behind the eye. Mirrors renderer._draw_eye. */
function eyeClipPath(e) {
  const x0 = e.cx - e.rx - 4, x1 = e.cx + e.rx + 4;
  const top = e.arc < -0.02
    ? e.cy - e.ry * (1 - 1.4 * -e.arc)          // heavy upper lid
    : e.cy - e.ry - 4;
  const floor = e.cy + e.ry + 4 - e.lidBottom;  // squint trims from below

  if (e.arc > 0.02) {
    const base = Math.min(floor, e.cy + e.ry * (1 - 1.55 * e.arc));
    const bulge = e.ry * e.arc * 0.5;
    const steps = 16;
    let d = `M ${x0} ${top} L ${x1} ${top} L ${x1} ${base}`;
    for (let i = steps; i >= 0; i--) {
      const u = i / steps;
      const x = x0 + (x1 - x0) * u;
      const y = base - bulge * Math.sin(Math.PI * u);
      d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
    }
    return d + " Z";
  }
  return `M ${x0} ${top} L ${x1} ${top} L ${x1} ${floor} L ${x0} ${floor} Z`;
}

function mouthPath(g) {
  const steps = 26;
  const top = [], bottom = [];
  for (let i = 0; i <= steps; i++) {
    const u = i / steps;
    const x = g.mouthCx - g.mouthW / 2 + g.mouthW * u;
    // Negated so a positive curve is a smile: centre below the corners.
    const bend = Math.pow(u - 0.5, 2) * 4 - 1;
    const yMid = g.mouthCy - bend * g.mouthCurve * g.mouthW * 0.22;
    const half = (g.mouthH / 2) * Math.pow(Math.sin(Math.PI * u), 0.6);
    top.push([x, yMid - half]);
    bottom.push([x, yMid + half]);
  }
  const pts = top.concat(bottom.reverse());
  return "M " + pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L ") + " Z";
}

export class FaceView {
  constructor(svg, palette, opts) {
    this.svg = svg;
    this.palette = palette;
    this.opts = opts;
    this.params = { ...DEFAULT_PARAMS };
    this.build();
  }

  el(tag, attrs = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }

  build() {
    const svg = this.svg;
    svg.setAttribute("viewBox", `0 0 ${VIEW} ${VIEW}`);
    svg.innerHTML = "";

    const defs = this.el("defs");
    defs.innerHTML = `
      <radialGradient id="eyeGlow">
        <stop offset="0%" stop-color="${this.palette.glow}" stop-opacity="0.75"/>
        <stop offset="100%" stop-color="${this.palette.glow}" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="blushGrad">
        <stop offset="0%" stop-color="${this.palette.blush}" stop-opacity="0.6"/>
        <stop offset="100%" stop-color="${this.palette.blush}" stop-opacity="0"/>
      </radialGradient>`;
    svg.appendChild(defs);

    this.root = this.el("g");
    svg.appendChild(this.root);

    svg.appendChild(this.el("circle", {
      cx: VIEW / 2, cy: VIEW / 2, r: VIEW / 2 - 1,
      fill: "none", stroke: "rgba(255,255,255,0.07)", "stroke-width": 2,
    }));

    this.nodes = {};
    for (const side of ["left", "right"]) {
      this.nodes[side] = {
        glow: this.el("ellipse", { fill: "url(#eyeGlow)" }),
        blush: this.el("ellipse", { fill: "url(#blushGrad)" }),
        clip: this.el("clipPath", { id: `clip-${side}` }),
        clipShape: this.el("path"),
        group: this.el("g", { "clip-path": `url(#clip-${side})` }),
        white: this.el("ellipse", { fill: this.palette.iris }),
        pupil: this.el("circle", { fill: this.palette.iris_inner }),
        spark: this.el("circle", { fill: "#ffffff", opacity: 0.9 }),
        brow: this.el("line", {
          stroke: this.palette.iris, "stroke-linecap": "round",
        }),
        shut: this.el("line", {
          stroke: this.palette.iris, "stroke-linecap": "round", opacity: 0,
        }),
      };
      const n = this.nodes[side];
      n.clip.appendChild(n.clipShape);
      defs.appendChild(n.clip);
      this.root.appendChild(n.glow);
      this.root.appendChild(n.blush);
      for (const key of ["white", "pupil", "spark"]) n.group.appendChild(n[key]);
      this.root.appendChild(n.group);
      this.root.appendChild(n.brow);
      this.root.appendChild(n.shut);
    }
    this.mouth = this.el("path", { fill: this.palette.mouth });
    this.root.appendChild(this.mouth);
  }

  setPalette(palette) {
    this.palette = palette;
    this.build();
  }

  update(params) {
    this.params = { ...this.params, ...params };
  }

  draw(t) {
    const g = layout(this.params, this.opts, t);
    this.root.setAttribute(
      "transform",
      `translate(${g.jx.toFixed(2)} ${g.jy.toFixed(2)}) rotate(${g.tilt.toFixed(2)} ${VIEW / 2} ${VIEW / 2})`
    );

    for (const [side, e] of [["left", g.left], ["right", g.right]]) {
      const n = this.nodes[side];
      const shut = e.ry < 2.5;

      n.glow.setAttribute("cx", e.cx);
      n.glow.setAttribute("cy", e.cy);
      n.glow.setAttribute("rx", e.rx * 2.6);
      n.glow.setAttribute("ry", Math.max(e.ry, 8) * 2.6);
      n.glow.setAttribute("opacity", g.glow.toFixed(3));

      n.blush.setAttribute("cx", e.cx);
      n.blush.setAttribute("cy", e.cy + Math.max(e.ry, 10) * 1.5);
      n.blush.setAttribute("rx", e.rx * 1.2);
      n.blush.setAttribute("ry", Math.max(e.ry, 10) * 0.7);
      n.blush.setAttribute("opacity", g.blush.toFixed(3));

      n.shut.setAttribute("opacity", shut ? 1 : 0);
      if (shut) {
        n.shut.setAttribute("x1", e.cx - e.rx);
        n.shut.setAttribute("x2", e.cx + e.rx);
        n.shut.setAttribute("y1", e.cy);
        n.shut.setAttribute("y2", e.cy);
        n.shut.setAttribute("stroke-width", Math.max(3, e.rx * 0.13));
      }
      n.group.setAttribute("opacity", shut ? 0 : 1);
      if (shut) continue;

      n.clipShape.setAttribute("d", eyeClipPath(e));

      n.white.setAttribute("cx", e.cx);
      n.white.setAttribute("cy", e.cy);
      n.white.setAttribute("rx", e.rx);
      n.white.setAttribute("ry", e.ry);

      n.pupil.setAttribute("cx", e.px);
      n.pupil.setAttribute("cy", e.py);
      n.pupil.setAttribute("r", e.pr);

      n.spark.setAttribute("cx", e.px + e.pr * 0.35);
      n.spark.setAttribute("cy", e.py - e.pr * 0.4);
      n.spark.setAttribute("r", Math.max(1, e.pr * 0.22));

      const b = side === "left" ? g.browLeft : g.browRight;
      n.brow.setAttribute("x1", b.x1);
      n.brow.setAttribute("y1", b.y1);
      n.brow.setAttribute("x2", b.x2);
      n.brow.setAttribute("y2", b.y2);
      n.brow.setAttribute("stroke-width", g.browWidth);
      n.brow.setAttribute("opacity", g.browAlpha.toFixed(3));
    }

    this.mouth.setAttribute("d", mouthPath(g));
  }
}
