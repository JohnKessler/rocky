/* Rocky's dashboard.
 *
 * One websocket carries everything live; HTTP handles commands and the
 * settings tree. Nothing here knows Rocky's vocabulary in advance - the
 * expression, gesture and chord palettes and every settings control are built
 * from what the API reports, so adding a gesture in Python makes a button
 * appear here without touching this file.
 */

import { FaceView, DEFAULT_PARAMS } from "/static/js/face.js";

const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
};
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = (path, body) => api(path, { method: "PATCH", body: JSON.stringify(body) });

const state = {
  config: { values: {}, schema: {} },
  faceOpts: { eye_spacing: 0.3, eye_radius: 0.135, eye_y: 0.46 },
  palette: {
    background: "#05070d", iris: "#6fd3e7", iris_inner: "#bff0fa",
    glow: "#1c6b7d", mouth: "#6fd3e7", blush: "#e0715f",
  },
  faces: [],
};

let faceA = null, faceB = null;

/* ------------------------------------------------------------------ tabs */

$("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-tab]");
  if (!btn) return;
  for (const b of $("tabs").children) b.classList.toggle("on", b === btn);
  for (const s of document.querySelectorAll(".tab")) {
    s.classList.toggle("on", s.id === `tab-${btn.dataset.tab}`);
  }
  if (btn.dataset.tab === "memory") loadMemory();
});

/* --------------------------------------------------------------- palettes */

async function buildVocabulary() {
  const vocab = await api("/api/vocabulary");
  $("robot-name").textContent = vocab.identity.name;
  $("owner").textContent = vocab.identity.owner ? `· ${vocab.identity.owner}` : "";
  document.title = vocab.identity.name;

  const exprBox = $("expression-palette");
  exprBox.innerHTML = "";
  for (const name of vocab.expressions) {
    const b = document.createElement("button");
    b.textContent = name;
    b.onclick = () => post("/api/expression", {
      name,
      intensity: Number($("expr-intensity").value),
      hold: Number($("expr-hold").value),
    }).catch(showError);
    exprBox.appendChild(b);
  }

  const gestBox = $("gesture-palette");
  gestBox.innerHTML = "";
  for (const g of vocab.gestures) {
    const b = document.createElement("button");
    b.innerHTML = `${g.name}<small>${g.description}</small>`;
    b.onclick = () => post("/api/gesture", { name: g.name }).catch(showError);
    gestBox.appendChild(b);
  }

  const motifBox = $("motif-palette");
  motifBox.innerHTML = "";
  for (const m of vocab.motifs) {
    const b = document.createElement("button");
    b.innerHTML = `${m.name}<small>“${m.meaning}”</small>`;
    b.onclick = () => post("/api/chirp", { motif: m.name }).catch(showError);
    motifBox.appendChild(b);
  }
}

/* --------------------------------------------------------------- settings */

/* One control renderer for the whole config tree. The schema carries type,
 * bounds, choices and help text, so a new setting in Python shows up here
 * with the right widget and the right limits automatically. */
function settingRow(path, value, meta) {
  const row = document.createElement("div");
  row.className = "setting";

  const key = document.createElement("div");
  key.className = "key";
  key.innerHTML = `${path}${meta.help ? `<small>${meta.help}</small>` : ""}`;
  row.appendChild(key);

  const out = document.createElement("div");
  out.className = "val";

  let input;
  const apply = async (raw) => {
    try {
      const res = await patch("/api/config", { path, value: raw });
      row.classList.remove("invalid");
      out.textContent = format(res.value);
      state.config.values[path] = res.value;
    } catch (err) {
      row.classList.add("invalid");
      out.textContent = String(err).slice(0, 40);
    }
  };

  if (meta.choices) {
    input = document.createElement("select");
    for (const c of meta.choices) {
      const o = document.createElement("option");
      o.value = o.textContent = c;
      input.appendChild(o);
    }
    input.value = value;
    input.onchange = () => apply(input.value);
    out.textContent = value;
  } else if (meta.type === "bool") {
    input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    input.onchange = () => apply(input.checked);
    out.textContent = value ? "on" : "off";
    input.addEventListener("change", () => { out.textContent = input.checked ? "on" : "off"; });
  } else if ((meta.type === "float" || meta.type === "int") &&
             ("min" in meta || "min_exclusive" in meta) &&
             ("max" in meta || "max_exclusive" in meta)) {
    const lo = meta.min ?? meta.min_exclusive;
    const hi = meta.max ?? meta.max_exclusive;
    input = document.createElement("input");
    input.type = "range";
    input.min = lo; input.max = hi;
    input.step = meta.type === "int" ? 1 : Math.max((hi - lo) / 200, 0.001);
    input.value = value;
    out.textContent = format(value);
    input.oninput = () => { out.textContent = format(Number(input.value)); };
    input.onchange = () => apply(Number(input.value));
  } else {
    input = document.createElement("input");
    input.value = value ?? "";
    input.onchange = () => {
      const raw = meta.type === "int" ? parseInt(input.value, 10)
                : meta.type === "float" ? parseFloat(input.value)
                : input.value;
      apply(raw);
    };
    out.textContent = format(value);
  }

  row.appendChild(input);
  row.appendChild(out);
  return row;
}

const format = (v) =>
  typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(3)) : String(v);

function renderSettings(container, predicate) {
  container.innerHTML = "";
  const { values, schema } = state.config;
  for (const path of Object.keys(schema).sort()) {
    if (!predicate(path)) continue;
    container.appendChild(settingRow(path, values[path], schema[path]));
  }
}

async function loadConfig() {
  state.config = await api("/api/config");
  const v = state.config.values;
  state.faceOpts = {
    eye_spacing: v["face.eye_spacing"], eye_radius: v["face.eye_radius"], eye_y: v["face.eye_y"],
  };
  state.palette = {
    background: v["face.palette.background"], iris: v["face.palette.iris"],
    iris_inner: v["face.palette.iris_inner"], glow: v["face.palette.glow"],
    mouth: v["face.palette.mouth"], blush: v["face.palette.blush"],
  };
  if (faceA) { faceA.opts = state.faceOpts; faceA.setPalette(state.palette); }
  if (faceB) { faceB.opts = state.faceOpts; faceB.setPalette(state.palette); }

  renderSettings($("trait-settings"), (p) => p.startsWith("identity."));
  renderSettings($("brain-settings"), (p) => p.startsWith("brain.") || p.startsWith("memory."));
  renderSettings($("motion-settings"), (p) => p.startsWith("motion."));
  renderSettings($("face-settings"), (p) => p.startsWith("face."));
  renderSettings($("audio-settings"), (p) => p.startsWith("audio."));
  applyFilter();

  $("jog-pan").min = v["motion.pan.min_deg"];
  $("jog-pan").max = v["motion.pan.max_deg"];
  $("jog-tilt").min = v["motion.tilt.min_deg"];
  $("jog-tilt").max = v["motion.tilt.max_deg"];
}

function applyFilter() {
  const q = $("settings-filter").value.trim().toLowerCase();
  renderSettings($("all-settings"), (p) => !q || p.toLowerCase().includes(q));
}
$("settings-filter").addEventListener("input", applyFilter);

$("save-config").onclick = async () => {
  try {
    const res = await post("/api/config/save");
    $("save-status").textContent = `saved ${res.saved}`;
  } catch (err) { $("save-status").textContent = String(err); }
  setTimeout(() => ($("save-status").textContent = ""), 4000);
};

/* ----------------------------------------------------------------- motion */

const jogDebounce = debounce((pan, tilt) => post("/api/motion/jog", { pan, tilt }).catch(showError), 90);
for (const axis of ["pan", "tilt"]) {
  const el = $(`jog-${axis}`);
  el.addEventListener("input", () => {
    $(`jog-${axis}-val`).textContent = el.value;
    jogDebounce(Number($("jog-pan").value), Number($("jog-tilt").value));
  });
}
document.querySelectorAll("[data-mode]").forEach((b) => {
  b.onclick = () => post("/api/motion/mode", { mode: b.dataset.mode }).catch(showError);
});
$("centre-btn").onclick = async () => {
  await post("/api/motion/centre").catch(showError);
  $("jog-pan").value = 0; $("jog-tilt").value = 0;
  $("jog-pan-val").textContent = "0"; $("jog-tilt-val").textContent = "0";
};
$("tone-btn").onclick = () => post("/api/audio/test").catch(showError);

for (const id of ["expr-intensity", "expr-hold"]) {
  $(id).addEventListener("input", () => { $(`${id}-val`).textContent = $(id).value; });
}

/* ------------------------------------------------------------ conversation */

$("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("ask-input").value.trim();
  if (!text) return;
  $("ask-input").value = "";
  addLine("user", text);
  try { await post("/api/ask", { text }); } catch (err) { showError(err); }
});
$("say-btn").onclick = async () => {
  const text = $("ask-input").value.trim();
  if (!text) return;
  $("ask-input").value = "";
  try { await post("/api/say", { text }); } catch (err) { showError(err); }
};

function addLine(kind, text, target = "transcript") {
  const box = $(target);
  const el = document.createElement("div");
  el.className = `line ${kind}`;
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  el.innerHTML = `<time>${time}</time>`;
  el.appendChild(document.createTextNode(text));
  box.appendChild(el);
  while (box.children.length > 200) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}

function showError(err) { addLine("event", `error: ${err}`); }

/* ----------------------------------------------------------------- memory */

async function loadMemory() {
  const data = await api("/api/memory").catch(() => ({ facts: [], stats: {} }));
  $("memory-count").textContent = data.facts.length;
  const box = $("memory-list");
  box.innerHTML = "";
  if (!data.facts.length) {
    box.innerHTML = `<div class="hint">Rocky has not kept anything yet.</div>`;
    return;
  }
  for (const f of data.facts) {
    const row = document.createElement("div");
    row.className = "fact";
    const left = document.createElement("div");
    left.innerHTML = `<span class="cat">${f.category}</span> ${escapeHtml(f.text)}`;
    const del = document.createElement("button");
    del.textContent = "Forget";
    del.onclick = async () => {
      await api(`/api/memory/${f.id}`, { method: "DELETE" }).catch(showError);
      loadMemory();
    };
    row.append(left, del);
    box.appendChild(row);
  }
}
$("memory-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("memory-input").value.trim();
  if (!text) return;
  $("memory-input").value = "";
  await post("/api/memory", { text }).catch(showError);
  loadMemory();
});

const escapeHtml = (s) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* -------------------------------------------------------------- telemetry */

function onStatus(s) {
  if (!s) return;
  $("pill-uptime").textContent = formatUptime(s.uptime_s);
  const temp = s.cpu_temp_c;
  const tempPill = $("pill-temp");
  tempPill.textContent = temp == null ? "temp n/a" : `${temp.toFixed(1)}°C`;
  tempPill.className = "pill" + (temp == null ? "" : temp > 78 ? " bad" : temp > 68 ? " hot" : "");

  if (s.motion) {
    $("pose-pan").textContent = `${s.motion.pan.toFixed(1)}°`;
    $("pose-tilt").textContent = `${s.motion.tilt.toFixed(1)}°`;
    $("pose-torque").textContent = s.motion.torque ? "driving" : "released";
    $("pose-track").textContent = s.motion.tracking ? "locked" : "searching";
    $("pill-mode").textContent = s.motion.mode;
    drawPoseMap(s.motion);
  }
  if (s.audio) {
    $("level-bar").style.width = `${Math.min(100, s.audio.level * 1400)}%`;
    $("wake-score").textContent = (s.audio.wake_score ?? 0).toFixed(2);
    $("mic-state").textContent = s.audio.mic_open ? "open" : "closed";
    $("last-heard").textContent = s.audio.last_transcript || "—";
    $("audio-engines").textContent = `${s.audio.stt} / ${s.audio.tts}`;
    const ears = $("pill-ears");
    ears.textContent = s.audio.speaking ? "speaking" : s.audio.mic_open ? "listening" : "mic closed";
    ears.className = "pill" + (s.audio.mic_open || s.audio.speaking ? " active" : "");
  }
  if (s.vision) $("cam-detector").textContent = `${s.vision.camera} · ${s.vision.detector}`;
  if (s.brain) {
    const u = s.brain.usage || {};
    $("usage").textContent =
      `model ${s.brain.model} · effort ${s.brain.effort} · ${s.brain.available ? "connected" : "offline"}\n` +
      `turns ${s.brain.turns} · requests ${u.requests ?? 0} · in ${u.input_tokens ?? 0} · out ${u.output_tokens ?? 0} · cached ${u.cache_read ?? 0}` +
      (s.brain.last_error ? `\nlast error: ${s.brain.last_error}` : "");
  }
  $("service-status").textContent = JSON.stringify(
    {
      bus: s.bus, host: s.host, load: s.load,
      face: s.face && { renderer: s.face.renderer, fps: s.face.fps },
      vision: s.vision, motion: s.motion && { backend: s.motion.backend, mode: s.motion.mode },
      audio: s.audio && { io: s.audio.io, wake: s.audio.wake },
    }, null, 1);
}

function drawPoseMap(m) {
  const svg = $("pose-map");
  svg.innerHTML = `
    <rect x="-100" y="-26" width="200" height="52" fill="none" stroke="#232c44" stroke-width="1"/>
    <line x1="0" y1="-30" x2="0" y2="30" stroke="#232c44" stroke-width="0.7"/>
    <line x1="-104" y1="0" x2="104" y2="0" stroke="#232c44" stroke-width="0.7"/>
    <circle cx="${m.target_pan}" cy="${-m.target_tilt}" r="5" fill="none" stroke="#2b7385" stroke-width="1.5"/>
    <g stroke="${m.torque ? "#6fd3e7" : "#7d8aa6"}" stroke-width="2">
      <line x1="${m.pan - 6}" y1="${-m.tilt}" x2="${m.pan + 6}" y2="${-m.tilt}"/>
      <line x1="${m.pan}" y1="${-m.tilt - 6}" x2="${m.pan}" y2="${-m.tilt + 6}"/>
    </g>`;
}

function drawFaceBoxes(items) {
  const svg = $("cam-overlay");
  svg.innerHTML = (items || []).map((d) => {
    const x = (d.cx - d.w / 2) * 100, y = (d.cy - d.h / 2) * 100;
    return `<rect x="${x}" y="${y}" width="${d.w * 100}" height="${d.h * 100}"
             fill="none" stroke="#6fd3e7" stroke-width="0.5" opacity="0.85"/>`;
  }).join("");
}

const formatUptime = (s) => {
  s = Math.floor(s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
};

/* -------------------------------------------------------------- websocket */

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => $("link-dot").classList.add("up");
  ws.onclose = () => {
    $("link-dot").classList.remove("up");
    setTimeout(connect, 1500);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (msg) => {
    const { topic, data } = JSON.parse(msg.data);
    switch (topic) {
      case "hello":
      case "system.telemetry":
        onStatus(topic === "hello" ? data : data.data);
        break;
      case "face.frame":
        faceA?.update(data.params);
        faceB?.update(data.params);
        $("face-expression").textContent = data.expression;
        $("face-params").textContent = Object.entries(data.params)
          .map(([k, v]) => `${k.padEnd(13)} ${Number(v).toFixed(2)}`).join("\n");
        break;
      case "vision.faces":
        drawFaceBoxes(data.items);
        break;
      case "vision.scene":
        if (data.summary) $("scene").textContent = data.summary;
        break;
      case "audio.speech":
        addLine("user", data.text);
        break;
      case "brain.utterance":
        addLine("rocky", data.text);
        break;
      case "brain.tool_call":
        addLine("event", `${data.name} ${JSON.stringify(data.arguments)}`, "tool-log");
        break;
      case "brain.state":
        $("pill-brain").textContent = data.state + (data.detail ? ` · ${data.detail.slice(0, 24)}` : "");
        $("pill-brain").className = "pill" + (data.state === "error" ? " bad" : data.state === "thinking" ? " active" : "");
        break;
      case "system.log":
        addLine(data.level, `${data.logger}  ${data.message}`, "log");
        break;
      case "system.config_changed":
        state.config.values[data.path] = data.value;
        break;
      case "face.expression":
      case "motion.gesture":
      case "audio.chirp":
        addLine("event", `${topic.split(".")[1]}: ${data.name ?? data.motif}`, "tool-log");
        break;
    }
  };
}

/* ------------------------------------------------------------------- boot */

function debounce(fn, ms) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function startCamera() {
  const img = $("camera");
  // A polled still is more robust across reconnects than a long-lived
  // multipart stream, and at these rates it costs the same.
  const tick = () => { img.src = `/api/camera/frame?t=${Date.now()}`; };
  img.onerror = () => {};
  tick();
  setInterval(tick, 200);
}

function animate() {
  const t = performance.now() / 1000;
  faceA?.draw(t);
  faceB?.draw(t);
  requestAnimationFrame(animate);
}

(async function boot() {
  try {
    await buildVocabulary();
    await loadConfig();
  } catch (err) {
    showError(err);
  }
  faceA = new FaceView($("face"), state.palette, state.faceOpts);
  faceB = new FaceView($("face2"), state.palette, state.faceOpts);
  faceA.update(DEFAULT_PARAMS);
  faceB.update(DEFAULT_PARAMS);
  startCamera();
  animate();
  connect();
  loadMemory();

  const transcript = await api("/api/transcript").catch(() => ({ turns: [] }));
  for (const turn of transcript.turns) addLine(turn.role === "user" ? "user" : "rocky", turn.text);
})();
