/* Seedance 2.5 Ad Agent — front-end controller. */
"use strict";

const state = {
  config: {}, plan: null,
  refs: [],            // brand-kit references: {url, ref, name, role}  (ref = asset:// or url/dataURI)
  voMode: "A", voRef: "",   // reference audio (asset:// or data URI) for VO mode B
  story: [],           // storyboard frames: {label, url, approved, useRefs[]}
  videoUrl: "",        // latest generated / edited ad
  chosenHook: null,    // index of the opening hook the user picked
};

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
const esc = s => (s == null ? "" : String(s)).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
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
  if (n === 2) renderHooks();
  if (n === 3) { renderProposals(); renderRefs(); }
  if (n === 4) renderStoryboard();
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
// Platform preset → sets aspect + duration together (format-first, like every leading tool).
$("#platform").addEventListener("change", e => {
  const v = e.target.value; if (v === "custom") return;
  const [, aspect, dur] = v.split("|");
  if (aspect) $("#aspect").value = aspect;
  if (dur) $("#duration").value = dur;
});

// STEP 1 -> plan
$("#genPlanBtn").addEventListener("click", async () => {
  const brief = $("#brief").value.trim(); if (!brief) return toast("Write a brief first", true);
  const btn = $("#genPlanBtn"); const orig = btn.textContent;
  btn.disabled = true; btn.textContent = "⏳ Writing the ad plan… (10–30s)";
  $("#planWarn").innerHTML = "⏳ The Script Agent (Seed LLM) is writing your ad plan. This takes 10–30 seconds…";
  try {
    const d = await api("/api/generate-plan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brief, duration: +$("#duration").value, aspect: $("#aspect").value,
        language: $("#language").value, model_text: $("#modelText").checked }) });
    setPlan(d.plan); $("#planWarn").innerHTML = "";
    toast("✓ Plan ready — opening the Script tab"); goStep(2);
  } catch (e) { $("#planWarn").innerHTML = `<div>⚠ ${esc(e.message)}</div>`; toast(e.message, true); }
  finally { btn.disabled = false; btn.textContent = orig; }
});
$("#skipPlanBtn").addEventListener("click", () => goStep(2));

// STEP 2 plan
function setPlan(plan) {
  state.plan = plan;
  state.story = [];   // rebuild storyboard from the new plan on next visit
  state.chosenHook = null;
  $("#planJson").value = JSON.stringify(plan, null, 2);
  $("#directorBrief").value = plan.director_brief || "";
  renderPlanView(); renderHooks();
}
// Opening-hook variants — the LLM already writes 2-3; let the user pick the strongest.
function renderHooks() {
  const box = $("#hookBox"); if (!box) return;
  const hooks = (state.plan && state.plan.hooks) || [];
  if (!hooks.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="refinfo"><b>🎣 Opening hooks</b> — the first ~3s decide watch-through.
    Pick the strongest first line; it's set as the opening voiceover (scene 1).
    <div class="hookrow">${hooks.map((h, i) =>
      `<button class="hookchip${state.chosenHook === i ? " on" : ""}" data-hook="${i}">${esc(h)}</button>`).join("")}</div></div>`;
}
$("#hookBox").addEventListener("click", e => {
  const b = e.target.closest("[data-hook]"); if (!b) return;
  const i = +b.dataset.hook, h = state.plan.hooks[i];
  if (state.plan.scenes && state.plan.scenes[0]) state.plan.scenes[0].vo_hindi = h;
  state.chosenHook = i;
  $("#planJson").value = JSON.stringify(state.plan, null, 2);
  renderPlanView(); renderHooks();
  toast("Hook set as the opening line (scene 1)");
});
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

// STEP 3 brand kit — typed, multi-reference
function refRoleColor(role) { return role === "Presenter" ? "run" : role === "Product" ? "ok" : ""; }
const ROLES = ["Presenter", "Product", "Logo", "Style", "Other"];
function roleOptions(sel) { return ROLES.map(r => `<option ${r === sel ? "selected" : ""}>${r}</option>`).join(""); }
function renderRefs() {
  $("#refList").innerHTML = state.refs.map((r, i) => `<div class="assetrow">
    <img src="${esc(r.url)}"><div class="grow"><b>${esc(r.name)}</b>
      <span class="status ${refRoleColor(r.role)}">${esc(r.role || "Other")}</span>
      <div><code>${r.ref && r.ref.startsWith("asset://") ? esc(r.ref) : "(inline image)"}</code></div></div>
    <label style="flex-direction:row;align-items:center;gap:6px">role
      <select data-refrole="${i}">${roleOptions(r.role || "Other")}</select></label>
    <button class="btn small" data-rmref="${i}">remove</button></div>`).join("")
    || `<p class="muted">No references yet. Add at least a <b>Presenter</b> and a <b>Product</b>.</p>`;
}
$("#refList").addEventListener("click", e => { const b = e.target.closest("[data-rmref]"); if (b) { state.refs.splice(+b.dataset.rmref, 1); state.story = []; renderRefs(); } });
$("#refList").addEventListener("change", e => {
  const s = e.target.closest("[data-refrole]"); if (!s) return;
  state.refs[+s.dataset.refrole].role = s.value; state.story = [];   // rebuild storyboard bindings
  renderRefs(); toast("Role updated — storyboard references refreshed");
});

function addRef(obj) { state.refs.push(obj); state.story = []; renderRefs(); }   // reset story so chips refresh

// ── Agent-proposed reference set ─────────────────────────────────────────────
// Derive the Brand Kit the ad needs directly from the plan (presenter + product)
// as ready-to-generate Seedream prompts, so the user doesn't hand-build each ref.
function proposeRefs() {
  const p = state.plan; if (!p) return [];
  const out = [];
  const presenter = (p.presenter || "").trim();
  out.push({ role: "Presenter", name: "Presenter",
    prompt: `high quality, ultra-fine, 2K, photorealistic portrait. ${presenter || "a friendly, relatable brand presenter"}, `
      + `natural confident expression, looking straight at camera, upper-body framing. clean neutral studio background. `
      + `vertical 9:16, sharp focus. soft even studio lighting, true-to-life skin tones` });
  const product = (p.product || "").trim();
  if (product) out.push({ role: "Product", name: product,
    prompt: `high quality, ultra-fine, 2K, photorealistic product shot of ${product}${p.brand ? " by " + p.brand : ""}. `
      + `entire product centered and fully visible, accurate colours, materials and proportions. clean seamless studio background. `
      + `three-quarter hero angle. crisp commercial product-photography lighting, subtle reflection` });
  return out;
}
function renderProposals() {
  const box = $("#refProposals"); if (!box) return;
  const props = proposeRefs();
  if (!props.length) { box.classList.add("hidden"); box.innerHTML = ""; return; }
  box.classList.remove("hidden"); box._props = props;
  const done = pr => state.refs.some(r => r._prop === pr.name);
  const allDone = props.every(done);
  box.innerHTML = `<div class="propose">
    <div class="phead"><b>✨ Agent-proposed reference set</b>
      <button class="btn small primary" id="genAllProps" ${allDone ? "disabled" : ""}>Generate all proposed →</button></div>
    <p class="muted">From your Ad Plan the agent proposes the references this ad needs. Generate the whole set with
      one click — or upload your own real photos instead (recommended for a real product or a real presenter).</p>
    ${props.map((pr, i) => `<div class="proprow">
      <span class="status ${refRoleColor(pr.role)}">${esc(pr.role)}</span>
      <textarea id="pp-${i}" rows="2">${esc(pr.prompt)}</textarea>
      <button class="btn small" data-genprop="${i}" ${done(pr) ? "disabled" : ""}>${done(pr) ? "✓ added" : "Generate"}</button>
    </div>`).join("")}
    <p class="muted">Brand <b>logo</b>: upload your real logo file below (role = Logo) — don't generate a logo.</p>
  </div>`;
}
async function generateProposal(i) {
  const pr = $("#refProposals")._props[i];
  const prompt = ($(`#pp-${i}`).value.trim()) || pr.prompt;
  toast(`Generating ${pr.role} reference…`);
  try {
    const d = await api("/api/seedream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, size: "2K" }) });
    const ref = await registerAsset(d.url, pr.name, "Image");
    addRef({ url: d.url, ref, name: pr.name, role: pr.role, _prop: pr.name });
    renderProposals();
    toast(`${pr.role} reference ready`);
  } catch (e) { toast(e.message, true); }
}
$("#refProposals").addEventListener("click", async e => {
  const g = e.target.closest("[data-genprop]");
  if (g) return generateProposal(+g.dataset.genprop);
  if (e.target.id === "genAllProps") {
    const props = $("#refProposals")._props || [];
    for (let i = 0; i < props.length; i++) if (!state.refs.some(r => r._prop === props[i].name)) await generateProposal(i);
    toast("Reference set ready — review, then continue to Storyboard");
  }
});

$("#refUpload").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  const role = $("#refRole").value; const data = await blobToDataURL(f);
  try {
    if (role === "Presenter") {
      toast("Preparing presenter (Seedream trusted pass)…");
      const d = await api("/api/prepare-face", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ image: data }) });
      const ref = await registerAsset(d.url, f.name, "Image");
      addRef({ url: d.url, ref, name: f.name, role });
    } else {
      // Non-face references are used inline (base64) by Seedream/Seedance directly.
      addRef({ url: data, ref: data, name: f.name, role });
    }
    toast(`${role} reference added`);
  } catch (err) { toast(err.message, true); }
});
$("#pickAssetBtn").addEventListener("click", async () => {
  const box = $("#assetPicker");
  if (!box.classList.contains("hidden")) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden"); box.innerHTML = `<p class="muted">Loading asset library…</p>`;
  try {
    const d = await api("/api/list-assets");
    const imgs = (d.assets || []).filter(a => (a.asset_type || "").toLowerCase() === "image" && a.url);
    if (!imgs.length) { box.innerHTML = `<p class="muted">No image assets found in the group.</p>`; return; }
    box.innerHTML = `<p class="muted">Click an existing asset to reuse it as a reference:</p>
      <div class="pickgrid">` + imgs.map((a, i) =>
        `<div class="pick" data-i="${i}" title="${esc(a.name || a.id)}"><img src="${esc(a.url)}"><span>${esc((a.name || a.id).slice(0, 16))}</span></div>`).join("") + `</div>`;
    box._imgs = imgs;
  } catch (e) { box.innerHTML = `<p class="muted">Could not load assets: ${esc(e.message)}</p>`; }
});
$("#assetPicker").addEventListener("click", e => {
  const p = e.target.closest(".pick"); if (!p) return;
  const a = $("#assetPicker")._imgs[+p.dataset.i];
  addRef({ url: a.url, ref: "asset://" + a.id, name: a.name || a.id, role: $("#refRole").value });
  $("#assetPicker").classList.add("hidden"); toast(`${$("#refRole").value} reference added from library`);
});
$("#genRefBtn").addEventListener("click", async () => {
  const role = $("#refRole").value;
  const prompt = window.prompt(`Describe the ${role} reference to generate:`);
  if (!prompt) return;
  try {
    toast("Generating with Seedream…");
    const d = await api("/api/seedream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt, size: "2K" }) });
    const ref = await registerAsset(d.url, prompt.slice(0, 24), "Image");
    addRef({ url: d.url, ref, name: prompt.slice(0, 24), role });
    toast(`${role} reference generated`);
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

// STEP 4 storyboard — one editable card per scene; nothing generates until you ask.
const SAFETY_SUFFIX = " Exactly one product/subject in frame; no floating icons, holograms, shields, "
  + "UI graphics, badges or on-screen text; photorealistic advertising still, vertical 9:16.";

// Default reference selection for a new frame: presenter + product on, others off.
function defaultUseRefs() {
  return state.refs.map(r => r.role === "Presenter" || r.role === "Product");
}
function initStoryboard() {
  const scenes = (state.plan && state.plan.scenes) || [];
  state.story = scenes.map((s, i) => ({
    label: `Beat ${s.index || i + 1} · ${s.t_start ?? "?"}–${s.t_end ?? "?"}s`,
    scene: s,
    prompt: (s.keyframe_prompt || composeStoryPrompt(s)),
    useRefs: defaultUseRefs(),
    url: "", approved: false, seed: null, _st: "",
  }));
  renderStory();
}
function renderStoryboard() { if (!state.story.length) initStoryboard(); }

// Fallback composer if the plan lacks a keyframe_prompt (older plans).
function composeStoryPrompt(scene) {
  const product = (state.plan && state.plan.product) || "the product";
  return `high quality, ultra-fine, 2K, photorealistic. the presenter standing with a single ${product}. `
    + `${scene.camera || "vertical 9:16 framing"}. bright modern setting, cinematic advertising still, natural lighting`;
}

// Seedream 5.0 pro reference convention (from the official samples): references are
// cited INLINE as @image1, @image2… in natural language, each with a role-appropriate
// "match exactly / unchanged" instruction. `tags` is like "@image1" or "@image1 and @image2".
function refClause(role, tags, product) {
  if (role === "Presenter")
    return `The presenter is the person from ${tags}; their face, identity, skin tone, hair, build and proportions must match ${tags} exactly`;
  if (role === "Product")
    return `Feature the exact ${product} from ${tags} — its design, colour, materials, proportions and any markings/branding completely unchanged; it stays the clear focal point of the shot`;
  if (role === "Logo")
    return `Include the exact brand logo from ${tags}, its shape and colours unchanged`;
  if (role === "Style")
    return `Match the overall look, colour palette, mood and lighting of ${tags}`;
  return `Use ${tags} as a reference, matching it closely`;
}
// Short per-image label for the Seedance video omni-reference bindings.
function roleBinding(role, name) {
  const p = (state.plan && state.plan.product) || name || "the product";
  if (role === "Presenter") return "the presenter — match this person's identity exactly";
  if (role === "Product")   return `the exact ${p} — same design, colour and materials, unchanged`;
  if (role === "Logo")      return "the exact brand logo, unchanged";
  if (role === "Style")     return "a style/mood reference — match its look";
  return `${name || "a reference image"}`;
}

// Build the ordered list of selected refs for a frame (used for @Image numbering).
function selectedRefs(s) {
  return state.refs.filter((_, idx) => s.useRefs && s.useRefs[idx]);
}

async function storyGenerate(i, opts = {}) {
  const s = state.story[i];
  // Honor the user's edited prompt from the textarea.
  const ta = $(`#sp-${i}`); if (ta && !opts.editInstruction) s.prompt = ta.value.trim();

  let prompt, image;
  if (opts.editInstruction) {
    // In-place edit of the already-generated frame — single reference (that image).
    prompt = `${opts.editInstruction}. Keep the same people, product and scene; only apply this change. Photorealistic, vertical 9:16.`;
    image = opts.editImage;
  } else {
    const refs = selectedRefs(s);
    if (refs.length) {
      // Seedream-native: cite each reference inline as @imageN (numbered by send order),
      // grouped by role so several images of one subject bind together (Kling "Elements").
      const product = (state.plan && state.plan.product) || "the product";
      const byRole = {};
      refs.forEach((r, n) => { (byRole[r.role] = byRole[r.role] || []).push(`@image${n + 1}`); });
      const order = ["Presenter", "Product", "Logo", "Style", "Other"];
      const clauses = order.filter(rl => byRole[rl]).map(rl => refClause(rl, byRole[rl].join(" and "), product));
      // Scene describes pose/action/environment/camera/lighting (identity/product come from refs).
      prompt = `${clauses.join(". ")}. ${s.prompt}${SAFETY_SUFFIX}`;
      image = refs.map(r => r.url);            // multi-image reference array for Seedream, in @imageN order
    } else {
      // No references selected — fall back to the plan's presenter description.
      prompt = ((state.plan && state.plan.presenter) ? state.plan.presenter + ". " : "") + s.prompt + SAFETY_SUFFIX;
      image = null;
    }
  }
  const seed = opts.newSeed ? Math.floor(Math.random() * 2147483000) : (s.seed ?? undefined);
  s.seed = seed;
  setStory(i, opts.editInstruction ? "editing…" : "generating…", "run");
  try {
    const d = await api("/api/seedream", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, size: "2K", image, seed, optimize_prompt: false }) });
    s.url = d.url; s.approved = false; renderStory();
    setStory(i, opts.editInstruction ? "edited" : "generated", "ok");
  } catch (e) { setStory(i, "error", "err"); toast(`${s.label}: ${e.message}`, true); }
}
function renderStory() {
  const wrap = $("#storyCards"); wrap.innerHTML = "";
  const banner = el("div", "refinfo");
  banner.innerHTML = state.refs.length
    ? `🎯 <b>References drive appearance.</b> Toggle which Brand-Kit references each frame uses. Selected ones are cited inline as <code>@image1</code>, <code>@image2</code>… with "match exactly / unchanged" instructions (Seedream convention), so it reproduces that exact person AND that exact product — check each chip's role is right (person = Presenter, shoe = Product). The prompt controls pose &amp; scene only.`
    : `👤 <b>No references yet.</b> Frames will use the plan's presenter description only. Add a <b>Presenter</b> and <b>Product</b> in <b>Brand Kit</b> (Step 3) to lock the exact person and product.`;
  wrap.appendChild(banner);
  state.story.forEach((s, i) => {
    if (!s.useRefs || s.useRefs.length !== state.refs.length) s.useRefs = defaultUseRefs();
    const sel = selectedRefs(s);
    const chips = state.refs.map((r, idx) => {
      const on = s.useRefs[idx];
      const n = on ? sel.indexOf(r) + 1 : 0;   // @Image N among selected
      return `<button class="refchip ${on ? "on " + refRoleColor(r.role) : ""}" data-chip="${i}:${idx}" title="${esc(r.name)}">
        <img src="${esc(r.url)}">${on ? `<b>@${n}</b>` : ""} ${esc(r.role)}</button>`;
    }).join("");
    const c = el("div", "card" + (s.approved ? " approved" : ""));
    c.innerHTML = `<div class="head"><b>${esc(s.label)}</b><span class="status" id="ss-${i}">${esc(s._st || "")}</span></div>
      <div class="media">${s.url ? `<img src="${esc(s.url)}">` : "not generated yet"}</div>
      <div class="body">
        ${state.refs.length ? `<div class="chiprow">${chips}</div>` : ""}
        <label style="color:var(--muted);font-size:12px">Keyframe prompt (edit before generating)
          <textarea id="sp-${i}" rows="4">${esc(s.prompt)}</textarea>
        </label>
        <div class="actions">
          <button class="btn primary small" data-act="gen" data-i="${i}">${s.url ? "↻ Regenerate" : "Generate"}</button>
          <button class="btn small" data-act="edit" data-i="${i}" ${s.url ? "" : "disabled"}>✎ Edit image</button>
          <button class="btn small" data-act="approve" data-i="${i}" ${s.url ? "" : "disabled"}>${s.approved ? "✓ Approved (anchored)" : "Approve & anchor"}</button>
        </div>
      </div>`;
    $("#storyCards").appendChild(c);
  });
}
function setStory(i, t, c) { if (state.story[i]) state.story[i]._st = t; const e = $(`#ss-${i}`); if (e) { e.textContent = t; e.className = "status " + (c || ""); } }
$("#genStoryBtn").addEventListener("click", async () => {
  if (!state.story.length) initStoryboard();
  const pending = state.story.map((s, i) => i).filter(i => !state.story[i].url);
  if (!pending.length) return toast("All frames generated — use Regenerate on a card to redo one");
  for (const i of pending) await storyGenerate(i);
  toast("Done — Edit/Regenerate any frame, then Approve the ones to anchor");
});
$("#resetStoryBtn").addEventListener("click", () => { initStoryboard(); toast("Reloaded prompts from the plan"); });
$("#storyCards").addEventListener("click", async e => {
  const chip = e.target.closest("[data-chip]");
  if (chip) { const [i, idx] = chip.dataset.chip.split(":").map(Number); const s = state.story[i];
    s.useRefs[idx] = !s.useRefs[idx]; renderStory(); return; }
  const b = e.target.closest("[data-act]"); if (!b) return;
  const i = +b.dataset.i, act = b.dataset.act, s = state.story[i];
  if (act === "gen") return storyGenerate(i, { newSeed: !!s.url });
  if (act === "approve") { if (!s.url) return toast("Generate this frame first", true); s.approved = !s.approved; renderStory(); return; }
  if (act === "edit") {
    if (!s.url) return toast("Generate this frame first, then edit", true);
    const instr = window.prompt(`Edit instruction for ${s.label}\n(e.g. "remove the second car", "make the car dark grey", "fix the left hand")`);
    if (instr) storyGenerate(i, { editInstruction: instr, editImage: s.url });
  }
});

// STEP 5 generate
function collectRefs() {
  const imgs = state.refs.map(r => r.ref);
  const labels = state.refs.map(r => roleBinding(r.role, r.name));
  state.story.filter(s => s.approved && s.url).forEach(s => { imgs.push(s.url); labels.push(`approved ${s.label} storyboard frame — anchor this exact composition`); });
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
    : `<p class="muted">No overlay text in the plan — only Hindi VO captions (if enabled) will be burned.</p>`;
  // Preflight the compositor so the user knows before clicking.
  api("/api/overlay-preflight").then(d => {
    $("#ovWarn").innerHTML = d.ok ? "" : `<div>⚠ Overlay tools not ready: ${esc(d.message)}. Run <code>pip install imageio-ffmpeg Pillow</code>.</div>`;
  }).catch(() => {});
}
// Map aspect + resolution to pixel dimensions for the compositor.
function videoDims() {
  const aspect = (state.plan && state.plan.aspect) || $("#aspect").value || "9:16";
  const res = $("#res").value || "720p";
  const shortSide = res === "1080p" ? 1080 : res === "480p" ? 480 : 720;
  if (aspect === "1:1") return { w: shortSide, h: shortSide };
  if (aspect === "16:9") return { w: Math.round(shortSide * 16 / 9), h: shortSide };
  return { w: shortSide, h: Math.round(shortSide * 16 / 9) };   // 9:16 default
}
$("#renderOverlaysBtn").addEventListener("click", async () => {
  if (!state.videoUrl) return toast("Generate the ad first (step 5)", true);
  const logo = $("#ovLogo").checked ? (state.refs.find(r => r.role === "Logo") || {}).url : null;
  const { w, h } = videoDims();
  $("#ovStatus").textContent = "rendering…"; $("#ovStatus").className = "status run";
  try {
    const d = await api("/api/render-overlays", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_url: state.videoUrl, plan: state.plan, captions: $("#ovCaptions").checked,
        logo_url: logo, width: w, height: h }) });
    $("#ovStatus").textContent = `done (${d.overlay_count} overlays)`; $("#ovStatus").className = "status ok";
    $("#ovOut").innerHTML = `<video src="${esc(d.video_url)}" controls></video>
      <div><a href="${esc(d.video_url)}" download>⬇ Download branded MP4</a></div>`;
  } catch (e) { $("#ovStatus").textContent = "error"; $("#ovStatus").className = "status err"; toast(e.message, true); }
});

// boot
loadConfig().catch(e => toast(e.message, true));
loadBriefs().catch(() => {});
