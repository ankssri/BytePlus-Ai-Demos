/* Seedance 2.5 Ad Studio — front-end workflow controller. */
"use strict";

const state = {
  parsed: null,
  shots: [],      // working copy with runtime fields (imageUrl, assetId, taskId, videoUrl…)
  config: {},
  referenceUrl: "",   // approved frame used as the character/identity reference
  referenceKf: "",
};

// ── helpers ──────────────────────────────────────────────────────────────────
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (t, cls, html) => { const e = document.createElement(t); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const esc = (s) => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg; t.classList.toggle("err", !!isErr); t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 3200);
}
async function api(path, opts) {
  const res = await fetch(path, opts);
  let data; try { data = await res.json(); } catch { data = {}; }
  if (!res.ok) { const m = typeof data.error === "string" ? data.error : JSON.stringify(data.error || data); throw new Error(m); }
  return data;
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// ── step navigation ───────────────────────────────────────────────────────────
$$(".step").forEach(btn => btn.addEventListener("click", () => goStep(+btn.dataset.step)));
function goStep(n) {
  $$(".step").forEach(b => b.classList.toggle("active", +b.dataset.step === n));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === `panel-${n}`));
  if (n === 3) renderAssetRows();
  if (n === 4) renderVideoCards();
}

// ── config badges ─────────────────────────────────────────────────────────────
async function loadConfig() {
  state.config = await api("/api/config");
  const c = state.config;
  const b = (label, ok) => `<span class="badge ${ok ? "ok" : "bad"}">${label} ${ok ? "✓" : "✗"}</span>`;
  $("#configBadges").innerHTML =
    b("API key", c.api_key_configured) + b("AK/SK", c.ak_configured && c.sk_configured) +
    b("Seedream", c.seedream_model_configured) + b("Seedance", c.seedance_model_configured);
  if (c.asset_group_id) $("#groupId").value = c.asset_group_id;
}

// ── STEP 1 : load & parse ──────────────────────────────────────────────────────
async function loadSamples() {
  const { samples } = await api("/api/samples");
  const sel = $("#sampleSelect");
  samples.forEach(s => {
    const o = el("option"); o.value = JSON.stringify(s); o.textContent = s.key + (s.keyframes ? "  (+keyframes)" : "");
    sel.appendChild(o);
  });
}
$("#loadSampleBtn").addEventListener("click", async () => {
  const v = $("#sampleSelect").value; if (!v) return toast("Pick a sample first");
  const s = JSON.parse(v);
  const q = new URLSearchParams({ script: s.script || "", keyframes: s.keyframes || "" });
  const data = await api("/api/sample?" + q);
  $("#scriptMd").value = data.script_md || "";
  $("#keyframesMd").value = data.keyframes_md || "";
  toast("Sample loaded — now Parse");
});
$$('input[type=file][data-target]').forEach(inp => inp.addEventListener("change", e => {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader(); r.onload = () => { $("#" + inp.dataset.target).value = r.result; }; r.readAsText(f);
}));

$("#parseBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/parse-script", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ script_md: $("#scriptMd").value, keyframes_md: $("#keyframesMd").value }),
    });
    state.parsed = data;
    state.shots = data.shots.map(s => ({ ...s, imageUrl: "", approved: false, assetId: "", assetStatus: "", taskId: "", videoUrl: "", vidStatus: "" }));
    const w = $("#parseWarnings");
    w.innerHTML = (data.warnings || []).map(x => `<div>⚠ ${esc(x)}</div>`).join("");
    toast(`Parsed ${state.shots.length} shots`);
    renderShotCards();
    goStep(2);
  } catch (e) { toast(e.message, true); }
});

// ── STEP 2 : keyframes ─────────────────────────────────────────────────────────
function renderShotCards() {
  const wrap = $("#shotCards"); wrap.innerHTML = "";
  state.shots.forEach((shot, i) => wrap.appendChild(shotCard(shot, i)));
  renderRefInfo();
}
function shotCard(shot, i) {
  const card = el("div", "card" + (shot.approved ? " approved" : "") + (state.referenceKf === shot.kf ? " isref" : ""));
  card.id = `card-${i}`;
  const graphic = shot.is_graphic;
  card.innerHTML = `
    <div class="head">
      <span class="kf">${esc(shot.kf)} · ${esc(shot.title || "")}</span>
      <span class="tag ${graphic ? "graphic" : ""}">${graphic ? "graphic / post" : (shot.time ?? "") + "s"}</span>
    </div>
    <div class="media" id="media-${i}">${shot.imageUrl ? `<img src="${esc(shot.imageUrl)}">` : (graphic ? "designed end-card — build in post" : "no image yet")}</div>
    <div class="body">
      <div class="dlg">
        <div class="hi">🎙 ${esc(shot.dialogue_hindi) || "<span class='en'>(no dialogue in this shot)</span>"}</div>
        <div class="en">${esc(shot.dialogue_english)}</div>
      </div>
      <label style="color:var(--muted)">Image prompt
        <textarea id="prompt-${i}" ${graphic ? "" : ""}>${esc(shot.image_prompt)}</textarea>
      </label>
      <div class="actions">
        ${graphic ? "" : `<button class="btn primary small" data-act="gen" data-i="${i}">Generate</button>`}
        ${graphic ? "" : `<button class="btn small" data-act="edit" data-i="${i}">Edit frame</button>`}
        ${graphic ? "" : `<button class="btn small" data-act="ref" data-i="${i}">${state.referenceKf === shot.kf ? "★ Reference" : "☆ Use as ref"}</button>`}
        ${graphic ? "" : `<button class="btn small" data-act="approve" data-i="${i}">${shot.approved ? "✓ Approved" : "Approve"}</button>`}
        <span class="status ${shot._st || ""}" id="st-${i}">${shot._stTxt || ""}</span>
      </div>
    </div>`;
  return card;
}
// Convert any image URL (local /static example or remote) to a base64 data URI,
// so Seedream can always fetch it (a localhost URL is not reachable by BytePlus).
async function urlToDataURL(url) {
  const res = await fetch(url);
  const blob = await res.blob();
  return await blobToDataURL(blob);
}
function blobToDataURL(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = reject;
    r.readAsDataURL(blob);
  });
}

function renderRefInfo() {
  const box = document.getElementById("refInfo");
  if (!box) return;
  const examples = (state.refSamples || []).map(s =>
    `<img class="refthumb" src="${esc(s.url)}" title="${esc(s.name)}" data-url="${esc(s.url)}" data-name="${esc(s.name)}">`
  ).join("");
  const preview = state.referenceUrl
    ? `<img src="${esc(state.referenceUrl)}"><div>Locked to <b>${esc(state.referenceLabel || state.referenceKf || "reference")}</b> · <a href="#" id="clearRef">clear</a></div>`
    : `<div class="muted">No reference set — every frame is generated independently (face may drift).</div>`;
  box.innerHTML = `
    <div class="refpanel">
      <div class="refleft">
        <b>Character reference</b> — lock every keyframe to one person's face &amp; outfit.
        <div class="refcontrols">
          <label class="btn small">⬆ Upload image<input type="file" id="refUpload" accept="image/*" hidden></label>
          ${examples ? `<span class="muted">or pick an example:</span> ${examples}` :
            `<span class="muted">(drop photos in <code>static/sample_refs/</code> to add examples)</span>`}
        </div>
        <div class="muted" style="margin-top:6px">You can also generate a frame below and click <b>☆ Use as ref</b>.</div>
      </div>
      <div class="refpreview">${preview}</div>
    </div>`;

  const up = document.getElementById("refUpload");
  if (up) up.addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const data = await blobToDataURL(f);
    setReferenceImage(data, "your upload"); toast("Reference image uploaded");
  });
  box.querySelectorAll(".refthumb").forEach(t => t.addEventListener("click", async () => {
    try { const data = await urlToDataURL(t.dataset.url); setReferenceImage(data, t.dataset.name); toast(`Example "${t.dataset.name}" set as reference`); }
    catch (err) { toast("Could not load example image", true); }
  }));
  const c = document.getElementById("clearRef");
  if (c) c.addEventListener("click", (e) => { e.preventDefault(); clearReference(); });
}
function setReferenceImage(dataUrl, label) {
  state.referenceUrl = dataUrl; state.referenceLabel = label; state.referenceKf = "";
  renderShotCards();
}
function clearReference() {
  state.referenceUrl = ""; state.referenceKf = ""; state.referenceLabel = "";
  renderShotCards();
}
function setReference(i) {
  const shot = state.shots[i];
  if (!shot.imageUrl) return toast("Generate this frame first, then set it as reference", true);
  state.referenceUrl = shot.imageUrl; state.referenceKf = shot.kf; state.referenceLabel = shot.kf;
  renderShotCards();
  toast(`${shot.kf} set as character reference`);
}
async function loadRefSamples() {
  try { const d = await api("/api/ref-samples"); state.refSamples = d.samples || []; } catch { state.refSamples = []; }
}
$("#shotCards").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]"); if (!btn) return;
  const i = +btn.dataset.i, act = btn.dataset.act;
  if (act === "approve") return toggleApprove(i);
  if (act === "gen") return genKeyframe(i);
  if (act === "edit") return editKeyframe(i);
  if (act === "ref") return setReference(i);
});
function setStatus(i, txt, cls) {
  state.shots[i]._st = cls || ""; state.shots[i]._stTxt = txt || "";
  const s = $(`#st-${i}`); if (s) { s.textContent = txt || ""; s.className = "status " + (cls || ""); }
}
async function genKeyframe(i) {
  const shot = state.shots[i];
  const prompt = $(`#prompt-${i}`).value.trim(); shot.image_prompt = prompt;
  if (!prompt) return toast("Prompt is empty", true);
  setStatus(i, "generating…", "run");
  // Lock identity to the chosen reference frame (but never reference itself).
  const useRef = state.referenceUrl && state.referenceKf !== shot.kf ? state.referenceUrl : "";
  try {
    const data = await api("/api/generate-keyframe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, size: $("#imgSize").value.trim(), reference_image: useRef, seed: Math.floor(Math.random() * 2147483000) }),
    });
    shot.imageUrl = data.url; shot.approved = false;
    $(`#media-${i}`).innerHTML = `<img src="${esc(data.url)}">`;
    setStatus(i, "generated", "ok");
  } catch (e) { setStatus(i, "error", "err"); toast(`${shot.kf}: ${e.message}`, true); }
}
async function editKeyframe(i) {
  const shot = state.shots[i];
  if (!shot.imageUrl) return toast("Generate a frame first, then edit", true);
  const instr = prompt(`Edit instruction for ${shot.kf}\n(e.g. "make the blouse royal blue, fix the left hand")`);
  if (!instr) return;
  setStatus(i, "editing…", "run");
  try {
    const data = await api("/api/edit-keyframe", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: instr, image: shot.imageUrl, size: $("#imgSize").value.trim() }),
    });
    shot.imageUrl = data.url; shot.approved = false;
    $(`#media-${i}`).innerHTML = `<img src="${esc(data.url)}">`;
    setStatus(i, "edited", "ok");
  } catch (e) { setStatus(i, "error", "err"); toast(`${shot.kf}: ${e.message}`, true); }
}
function toggleApprove(i) {
  const shot = state.shots[i];
  if (!shot.imageUrl) return toast("Nothing to approve — generate first", true);
  shot.approved = !shot.approved;
  $(`#card-${i}`).classList.toggle("approved", shot.approved);
  const b = $(`#card-${i} button[data-act=approve]`); if (b) b.textContent = shot.approved ? "✓ Approved" : "Approve";
}
$("#genAllBtn").addEventListener("click", async () => {
  for (let i = 0; i < state.shots.length; i++) {
    if (state.shots[i].is_graphic || state.shots[i].imageUrl) continue;
    await genKeyframe(i);
  }
  toast("Done generating pending keyframes");
});

// ── STEP 3 : asset library ─────────────────────────────────────────────────────
function renderAssetRows() {
  const wrap = $("#assetRows"); wrap.innerHTML = "";
  const approved = state.shots.filter(s => s.approved && s.imageUrl);
  if (!approved.length) { wrap.innerHTML = `<p class="muted">No approved keyframes yet — go back to step 2 and approve some.</p>`; return; }
  approved.forEach(shot => {
    const i = state.shots.indexOf(shot);
    const row = el("div", "assetrow"); row.id = `asset-${i}`;
    row.innerHTML = `
      <img src="${esc(shot.imageUrl)}">
      <div class="grow">
        <div><b>${esc(shot.kf)}</b> · ${esc(shot.title || "")}</div>
        <div class="assetid" id="assetid-${i}">${shot.assetId ? `<code>asset://${esc(shot.assetId)}</code>` : "<span class='muted'>not uploaded</span>"}</div>
      </div>
      <span class="status ${shot.assetStatus === "Available" || shot.assetStatus === "Success" ? "ok" : ""}" id="astat-${i}">${esc(shot.assetStatus || "")}</span>
      <button class="btn small" data-i="${i}">Upload</button>`;
    wrap.appendChild(row);
  });
}
$("#assetRows").addEventListener("click", e => {
  const b = e.target.closest("button[data-i]"); if (!b) return; uploadAsset(+b.dataset.i);
});
async function uploadAsset(i) {
  const shot = state.shots[i]; const groupId = $("#groupId").value.trim();
  if (!groupId) return toast("Set an asset group id", true);
  const stat = $(`#astat-${i}`); stat.textContent = "creating…"; stat.className = "status run";
  try {
    const data = await api("/api/create-asset", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: groupId, url: shot.imageUrl, name: `${state.parsed.title || "ad"} ${shot.kf}`, asset_type: "Image" }),
    });
    shot.assetId = data.id;
    $(`#assetid-${i}`).innerHTML = `<code>asset://${esc(data.id)}</code>`;
    await pollAsset(i);
  } catch (e) { stat.textContent = "error"; stat.className = "status err"; toast(`${shot.kf}: ${e.message}`, true); }
}
async function pollAsset(i) {
  const shot = state.shots[i]; const stat = $(`#astat-${i}`);
  for (let n = 0; n < 30; n++) {
    const d = await api(`/api/asset-status/${shot.assetId}`);
    shot.assetStatus = d.status || "";
    stat.textContent = shot.assetStatus || "pending";
    if (["Available", "Success", "Succeeded", "ready", "Ready"].includes(shot.assetStatus)) { stat.className = "status ok"; return; }
    if (["Failed", "Error"].includes(shot.assetStatus)) { stat.className = "status err"; return; }
    stat.className = "status run"; await sleep(2500);
  }
}
$("#uploadAllBtn").addEventListener("click", async () => {
  const idx = state.shots.map((s, i) => i).filter(i => state.shots[i].approved && state.shots[i].imageUrl && !state.shots[i].assetId);
  for (const i of idx) await uploadAsset(i);
  toast("Uploaded approved keyframes");
});

// ── STEP 4 : video ─────────────────────────────────────────────────────────────
function renderVideoCards() {
  const wrap = $("#videoCards"); wrap.innerHTML = "";
  const ready = state.shots.filter(s => s.assetId || (s.approved && s.imageUrl));
  if (!ready.length) { wrap.innerHTML = `<p class="muted">Upload keyframes to the asset library first (step 3).</p>`; return; }
  ready.forEach(shot => {
    const i = state.shots.indexOf(shot);
    const card = el("div", "card"); card.id = `vcard-${i}`;
    const ref = shot.assetId ? `asset://${shot.assetId}` : "(image url)";
    card.innerHTML = `
      <div class="head"><span class="kf">${esc(shot.kf)}</span><span class="tag">${esc(ref)}</span></div>
      <div class="media" id="vmedia-${i}">${shot.videoUrl ? `<video src="${esc(shot.videoUrl)}" controls></video>` : (shot.imageUrl ? `<img src="${esc(shot.imageUrl)}">` : "")}</div>
      <div class="body">
        <label style="color:var(--muted)">Video prompt (motion + dialogue)
          <textarea id="vprompt-${i}">${esc(shot.video_prompt || "")}</textarea>
        </label>
        <div class="actions">
          <button class="btn primary small" data-i="${i}">Create task</button>
          <span class="status ${shot._vst || ""}" id="vst-${i}">${esc(shot.vidStatus || "")}</span>
        </div>
      </div>`;
    wrap.appendChild(card);
  });
}
$("#videoCards").addEventListener("click", e => {
  const b = e.target.closest("button[data-i]"); if (!b) return; createVideo(+b.dataset.i);
});
function setVst(i, txt, cls) { const s = $(`#vst-${i}`); state.shots[i]._vst = cls; state.shots[i].vidStatus = txt; if (s) { s.textContent = txt; s.className = "status " + (cls || ""); } }
async function createVideo(i) {
  const shot = state.shots[i];
  const first = shot.assetId ? `asset://${shot.assetId}` : shot.imageUrl;
  if (!first) return toast("No first frame for this shot", true);
  setVst(i, "submitting…", "run");
  try {
    const data = await api("/api/create-video-task", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: $(`#vprompt-${i}`).value.trim(),
        first_frame: first,
        resolution: $("#vidRes").value,
        duration: +$("#vidDur").value || 5,
        generate_audio: $("#vidAudio").checked,
      }),
    });
    shot.taskId = data.id;
    setVst(i, "queued " + (data.id || ""), "run");
    await pollVideo(i);
  } catch (e) { setVst(i, "error", "err"); toast(`${shot.kf}: ${e.message}`, true); }
}
async function pollVideo(i) {
  const shot = state.shots[i];
  for (let n = 0; n < 120; n++) {
    const d = await api(`/api/video-task/${shot.taskId}`);
    const st = d.status || "";
    if (st === "succeeded" && d.video_url) {
      shot.videoUrl = d.video_url; setVst(i, "done", "ok");
      $(`#vmedia-${i}`).innerHTML = `<video src="${esc(d.video_url)}" controls></video>`;
      return;
    }
    if (st === "failed" || d.error) { setVst(i, "failed", "err"); toast(`${shot.kf}: ${JSON.stringify(d.error || st)}`, true); return; }
    setVst(i, st || "running…", "run"); await sleep(5000);
  }
  setVst(i, "timeout", "err");
}
$("#genVideoAllBtn").addEventListener("click", async () => {
  const idx = state.shots.map((s, i) => i).filter(i => (state.shots[i].assetId || state.shots[i].imageUrl) && !state.shots[i].videoUrl);
  for (const i of idx) await createVideo(i);
  toast("All video tasks complete");
});

// ── STEP 5 : assemble ──────────────────────────────────────────────────────────
$("#stitchBtn").addEventListener("click", async () => {
  const urls = state.shots.filter(s => s.videoUrl).map(s => s.videoUrl);
  if (!urls.length) return toast("No finished clips yet", true);
  $("#ffmpegCmd").textContent =
    "# Manual stitch (save the printf list to concat.txt):\n" +
    urls.map((u, n) => `# clip ${n}: ${u}`).join("\n") +
    "\nffmpeg -f concat -safe 0 -i concat.txt -c copy final_ad.mp4";
  try {
    const d = await api("/api/stitch", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    $("#assembleOut").innerHTML = `<div class="assetrow"><div class="grow">✅ Stitched ${d.clips} clips → <code>${esc(d.output_path)}</code></div></div>`;
    toast("Stitched on server");
  } catch (e) {
    $("#assembleOut").innerHTML = `<p class="muted">Server stitch unavailable (${esc(e.message)}). Use the command below.</p>`;
  }
});

// ── boot ────────────────────────────────────────────────────────────────────────
loadConfig().catch(e => toast(e.message, true));
loadSamples().catch(() => {});
loadRefSamples();
