/* Seedance 2.0 Studio — frontend */

const $ = (id) => document.getElementById(id);

const state = {
  groups: [],
  assets: [],
  filteredAssets: [],
  currentGroupId: "",
  typeFilter: "",       // "", "Image", "Video", "Audio"
  search: "",
  // selected references per type — Seedance 2.0 accepts up to 9 images, 3 videos, 3 audios
  refs:   { Image: [], Video: [], Audio: [] },
  limits: { Image: 9,  Video: 3,  Audio: 3  },
  history: [],          // [{task_id, prompt, created_at, status, video_url}]
  pollers: {},          // task_id -> intervalId
};

const LS_HISTORY = "seedance_studio_history_v1";

// ─── Boot ──────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", async () => {
  loadHistory();
  renderHistory();

  await checkConfig();
  await loadGroups();

  $("btn-refresh-groups").addEventListener("click", loadGroups);
  $("btn-generate").addEventListener("click", generate);
  $("btn-clear-history").addEventListener("click", clearHistory);

  $("group-picker").addEventListener("change", onGroupChange);
  $("asset-search").addEventListener("input", (e) => {
    state.search = e.target.value.trim().toLowerCase();
    renderAssets();
  });

  document.querySelectorAll("#type-filter .pill").forEach(btn => {
    btn.addEventListener("click", () => {
      state.typeFilter = btn.dataset.type || "";
      document.querySelectorAll("#type-filter .pill").forEach(b => b.classList.toggle("is-active", b === btn));
      // Either re-fetch (server-side filter) or filter locally — we re-fetch for accuracy
      if (state.currentGroupId) loadAssets(state.currentGroupId);
      else renderAssets();
    });
  });

  // slot URL inputs — Enter / blur to add as another reference
  document.querySelectorAll(".slot-url").forEach(inp => {
    const submit = () => {
      const t = inp.dataset.url;
      const url = inp.value.trim();
      if (!url) return;
      if (attachRef(t, { id: "", name: shortUrl(url), url, asset_type: t })) {
        inp.value = "";
      }
    };
    inp.addEventListener("change", submit);
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } });
  });

  // render initial empty slots (so counts show)
  ["Image", "Video", "Audio"].forEach(renderSlot);

  // drag-drop on slots
  document.querySelectorAll(".slot").forEach(slot => {
    slot.addEventListener("dragover", (e) => { e.preventDefault(); slot.classList.add("dragover"); });
    slot.addEventListener("dragleave", () => slot.classList.remove("dragover"));
    slot.addEventListener("drop", (e) => {
      e.preventDefault();
      slot.classList.remove("dragover");
      try {
        const payload = JSON.parse(e.dataTransfer.getData("application/json"));
        if (payload && payload.asset_type === slot.dataset.type) {
          attachRef(payload.asset_type, payload);
        } else {
          toastStatus(`Type mismatch — this slot accepts ${slot.dataset.type}`, "is-err");
        }
      } catch (_) {}
    });
  });
});

// ─── Config / health ──────────────────────────────────────────────────────
async function checkConfig() {
  try {
    const r = await fetch("/api/config");
    const d = await r.json();
    const chip = $("status-chip");
    if (d.api_key_configured && d.ak_configured && d.sk_configured) {
      chip.textContent = "● ready"; chip.classList.add("ok");
    } else {
      chip.textContent = "● missing keys"; chip.classList.add("warn");
    }
  } catch (e) {
    $("status-chip").textContent = "● offline"; $("status-chip").classList.add("err");
  }
}

// ─── Groups ────────────────────────────────────────────────────────────────
async function loadGroups() {
  const picker = $("group-picker");
  picker.innerHTML = `<option value="">— loading… —</option>`;
  $("library-status").textContent = "Loading groups…";
  try {
    const r = await fetch("/api/groups");
    const d = await r.json();
    if (d.error) throw new Error(JSON.stringify(d.error));
    state.groups = d.groups || [];
    picker.innerHTML = `<option value="">— select a group —</option>`;
    state.groups.forEach(g => {
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = `${g.name}  (${g.id.slice(0, 10)}…)`;
      picker.appendChild(opt);
    });
    $("library-status").textContent = `${d.total ?? state.groups.length} group(s)`;
  } catch (err) {
    $("library-status").textContent = `Error: ${err.message}`;
  }
}

function onGroupChange(e) {
  const id = e.target.value;
  state.currentGroupId = id;
  if (id) loadAssets(id);
  else {
    state.assets = [];
    renderAssets();
  }
}

// ─── Assets ────────────────────────────────────────────────────────────────
async function loadAssets(groupId) {
  $("asset-grid").innerHTML = `<div class="empty-state">Loading…</div>`;
  $("library-status").textContent = "Loading assets…";
  try {
    const params = new URLSearchParams();
    if (state.typeFilter) params.set("type", state.typeFilter);
    const r = await fetch(`/api/groups/${encodeURIComponent(groupId)}/assets?${params}`);
    const d = await r.json();
    if (d.error) throw new Error(JSON.stringify(d.error));
    state.assets = d.assets || [];
    $("library-status").textContent = `${d.total ?? state.assets.length} asset(s)`;
    renderAssets();
  } catch (err) {
    $("asset-grid").innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
  }
}

function renderAssets() {
  const grid = $("asset-grid");
  let list = state.assets;
  if (state.search) {
    list = list.filter(a =>
      (a.name || "").toLowerCase().includes(state.search) ||
      (a.id   || "").toLowerCase().includes(state.search)
    );
  }
  state.filteredAssets = list;
  if (!list.length) {
    grid.innerHTML = `<div class="empty-state">No assets to show.</div>`;
    return;
  }
  grid.innerHTML = "";
  list.forEach(a => grid.appendChild(buildAssetCard(a)));
}

function buildAssetCard(a) {
  const card = document.createElement("div");
  card.className = "asset-card";
  card.draggable = true;
  card.dataset.id = a.id;

  const badge = document.createElement("span");
  badge.className = "asset-type-badge";
  badge.textContent = a.asset_type || "?";
  card.appendChild(badge);

  // media preview
  if (a.asset_type === "Image" && a.url) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = a.url;
    img.alt = a.name || a.id;
    card.appendChild(img);
  } else if (a.asset_type === "Video" && a.url) {
    const v = document.createElement("video");
    v.src = a.url; v.muted = true; v.preload = "metadata"; v.playsInline = true;
    card.appendChild(v);
    // hover-play
    card.addEventListener("mouseenter", () => { v.play().catch(()=>{}); });
    card.addEventListener("mouseleave", () => { v.pause(); v.currentTime = 0; });
  } else if (a.asset_type === "Audio" && a.url) {
    const el = document.createElement("div");
    el.className = "asset-audio";
    el.textContent = "🎵";
    card.appendChild(el);
  } else {
    const el = document.createElement("div");
    el.className = "asset-audio";
    el.textContent = "?";
    card.appendChild(el);
  }

  const label = document.createElement("div");
  label.className = "asset-label";
  label.textContent = a.name || a.id;
  card.appendChild(label);

  // click → attach (append to that type's list, up to the per-type limit)
  card.addEventListener("click", () => {
    if (!a.asset_type) return;
    attachRef(a.asset_type, a);
  });

  // drag
  card.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("application/json", JSON.stringify(a));
    e.dataTransfer.effectAllowed = "copy";
  });

  // hover preview (audio + larger video preview)
  if (a.asset_type === "Audio" && a.url) {
    attachHoverPreview(card, () => {
      const el = document.createElement("audio");
      el.controls = true; el.src = a.url; el.autoplay = true;
      return el;
    });
  }

  return card;
}

function markSelected() {
  const selectedIds = new Set();
  ["Image", "Video", "Audio"].forEach(t => {
    state.refs[t].forEach(r => { if (r.id) selectedIds.add(r.id); });
  });
  document.querySelectorAll(".asset-card").forEach(c => {
    c.classList.toggle("is-selected", selectedIds.has(c.dataset.id));
  });
}

// ─── References (multi-asset per type) ─────────────────────────────────────
/** Returns true if the asset was attached, false if rejected (limit hit or dupe). */
function attachRef(type, asset) {
  if (!["Image", "Video", "Audio"].includes(type)) return false;
  const list  = state.refs[type];
  const limit = state.limits[type];

  if (list.length >= limit) {
    toastStatus(`Limit reached: max ${limit} ${type.toLowerCase()} reference(s)`, "is-err");
    return false;
  }
  // Dedupe by asset id (URL-only entries are always allowed)
  if (asset.id && list.some(r => r.id === asset.id)) {
    toastStatus(`Already added: ${asset.name || asset.id}`, "is-err");
    return false;
  }

  list.push({
    id:   asset.id  || "",
    name: asset.name || (asset.id || ""),
    url:  asset.url || "",
    asset_type: type,
  });
  renderSlot(type);
  markSelected();
  toastStatus(`Added ${type.toLowerCase()} reference (${list.length}/${limit})`, "is-ok");
  return true;
}

function removeRef(type, index) {
  state.refs[type].splice(index, 1);
  renderSlot(type);
  markSelected();
}

function renderSlot(type) {
  const slot     = document.querySelector(`.slot[data-type="${type}"]`);
  const list     = state.refs[type];
  const limit    = state.limits[type];
  const thumbs   = slot.querySelector(`.slot-thumbs`);
  const hint     = slot.querySelector(`.slot-hint`);
  const countEl  = slot.querySelector(`.slot-count`);
  const urlInput = slot.querySelector(`.slot-url`);

  countEl.textContent = `${list.length} / ${limit}`;
  slot.classList.toggle("has-asset", list.length > 0);
  hint.style.display = list.length ? "none" : "";
  urlInput.disabled  = list.length >= limit;
  urlInput.placeholder = list.length >= limit
    ? `Limit reached (${limit})`
    : `or paste a public URL + Enter`;

  thumbs.innerHTML = "";
  list.forEach((ref, idx) => {
    const t = document.createElement("div");
    t.className = "slot-thumb";
    t.title = ref.name + (ref.id ? "" : "  (URL)");

    let inner = "";
    if (type === "Image") {
      inner = `<img src="${escapeAttr(ref.url)}" alt="" />`;
    } else if (type === "Video") {
      inner = `<video src="${escapeAttr(ref.url)}" muted playsinline preload="metadata"></video>`;
    } else {
      inner = `<div class="thumb-audio">🎵</div>`;
    }
    t.innerHTML = `${inner}<button class="thumb-x" title="Remove">✕</button>`;

    t.querySelector(".thumb-x").addEventListener("click", (e) => {
      e.stopPropagation();
      removeRef(type, idx);
    });

    if (type === "Video") {
      const v = t.querySelector("video");
      t.addEventListener("mouseenter", () => v && v.play().catch(()=>{}));
      t.addEventListener("mouseleave", () => { if (v) { v.pause(); v.currentTime = 0; } });
    }
    thumbs.appendChild(t);
  });
}

// ─── Generate ──────────────────────────────────────────────────────────────
async function generate() {
  const prompt = $("prompt").value.trim();
  if (!prompt) { toastStatus("Prompt is required", "is-err"); return; }

  const references = [];
  for (const t of ["Image", "Video", "Audio"]) {
    for (const r of state.refs[t]) {
      references.push({
        type: t,
        asset_id: r.id || undefined,
        url: r.id ? undefined : r.url || undefined,
      });
    }
  }

  const body = {
    prompt,
    references,
    options: {
      ratio:      $("opt-ratio").value || undefined,
      duration:   $("opt-duration").value ? parseInt($("opt-duration").value, 10) : undefined,
      resolution: $("opt-resolution").value || undefined,
    },
  };

  toastStatus("Submitting…", "is-busy");
  $("btn-generate").disabled = true;
  $("inspector").textContent = JSON.stringify(body, null, 2);

  try {
    const r = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    $("inspector").textContent = JSON.stringify({ request: body, response: d }, null, 2);
    if (d.error) throw new Error(typeof d.error === "string" ? d.error : JSON.stringify(d.error));

    const taskId = d.id || d.task_id || (d.result && d.result.id);
    if (!taskId) throw new Error("No task id in response — see API Request Inspector.");

    const item = {
      task_id: taskId,
      prompt,
      created_at: Date.now(),
      status: "running",
      video_url: null,
    };
    state.history.unshift(item);
    saveHistory(); renderHistory();
    showOutputLoading(taskId);
    toastStatus(`Task ${taskId} submitted — polling…`, "is-busy");

    pollTask(taskId);
  } catch (err) {
    toastStatus(`Error: ${err.message}`, "is-err");
  } finally {
    $("btn-generate").disabled = false;
  }
}

function pollTask(taskId) {
  if (state.pollers[taskId]) return;
  const interval = setInterval(async () => {
    try {
      const r = await fetch(`/api/task/${encodeURIComponent(taskId)}`);
      const d = await r.json();
      const status = (d.status || "").toLowerCase();
      const item = state.history.find(h => h.task_id === taskId);
      if (item) {
        item.status = status || "running";
        if (d.video_url) item.video_url = d.video_url;
      }
      saveHistory(); renderHistory();

      if (d.video_url) {
        showOutputVideo(d.video_url, taskId);
        toastStatus(`✔ Generation complete`, "is-ok");
        clearInterval(interval); delete state.pollers[taskId];
        return;
      }
      if (["failed", "error", "cancelled"].includes(status)) {
        if (item) item.status = "failed";
        saveHistory(); renderHistory();
        showOutputError(`Task ${status}.`);
        toastStatus(`Task ${status}`, "is-err");
        clearInterval(interval); delete state.pollers[taskId];
      }
    } catch (e) {
      // keep polling; might be transient
    }
  }, 4000);
  state.pollers[taskId] = interval;
}

function showOutputLoading(taskId) {
  $("output-body").innerHTML = `
    <div class="output-loader">
      <div class="spinner"></div>
      <div>Generating… task <code>${escapeHTML(taskId)}</code></div>
    </div>`;
  $("output-meta").textContent = `Task ${taskId}`;
}
function showOutputVideo(url, taskId) {
  $("output-body").innerHTML = `<video src="${escapeAttr(url)}" controls autoplay></video>`;
  $("output-meta").textContent = `Task ${taskId}`;
}
function showOutputError(msg) {
  $("output-body").innerHTML = `<div class="empty-state" style="color: var(--danger)">${escapeHTML(msg)}</div>`;
}

// ─── History ───────────────────────────────────────────────────────────────
function loadHistory() {
  try {
    state.history = JSON.parse(localStorage.getItem(LS_HISTORY) || "[]");
  } catch { state.history = []; }
  // Resume polling for anything still running
  state.history.forEach(h => {
    if (h.status === "running" && !h.video_url) pollTask(h.task_id);
  });
}
function saveHistory() {
  // keep last 30
  state.history = state.history.slice(0, 30);
  localStorage.setItem(LS_HISTORY, JSON.stringify(state.history));
}
function clearHistory() {
  if (!confirm("Clear history?")) return;
  state.history = [];
  saveHistory(); renderHistory();
}
function renderHistory() {
  const wrap = $("history");
  if (!state.history.length) {
    wrap.innerHTML = `<div class="empty-state">Generated videos appear here.</div>`;
    return;
  }
  wrap.innerHTML = "";
  state.history.forEach(h => {
    const el = document.createElement("div");
    el.className = "history-item";
    const time = new Date(h.created_at).toLocaleString();
    const statusClass = h.status === "succeeded" || h.video_url ? "success"
                      : h.status === "failed" ? "failed" : "running";
    const statusText  = h.video_url ? "done" : (h.status || "running");

    const top = h.video_url
      ? `<video src="${escapeAttr(h.video_url)}" muted playsinline preload="metadata"></video>`
      : `<div class="history-item is-pending"><div class="output-loader"><div class="spinner"></div><div>Generating…</div></div></div>`;

    el.innerHTML = `
      ${top}
      <div class="history-meta">
        <span class="history-status ${statusClass}">${statusText}</span>
        <div class="history-prompt">${escapeHTML(h.prompt || "")}</div>
        <div class="history-time">${time}</div>
      </div>
    `;
    if (h.video_url) {
      const v = el.querySelector("video");
      el.addEventListener("mouseenter", () => v && v.play().catch(()=>{}));
      el.addEventListener("mouseleave", () => { if (v) { v.pause(); v.currentTime = 0; } });
      el.addEventListener("click", () => showOutputVideo(h.video_url, h.task_id));
    }
    wrap.appendChild(el);
  });
}

// ─── Hover preview popover ─────────────────────────────────────────────────
function attachHoverPreview(card, makeNode) {
  const pop = $("hover-preview");
  let node = null;
  card.addEventListener("mouseenter", (e) => {
    node = makeNode();
    pop.innerHTML = ""; pop.appendChild(node);
    pop.hidden = false;
    positionPopover(pop, e);
  });
  card.addEventListener("mousemove", (e) => positionPopover(pop, e));
  card.addEventListener("mouseleave", () => {
    pop.hidden = true; pop.innerHTML = "";
  });
}
function positionPopover(pop, evt) {
  const pad = 12;
  let x = evt.clientX + pad;
  let y = evt.clientY + pad;
  const rect = pop.getBoundingClientRect();
  if (x + rect.width  > window.innerWidth)  x = evt.clientX - rect.width  - pad;
  if (y + rect.height > window.innerHeight) y = evt.clientY - rect.height - pad;
  pop.style.left = `${x}px`;
  pop.style.top  = `${y}px`;
}

// ─── Utilities ─────────────────────────────────────────────────────────────
function toastStatus(msg, cls = "") {
  const el = $("composer-status");
  el.className = `composer-status ${cls}`;
  el.textContent = msg;
}
function shortUrl(u) {
  try { const x = new URL(u); return x.hostname + "…" + x.pathname.slice(-12); }
  catch { return u.slice(0, 24) + "…"; }
}
function escapeHTML(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
}
function escapeAttr(s) { return escapeHTML(s); }
