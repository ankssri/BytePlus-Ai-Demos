/* Real-Human Portrait Demo — Frontend Logic */
"use strict";

// ── State ────────────────────────────────────────────────────────
const state = {
  groupId:        null,
  // registeredAssets: [{asset_id, asset_type, name, status, ref_label}]
  registeredAssets: [],
  taskId:         null,
  pollTimer:      null,
  assetPollTimer: null,
};

// ── DOM refs ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Workflow step highlighter ─────────────────────────────────────
function setWorkflowStep(n) {
  for (let i = 1; i <= 5; i++) {
    const el = $(`wf${i}`);
    el.classList.remove("active", "done");
    if (i < n)  el.classList.add("done");
    if (i === n) el.classList.add("active");
  }
}

// ── API status check ─────────────────────────────────────────────
async function checkApiConfig() {
  try {
    const r = await fetch("/api/config");
    const d = await r.json();
    const badge = $("api-status");
    const allConfigured = d.api_key_configured && d.ak_configured && d.sk_configured;
    if (allConfigured) {
      badge.textContent = "API Connected ✓";
      badge.className = "api-badge ok";
    } else if (d.api_key_configured) {
      badge.textContent = "AK/SK Missing ⚠";
      badge.className = "api-badge error";
    } else {
      badge.textContent = "API Key Missing ✗";
      badge.className = "api-badge error";
    }
  } catch {
    $("api-status").textContent = "Cannot reach server";
    $("api-status").className = "api-badge error";
  }
}

// ── Inspector tabs ───────────────────────────────────────────────
document.querySelectorAll(".itab").forEach(tab => {
  tab.addEventListener("click", () => {
    const container = tab.closest(".inspector");
    container.querySelectorAll(".itab").forEach(t => t.classList.remove("active"));
    container.querySelectorAll(".code-block").forEach(b => b.classList.add("hidden"));
    tab.classList.add("active");
    const target = container.querySelector(`#${tab.dataset.tab}`);
    if (target) target.classList.remove("hidden");
  });
});

function setInspector(id, obj) {
  const el = $(id);
  if (el) el.textContent = JSON.stringify(obj, null, 2);
}

// ── Timeline helpers ─────────────────────────────────────────────
function tlSet(id, tlState, detail) {
  const item = $(id);
  if (!item) return;
  item.className = `tl-item ${tlState}`;
  const d = item.querySelector(".tl-detail");
  if (d) d.textContent = detail;
}

// ── STEP 1: Load existing groups ──────────────────────────────────
$("btn-load-groups").addEventListener("click", loadAssetGroups);

async function loadAssetGroups() {
  const statusEl = $("load-groups-status");
  const btn      = $("btn-load-groups");
  btn.disabled   = true;
  statusEl.textContent = "Loading…";

  setInspector("req-list-groups", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssetGroups&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: {
      Filter: { GroupType: "LivenessFace" },
      PageNumber: 1, PageSize: 50,
      SortBy: "CreateTime", SortOrder: "Desc",
      ProjectName: "default",
    },
  });

  try {
    const r = await fetch("/api/list-asset-groups");
    const d = await r.json();
    setInspector("res-list-groups", d);

    if (d.error) throw new Error(JSON.stringify(d.error));

    const picker = $("group-picker");
    picker.innerHTML = '<option value="">— create a new group below —</option>';
    (d.groups || []).forEach(g => {
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = `${g.name}  (${g.id})`;
      opt.dataset.name = g.name;
      picker.appendChild(opt);
    });

    $("group-picker-wrap").classList.remove("hidden");
    statusEl.textContent = `${d.total ?? d.groups.length} group(s) found`;
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
  }
}

$("group-picker").addEventListener("change", function () {
  const selected = this.options[this.selectedIndex];
  if (this.value) {
    setGroupId(this.value);
    $("group-name").value = selected.dataset.name || "";
  } else {
    state.groupId = null;
    $("group-result").classList.add("hidden");
    $("asset-form").classList.add("hidden");
    $("group-required-notice").classList.remove("hidden");
  }
});

// ── STEP 1: Create new group ─────────────────────────────────────
$("btn-create-group").addEventListener("click", createAssetGroup);

async function createAssetGroup() {
  const name = $("group-name").value.trim() || "My Real-Human Group";
  const desc = $("group-desc").value.trim();
  const btn  = $("btn-create-group");
  btn.disabled = true;
  btn.textContent = "Creating…";

  const reqBody = { Name: name, Description: desc, GroupType: "LivenessFace", ProjectName: "default" };
  setInspector("req-create-group", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAssetGroup&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: reqBody,
  });

  try {
    const r = await fetch("/api/create-asset-group", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description: desc }),
    });
    const d = await r.json();
    setInspector("res-create-group", d);

    if (d.error) throw new Error(JSON.stringify(d.error));

    setGroupId(d.id);
    setWorkflowStep(2);
  } catch (err) {
    alert(`Create group failed: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Create New Group";
  }
}

function setGroupId(id) {
  state.groupId = id;
  $("out-group-id").textContent = id;
  $("group-result").classList.remove("hidden");
  $("group-required-notice").classList.add("hidden");
  $("asset-form").classList.remove("hidden");
  $("btn-add-asset").disabled = false;
  $("assets-list-wrap").classList.remove("hidden");
  setWorkflowStep(2);
}

// ── STEP 2: Register asset URL ───────────────────────────────────
$("asset-url-input").addEventListener("input", () => {
  const url = $("asset-url-input").value.trim();
  $("btn-add-asset").disabled = !(url.startsWith("http") && state.groupId);
});

$("btn-add-asset").addEventListener("click", registerAsset);

async function registerAsset() {
  const assetUrl  = $("asset-url-input").value.trim();
  const assetType = $("asset-type-select").value;
  const assetName = $("asset-name-input").value.trim() || `${assetType} Asset`;
  const btn       = $("btn-add-asset");

  if (!assetUrl || !state.groupId) return;

  btn.disabled = true;
  btn.textContent = "Registering…";
  $("asset-timeline").classList.remove("hidden");

  tlSet("tl-upload", "active", "Registering asset URL…");

  const reqBody = {
    GroupId: state.groupId, URL: assetUrl,
    AssetType: assetType, Name: assetName, ProjectName: "default",
  };
  setInspector("req-asset", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAsset&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: reqBody,
  });

  let assetId;
  try {
    const r = await fetch("/api/create-asset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        group_id: state.groupId,
        url: assetUrl,
        asset_type: assetType,
        name: assetName,
      }),
    });
    const d = await r.json();
    setInspector("res-asset", d);

    if (d.error) throw new Error(JSON.stringify(d.error));

    assetId = d.id;
    tlSet("tl-upload", "done", `Asset ID: ${assetId}`);
  } catch (err) {
    tlSet("tl-upload", "error", `Failed: ${err.message}`);
    btn.disabled = false;
    btn.textContent = "Register Asset";
    return;
  }

  // Add to list as Processing immediately
  const entry = { asset_id: assetId, asset_type: assetType, name: assetName, status: "Processing" };
  state.registeredAssets.push(entry);
  renderAssetList();

  // Poll for Active status
  tlSet("tl-verify", "active", "Waiting for verification…");
  pollAsset(assetId, entry, () => {
    btn.disabled = false;
    btn.textContent = "Register Asset";
    $("asset-url-input").value = "";
    updateAssetRefGuide();
    updateAssetNotice();
  });
}

function pollAsset(assetId, entry, onDone) {
  let attempts = 0;
  const poll = async () => {
    attempts++;
    try {
      const r = await fetch(`/api/asset-status/${assetId}`);
      const d = await r.json();
      entry.status = d.status;
      renderAssetList();

      if (d.status === "Active") {
        tlSet("tl-verify", "done", "Asset verified and active");
        onDone();
        return;
      }
      if (d.status === "Failed") {
        tlSet("tl-verify", "error", "Verification failed");
        onDone();
        return;
      }

      tlSet("tl-verify", "active", `Attempt ${attempts} — ${d.status}`);
      if (attempts < 30) {
        state.assetPollTimer = setTimeout(poll, 5000);
      } else {
        tlSet("tl-verify", "active", "Still processing — check back later");
        onDone();
      }
    } catch (err) {
      tlSet("tl-verify", "error", err.message);
      onDone();
    }
  };
  state.assetPollTimer = setTimeout(poll, 3000);
}

// ── Asset list rendering ─────────────────────────────────────────

function getRefLabel(asset) {
  const sameType = state.registeredAssets.filter(a => a.asset_type === asset.asset_type);
  const idx = sameType.indexOf(asset);
  if (idx === -1) return `${asset.asset_type} ?`;
  return `${asset.asset_type} ${idx + 1}`;
}

function renderAssetList() {
  const list = $("assets-list");
  if (!list) return;
  if (state.registeredAssets.length === 0) {
    list.innerHTML = '<p style="color:var(--text-muted);font-size:0.82rem">No assets registered yet.</p>';
    return;
  }

  list.innerHTML = "";
  state.registeredAssets.forEach((asset) => {
    const label = getRefLabel(asset);
    asset.ref_label = label;
    const div = document.createElement("div");
    div.className = "asset-row";
    div.innerHTML = `
      <span class="asset-label-tag">${label}</span>
      <span class="asset-type-icon">${assetTypeIcon(asset.asset_type)}</span>
      <span class="asset-name">${asset.name || asset.asset_id}</span>
      <code class="asset-id-code">${asset.asset_id}</code>
      <span class="badge ${asset.status === 'Active' ? 'active' : asset.status === 'Failed' ? 'failed' : 'processing'}">${asset.status}</span>
    `;
    list.appendChild(div);
  });
}

function assetTypeIcon(type) {
  if (type === "Video") return "🎞️";
  if (type === "Audio") return "🔊";
  return "🖼️";
}

// ── Refresh assets from API ──────────────────────────────────────
$("btn-refresh-assets").addEventListener("click", refreshAssetList);

async function refreshAssetList() {
  if (!state.groupId) return;
  const statusEl = $("refresh-status");
  statusEl.textContent = "Loading…";

  const reqBody = {
    Filter: { GroupIds: [state.groupId], GroupType: "LivenessFace" },
    PageNumber: 1, PageSize: 50,
    SortBy: "CreateTime", SortOrder: "Desc", ProjectName: "default",
  };
  setInspector("req-list-assets", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssets&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: reqBody,
  });

  try {
    const r = await fetch(`/api/list-assets?group_id=${encodeURIComponent(state.groupId)}`);
    const d = await r.json();
    setInspector("res-list-assets", d);

    if (d.error) throw new Error(JSON.stringify(d.error));

    state.registeredAssets = (d.assets || []).map(a => ({
      asset_id:   a.id,
      asset_type: a.asset_type || "Image",
      name:       a.name || "",
      status:     a.status || "Processing",
    }));

    renderAssetList();
    updateAssetRefGuide();
    updateAssetNotice();
    statusEl.textContent = `${d.total ?? d.assets.length} asset(s) loaded`;
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  }
}

// ── Asset reference guide for prompt panel ───────────────────────
function updateAssetRefGuide() {
  const active = state.registeredAssets.filter(a => a.status === "Active");
  const guide  = $("asset-ref-guide");
  const list   = $("asset-ref-list");

  if (active.length === 0) {
    guide.classList.add("hidden");
    return;
  }

  guide.classList.remove("hidden");
  list.innerHTML = "";
  active.forEach(asset => {
    const label = getRefLabel(asset);
    const span = document.createElement("span");
    span.className = "ref-tag";
    span.textContent = `${label} — ${asset.name || asset.asset_id}`;
    list.appendChild(span);
  });
}

function updateAssetNotice() {
  const active = state.registeredAssets.filter(a => a.status === "Active");
  const icon   = $("asset-notice-icon");
  const text   = $("asset-notice-text");
  const notice = $("asset-notice");

  if (active.length > 0) {
    notice.classList.add("ready");
    icon.textContent = "✓";
    text.textContent = `${active.length} active asset(s) ready — reference them in the prompt using Image 1, Image 2, Audio 1, etc.`;
    setWorkflowStep(3);
  } else {
    notice.classList.remove("ready");
    icon.textContent = "⏳";
    text.textContent = "No active assets yet. Register assets in Steps 1 & 2 first.";
  }
}

// ── Sample prompts ───────────────────────────────────────────────
document.querySelectorAll(".chip[data-prompt]").forEach(chip => {
  chip.addEventListener("click", () => {
    $("video-prompt").value = chip.dataset.prompt;
  });
});

// ── Generate video ───────────────────────────────────────────────
$("btn-generate").addEventListener("click", generateVideo);

async function generateVideo() {
  const prompt        = $("video-prompt").value.trim();
  const modelId       = $("model-id").value.trim();
  const generateAudio = $("opt-generate-audio").checked;

  if (!prompt) {
    alert("Please enter a video prompt.");
    return;
  }

  const activeAssets = state.registeredAssets.filter(a => a.status === "Active");

  const btn = $("btn-generate");
  btn.disabled = true;
  btn.textContent = "Submitting…";
  $("video-timeline").classList.remove("hidden");
  $("task-id-row").classList.remove("hidden");
  $("progress-wrap").classList.remove("hidden");
  $("video-result").classList.add("hidden");
  $("video-placeholder").classList.remove("hidden");
  setWorkflowStep(4);

  const assetsPayload = activeAssets.map(a => ({
    asset_id:   a.asset_id,
    asset_type: a.asset_type,
  }));

  const body = { prompt, model_id: modelId, assets: assetsPayload, generate_audio: generateAudio };

  // Build inspector preview
  const ratioM = prompt.match(/--ratio\s+(\S+)/);
  const durM   = prompt.match(/--duration\s+(\d+)/);
  const resM   = prompt.match(/--resolution\s+(\S+)/);
  const cleanPrompt = prompt
    .replace(/--ratio\s+\S+/, "")
    .replace(/--duration\s+\d+/, "")
    .replace(/--resolution\s+\S+/, "")
    .trim();

  const previewContent = [{ type: "text", text: cleanPrompt }];
  activeAssets.forEach(a => {
    if (a.asset_type === "Audio") {
      previewContent.push({ type: "audio_url", role: "reference_audio", audio_url: { url: `asset://${a.asset_id}` } });
    } else {
      previewContent.push({ type: "image_url", role: "reference_image", image_url: { url: `asset://${a.asset_id}` } });
    }
  });
  const previewPayload = { model: modelId, content: previewContent, watermark: false };
  if (ratioM) previewPayload.ratio      = ratioM[1];
  if (durM)   previewPayload.duration   = parseInt(durM[1]);
  if (resM)   previewPayload.resolution = resM[1];
  if (generateAudio) previewPayload.generate_audio = true;

  setInspector("req-video", {
    method: "POST",
    url: "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks",
    auth: "Bearer API Key",
    body: previewPayload,
  });

  tlSet("tl-submit", "active", "Submitting video task…");

  let taskResp;
  try {
    const r = await fetch("/api/create-video-task", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    taskResp = await r.json();

    if (taskResp._byteplus_request) {
      setInspector("req-video", {
        method: "POST",
        url: "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks",
        auth: "Bearer API Key",
        body: taskResp._byteplus_request,
      });
    }
    setInspector("res-video-create", taskResp);

    if (taskResp.error) throw new Error(JSON.stringify(taskResp.error));

    state.taskId = taskResp.id;
    $("out-task-id").textContent = state.taskId;
    updateTaskBadge(taskResp.status || "queued");
    tlSet("tl-submit", "done", `Task ID: ${state.taskId}`);
  } catch (err) {
    tlSet("tl-submit", "error", `Failed: ${err.message}`);
    resetGenerateButton();
    return;
  }

  tlSet("tl-poll", "active", "Video processing…");
  pollVideoTask();
}

function updateTaskBadge(status) {
  const badge = $("out-task-status");
  badge.textContent = status;
  badge.className   = `badge ${status}`;
}

let pollAttempts = 0;
const MAX_POLL = 72;

function pollVideoTask() {
  pollAttempts = 0;
  const progressFill  = $("progress-fill");
  const progressLabel = $("progress-label");

  const poll = async () => {
    pollAttempts++;
    const pct = Math.min(95, (pollAttempts / MAX_POLL) * 100);
    progressFill.style.width  = `${pct}%`;
    progressLabel.textContent = `${pollAttempts} / ${MAX_POLL} polls`;

    try {
      const r = await fetch(`/api/video-task/${state.taskId}`);
      const d = await r.json();
      setInspector("res-video-poll", d);

      const status = d.status || "";
      updateTaskBadge(status);
      tlSet("tl-poll", "active", `Poll #${pollAttempts} — ${status}`);

      if (status === "succeeded") {
        progressFill.style.width = "100%";
        tlSet("tl-poll", "done", "Processing complete");
        tlSet("tl-done", "done", d._video_url || "Video ready");
        setWorkflowStep(5);
        showVideo(d._video_url);
        resetGenerateButton();
        return;
      }

      if (status === "failed") {
        const msg = (d.error || {}).message || "Unknown error";
        tlSet("tl-poll", "error", `Failed: ${msg}`);
        tlSet("tl-done", "error", "Generation failed");
        resetGenerateButton();
        return;
      }

      if (pollAttempts < MAX_POLL) {
        state.pollTimer = setTimeout(poll, 10000);
      } else {
        tlSet("tl-poll", "active", `Max polls reached. Task ID: ${state.taskId}`);
        resetGenerateButton();
      }
    } catch (err) {
      tlSet("tl-poll", "error", err.message);
      resetGenerateButton();
    }
  };

  state.pollTimer = setTimeout(poll, 5000);
}

function showVideo(url) {
  if (!url) return;
  $("video-placeholder").classList.add("hidden");
  $("video-result").classList.remove("hidden");
  const vid = $("result-video");
  vid.src = url;
  vid.load();
  $("video-download-link").href = url;
  $("video-url-display").textContent = url;
}

$("btn-copy-url").addEventListener("click", () => {
  const url = $("video-url-display").textContent;
  if (url) navigator.clipboard.writeText(url).then(() => {
    $("btn-copy-url").textContent = "Copied!";
    setTimeout(() => { $("btn-copy-url").textContent = "⎘ Copy URL"; }, 1500);
  });
});

function resetGenerateButton() {
  const btn = $("btn-generate");
  btn.disabled = false;
  btn.textContent = "Generate Video";
}

// ── Init ─────────────────────────────────────────────────────────
checkApiConfig();
setWorkflowStep(1);
renderAssetList();
