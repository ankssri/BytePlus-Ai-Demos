/* Seedance 2.5 Ad Agent — front-end controller. */
"use strict";

const state = {
  config: {}, plan: null,
  refs: [],            // brand-kit references: {url, ref, name, kind}  (ref = asset:// or url/dataURI)
  voMode: "A", voRef: "",   // reference audio (asset:// or data URI) for VO mode B
  story: [],           // storyboard frames: {label, url, approved}
  videoUrl: "",        // latest generated / edited ad
};

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
const esc = s => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sleep = ms => new Promise(r => setTimeout(r, ms));
function toast(m, e) { const t = $("#toast"); t.textContent = m; t.classList.toggle("err", !!e); t.classList.add("show"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 3400); }
async function api(p, o) { const r = await fetch(p, o); let d; try { d = await r.json(); } catch { d = {}; } if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : JSON.stringify(d.error || d)); return d; }
function blobToDataURL(b) { return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(b); }); }

// nav
$$(".step").forEach(b => b.addEventListener("click", () => goStep(+b.dataset.step)));
document.addEventListener("click", e => { const b = e.target.closest("[data-goto]"); if (b) goStep(+b.dataset.goto); });
function goStep(n) {
  $$(".step").forEach(b => b.classList.toggle("active", +b.dataset.step === n));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === `panel-${n}`));
  if (n === 5) renderGenerate();
  if (n === 6) renderOverlayPlan();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadConfig() {
  const c = state.config = await api("/api/config");
  const b = (l, ok) => `<span class="badge ${ok ? "ok" : "bad"}">${l} ${ok ? "✓" : "✗"}</span>`;
  $("#configBadges").innerHTML = b("API", c.api_key_configured) + b("AK/SK", c.ak_configured && c.sk_configured)
    + b("Seedream", c.seedream_model_configured) + b("Seedance", c.seedance_model_configured)
    + b("LLM", c.llm_model_configured) + b("TTS", c.tts_configured);
}
async function loadBriefs() {
  const { briefs } = await api("/api/sample-briefs");
  briefs.forEach(x => { const o = el("option"); o.value = x.name; o.textContent = x.name; $("#sampleBrief").appendChild(o); });
}
$("#loadBrief").addEventListener("click", async () => {
  const n = $("#sampleBrief").value; if (!n) return toast("Pick a sample");
  const d = await api("/api/sample-brief?name=" + encodeURIComponent(n));
  $("#brief").value = d.text || ""; toast("Brief loaded");
});

// STEP 1 -> plan
$("#genPlanBtn").addEventListener("click", async () => {
  const brief = $("#brief").value.trim(); if (!brief) return toast("Write a brief first", true);
  $("#planWarn").innerHTML = "⏳ Script Agent is writing the ad plan…";
  try {
    const d = await api("/api/generate-plan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, duration: +$("#duration").value, aspect: $("#aspect").value,
        language: $("#language").value, model_text: $("#modelText").checked }) });
    setPlan(d.plan); $("#planWarn").innerHTML = ""; toast("Plan ready"); goStep(2);
  } catch (e) { $("#planWarn").innerHTML = ""; toast(e.message, true); }
});
$("#skipPlanBtn").addEventListener("click", () => goStep(2));

// STEP 2 plan
function setPlan(plan) {
  state.plan = plan;
  $("#planJson").value = JSON.stringify(plan, null, 2);
  $("#directorBrief").value = plan.director_brief || "";
  renderPlanView();
}
$("#applyPlan").addEventListener("click", () => {
  try { const p = JSON.parse($("#planJson").value); setPlan(p); toast("Plan applied"); }
  catch (e) { toast("Invalid JSON: " + e.message, true); }
});
function renderPlanView() {
  const p = state.plan; if (!p) return;
  const scenes = (p.scenes || []).map(s => `<div class="planscene">
    <span class="t">${s.t_start}–${s.t_end}s · ${esc(s.camera || "")}</span><br>
    <span class="hi">${esc(s.action || "")}</span><br>
    🎙 ${esc(s.vo_hindi || "")} <span class="t">${esc(s.vo_english || "")}</span>
    ${s.on_screen_text ? `<br>🔤 <b>${esc(s.on_screen_text)}</b>` : ""}</div>`).join("");
  $("#planView").innerHTML = `<h3>${esc(p.title || "")} — ${esc(p.duration_seconds || "")}s ${esc(p.aspect || "")}</h3>${scenes}`;
}

// STEP 3 brand kit
function renderRefs() {
  $("#refList").innerHTML = state.refs.map((r, i) => `<div class="assetrow">
    <img src="${esc(r.url)}"><div class="grow"><b>${esc(r.name)}</b> <span class="status">${esc(r.kind)}</span>
    <div><code>${esc(r.ref.startsWith("asset://") ? r.ref : "(inline image)")}</code></div></div>
    <button class="btn small" data-rmref="${i}">remove</button></div>`).join("")
    || `<p class="muted">No references yet.</p>`;
}
$("#refList").addEventListener("click", e => { const b = e.target.closest("[data-rmref]"); if (b) { state.refs.splice(+b.dataset.rmref, 1); renderRefs(); } });

$("#refUpload").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  const data = await blobToDataURL(f);
  try {
    if ($("#isFace").checked) {
      toast("Preparing face (Seedream trusted pass)…");
      const d = await api("/api/prepare-face", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ image: data }) });
      const ref = await registerAsset(d.url, f.name, "Image");
      state.refs.push({ url: d.url, ref, name: f.name, kind: "presenter (trusted)" });
    } else {
      state.refs.push({ url: data, ref: data, name: f.name, kind: "reference (inline)" });
    }
    renderRefs(); toast("Reference added");
  } catch (err) { toast(err.message, true); }
});
$("#genRefBtn").addEventListener("click", async () => {
  const prompt = window.prompt("Describe the reference to generate (product / logo / presenter / style):");
  if (!prompt) return;
  try {
    toast("Generating with Seedream…");
    const d = await api("/api/seedream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, size: "720x1280" }) });
    const ref = await registerAsset(d.url, prompt.slice(0, 24), "Image");
    state.refs.push({ url: d.url, ref, name: prompt.slice(0, 24), kind: "generated" });
    renderRefs(); toast("Reference generated");
  } catch (e) { toast(e.message, true); }
});
async function registerAsset(url, name, type) {
  // Register a public URL as an Asset so Seedance can use asset://<id>. Falls back
  // to the raw URL if the asset API isn't available.
  try {
    const d = await api("/api/create-asset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, name, asset_type: type }) });
    if (d.id) { await pollAsset(d.id); return "asset://" + d.id; }
  } catch (e) { /* fall back to URL */ }
  return url;
}
async function pollAsset(id) { for (let i = 0; i < 20; i++) { try { const d = await api("/api/asset-status/" + id); if (["Available", "Success", "Succeeded", "Ready", "ready"].includes(d.status)) return; if (["Failed", "Error"].includes(d.status)) return; } catch {} await sleep(2000); } }

// VO
$("#voA").addEventListener("change", () => { state.voMode = "A"; $("#voBBox").classList.add("hidden"); });
$("#voB").addEventListener("change", () => { state.voMode = "B"; $("#voBBox").classList.remove("hidden"); });
$("#ttsBtn").addEventListener("click", async () => {
  const text = ((state.plan && state.plan.scenes) || []).map(s => s.vo_hindi).filter(Boolean).join(" ");
  if (!text) return toast("No VO lines in the plan", true);
  $("#voStatus").textContent = "synthesizing…"; $("#voStatus").className = "status run";
  try {
    const d = await api("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language: "hi" }) });
    if (d.audio_url) { state.voRef = await registerAsset(d.audio_url, "vo", "Audio"); }
    else if (d.audio_base64) { state.voRef = "data:audio/mp3;base64," + d.audio_base64; }
    $("#voStatus").textContent = "VO ready"; $("#voStatus").className = "status ok";
  } catch (e) { $("#voStatus").textContent = "TTS unavailable"; $("#voStatus").className = "status err"; toast(e.message, true); }
});
$("#voUpload").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  state.voRef = await blobToDataURL(f);
  $("#voStatus").textContent = "VO uploaded"; $("#voStatus").className = "status ok"; toast("VO audio set");
});

// STEP 4 storyboard
$("#genStoryBtn").addEventListener("click", async () => {
  const scenes = (state.plan && state.plan.scenes) || [];
  if (!scenes.length) return toast("No plan scenes — do step 2 first", true);
  const pick = [scenes[0], scenes[Math.floor(scenes.length / 2)], scenes[scenes.length - 1]].filter(Boolean);
  const anchor = state.refs[0] ? state.refs[0].url : null;   // keep presenter if we have one
  state.story = pick.map((s, i) => ({ label: ["Open", "Hero", "CTA"][i] || ("F" + i), scene: s, url: "", approved: false }));
  renderStory();
  for (let i = 0; i < state.story.length; i++) {
    const s = state.story[i];
    setStory(i, "generating…", "run");
    try {
      // Seedream 6-part composition: quality + subject + environment + shot + style + light.
      const subj = (anchor ? "Keep the exact same person as in the reference image. " : "") + (s.scene.action || "");
      const prompt = `high quality, ultra-fine, 2K. ${subj} Vertical 9:16 mobile framing. Photorealistic, cinematic, natural lighting.`;
      const d = await api("/api/seedream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, size: "2K", image: anchor }) });
      s.url = d.url; renderStory();
    } catch (e) { setStory(i, "error", "err"); toast(e.message, true); }
  }
});
function renderStory() {
  $("#storyCards").innerHTML = "";
  state.story.forEach((s, i) => {
    const c = el("div", "card" + (s.approved ? " approved" : ""));
    c.innerHTML = `<div class="head"><b>${esc(s.label)}</b><span class="status" id="ss-${i}"></span></div>
      <div class="media">${s.url ? `<img src="${esc(s.url)}">` : "…"}</div>
      <div class="body"><button class="btn small" data-story="${i}">${s.approved ? "✓ Approved (anchored)" : "Approve & anchor"}</button></div>`;
    $("#storyCards").appendChild(c);
  });
}
function setStory(i, t, c) { const e = $(`#ss-${i}`); if (e) { e.textContent = t; e.className = "status " + (c || ""); } }
$("#storyCards").addEventListener("click", e => { const b = e.target.closest("[data-story]"); if (!b) return; const i = +b.dataset.story; if (!state.story[i].url) return toast("Not generated yet", true); state.story[i].approved = !state.story[i].approved; renderStory(); });

// STEP 5 generate
function collectRefs() {
  const imgs = state.refs.map(r => r.ref);
  const labels = state.refs.map(r => r.kind);
  state.story.filter(s => s.approved && s.url).forEach(s => { imgs.push(s.url); labels.push(`approved ${s.label} storyboard frame (anchor this composition)`); });
  const auds = (state.voMode === "B" && state.voRef) ? [state.voRef] : [];
  return { imgs, auds, labels };
}
$("#optimizeBtn").addEventListener("click", async () => {
  const prompt = $("#directorBrief").value.trim(); if (!prompt) return toast("Nothing to optimize", true);
  $("#optStatus").textContent = "optimizing…"; $("#optStatus").className = "status run";
  try {
    const d = await api("/api/optimize-prompt", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, duration: +$("#genDur").value, aspect: $("#aspect").value }) });
    if (d.optimized) $("#directorBrief").value = d.optimized;
    $("#optStatus").textContent = "optimized"; $("#optStatus").className = "status ok";
  } catch (e) { $("#optStatus").textContent = "error"; $("#optStatus").className = "status err"; toast(e.message, true); }
});
function renderGenerate() {
  if (state.plan && !$("#directorBrief").value.trim()) $("#directorBrief").value = state.plan.director_brief || "";
  const { imgs, auds } = collectRefs();
  $("#refsSummary").textContent = `Omni references: ${imgs.length} image(s), ${auds.length} audio · VO mode ${state.voMode}`;
}
$("#genVideoBtn").addEventListener("click", async () => {
  const brief = $("#directorBrief").value.trim(); if (!brief) return toast("Director's brief is empty", true);
  const { imgs, auds, labels } = collectRefs();
  $("#genStatus").textContent = "submitting…"; $("#genStatus").className = "status run";
  try {
    const d = await api("/api/generate-video", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ director_brief: brief, reference_images: imgs, reference_audios: auds, reference_labels: labels,
        resolution: $("#res").value, duration: +$("#genDur").value, aspect: $("#aspect").value, generate_audio: $("#genAudio").checked }) });
    await pollVideo(d.id, "#genStatus", url => { state.videoUrl = url; $("#videoOut").innerHTML = `<video src="${esc(url)}" controls></video>`; });
  } catch (e) { $("#genStatus").textContent = "error"; $("#genStatus").className = "status err"; toast(e.message, true); }
});
async function pollVideo(taskId, statusSel, onDone) {
  const s = $(statusSel);
  for (let n = 0; n < 180; n++) {
    const d = await api("/api/video-task/" + taskId);
    const st = d.status || "";
    if (st === "succeeded" && d.video_url) { s.textContent = "done"; s.className = "status ok"; onDone(d.video_url); return; }
    if (st === "failed" || d.error) { s.textContent = "failed"; s.className = "status err"; toast(JSON.stringify(d.error || st), true); return; }
    s.textContent = st || "running…"; s.className = "status run"; await sleep(5000);
  }
  s.textContent = "timeout"; s.className = "status err";
}

// STEP 6 edit / extend / overlays
$("#editBtn").addEventListener("click", () => runEdit("/api/edit-video"));
$("#extendBtn").addEventListener("click", () => runEdit("/api/extend-video"));
async function runEdit(path) {
  if (!state.videoUrl) return toast("Generate the ad first (step 5)", true);
  const instruction = $("#editInstr").value.trim(); if (!instruction) return toast("Write an edit instruction", true);
  $("#editStatus").textContent = "submitting…"; $("#editStatus").className = "status run";
  try {
    const d = await api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ video_url: state.videoUrl, instruction }) });
    await pollVideo(d.id, "#editStatus", url => { state.videoUrl = url; $("#editOut").innerHTML = `<video src="${esc(url)}" controls></video>`; });
  } catch (e) { $("#editStatus").textContent = "error"; $("#editStatus").className = "status err"; toast(e.message, true); }
}
function renderOverlayPlan() {
  const ov = (state.plan && state.plan.overlay_text) || [];
  $("#overlayPlan").innerHTML = ov.length ? ov.map(o => `<div class="assetrow"><div class="grow">
    <b>${esc(o.text)}</b> <span class="status">${esc(o.position)}</span> <span class="muted">${o.t_start}–${o.t_end}s</span></div></div>`).join("")
    : `<p class="muted">No overlay text in the plan. Composite logo, contact bar, Hindi/number badges and captions in your editor.</p>`;
}

// boot
loadConfig().catch(e => toast(e.message, true));
loadBriefs().catch(() => {});
