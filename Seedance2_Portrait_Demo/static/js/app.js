/* Seedance 2.0 Portrait Video Demo — Frontend Logic */
"use strict";

// ── State ────────────────────────────────────────────────────────
const state = {
  imageUrl: null,
  groupId: null,
  assetId: null,
  assetType: null,
  assetStatus: null,
  taskId: null,
  pollTimer: null,
  assetPollTimer: null,
  _fromPicker: false,
};

// ── DOM refs ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const imgUrlInput      = $("image-url-input");
const imgPreviewWrap   = $("image-preview-wrap");
const imgPreview       = $("image-preview");
const videoPreview     = $("video-preview");
const audioPreview     = $("audio-preview");
const imgError         = $("image-error");
const btnPreviewImage  = $("btn-preview-image");
const assetTypeSelect  = $("asset-type");
const btnRegister      = $("btn-register");
const assetTimeline    = $("asset-timeline");
const assetResult      = $("asset-result");
const videoTimeline    = $("video-timeline");
const taskIdRow        = $("task-id-row");
const btnGenerate      = $("btn-generate");
const videoResult      = $("video-result");
const videoPlaceholder = $("video-placeholder");
const assetNotice      = $("asset-notice");
const assetNoticeIcon  = $("asset-notice-icon");
const assetNoticeText  = $("asset-notice-text");
const progressWrap       = $("progress-wrap");
const progressFill       = $("progress-fill");
const progressLabel      = $("progress-label");
const assetPickerWrap    = $("asset-picker-wrap");
const assetPicker        = $("asset-picker");
const loadAssetsStatus   = $("load-assets-status");
const selectedAssetInfo  = $("selected-asset-info");

// ── Workflow step highlighter ────────────────────────────────────
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

// ── Image URL input ──────────────────────────────────────────────
imgUrlInput.addEventListener("input", () => {
  const url = imgUrlInput.value.trim();
  btnRegister.disabled = !url.startsWith("http");
  if (url.startsWith("http")) setWorkflowStep(2);
  else setWorkflowStep(1);
  imgError.classList.add("hidden");
});

function hideAllPreviews() {
  imgPreview.style.display = "none";
  videoPreview.style.display = "none";
  audioPreview.style.display = "none";
  imgPreview.src = "";
  videoPreview.src = "";
  audioPreview.src = "";
}

btnPreviewImage.addEventListener("click", () => {
  const url  = imgUrlInput.value.trim();
  const type = assetTypeSelect.value;
  if (!url) return;
  hideAllPreviews();
  imgError.classList.add("hidden");

  if (type === "Image") {
    imgPreview.src = url;
    imgPreview.style.display = "block";
    imgPreview.onload  = () => imgPreviewWrap.classList.remove("hidden");
    imgPreview.onerror = () => showError(imgError, "Could not load image from this URL. Ensure it is publicly accessible.");
  } else if (type === "Video") {
    videoPreview.src = url;
    videoPreview.style.display = "block";
    imgPreviewWrap.classList.remove("hidden");
    videoPreview.onerror = () => showError(imgError, "Could not load video from this URL. Ensure it is publicly accessible.");
  } else if (type === "Audio") {
    audioPreview.src = url;
    audioPreview.style.display = "block";
    imgPreviewWrap.classList.remove("hidden");
    audioPreview.onerror = () => showError(imgError, "Could not load audio from this URL. Ensure it is publicly accessible.");
  }
});

assetTypeSelect.addEventListener("change", () => {
  const placeholders = {
    Image: "https://example.com/portrait.jpg",
    Video: "https://example.com/clip.mp4",
    Audio: "https://example.com/voice.mp3",
  };
  imgUrlInput.placeholder = placeholders[assetTypeSelect.value] || placeholders.Image;
  hideAllPreviews();
  imgPreviewWrap.classList.add("hidden");
});

$("btn-clear-image").addEventListener("click", () => {
  imgUrlInput.value = "";
  state.imageUrl = null;
  imgPreviewWrap.classList.add("hidden");
  hideAllPreviews();
  btnRegister.disabled = true;
  imgError.classList.add("hidden");
  setWorkflowStep(1);
});

// ── Load existing asset groups ───────────────────────────────────
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
      Filter: { GroupType: "AIGC" },
      PageNumber: 1,
      PageSize: 50,
      SortBy: "CreateTime",
      SortOrder: "Desc",
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
      opt.value       = g.id;
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
    state.groupId = this.value;
    $("group-name").value = selected.dataset.name || "";
    $("out-group-id").textContent = this.value;
    $("asset-result").classList.remove("hidden");
    tlSet("tl-group", "done", `Using existing group: ${this.value}`);
    loadAssets(this.value);
  } else {
    state.groupId = null;
    $("out-group-id").textContent = "—";
    assetPickerWrap.classList.add("hidden");
    selectedAssetInfo.classList.add("hidden");
  }
});

async function loadAssets(groupId) {
  assetPickerWrap.classList.remove("hidden");
  loadAssetsStatus.textContent = "Loading…";
  assetPicker.innerHTML = '<option value="">— loading… —</option>';
  selectedAssetInfo.classList.add("hidden");

  const reqBody = {
    Filter: { GroupIds: [groupId], GroupType: "AIGC" },
    PageNumber: 1,
    PageSize: 50,
    SortBy: "CreateTime",
    SortOrder: "Desc",
    ProjectName: "default",
  };
  setInspector("req-list-assets", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=ListAssets&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: reqBody,
  });

  try {
    const r = await fetch(`/api/list-assets?group_id=${encodeURIComponent(groupId)}`);
    const d = await r.json();
    setInspector("res-list-assets", d);

    if (d.error) throw new Error(JSON.stringify(d.error));

    const assets = d.assets || [];
    assetPicker.innerHTML = '<option value="">— select an existing asset —</option>';
    assets.forEach(a => {
      const icon   = a.status === "Active" ? "✓" : a.status === "Failed" ? "✗" : "⏳";
      const opt    = document.createElement("option");
      opt.value    = a.id;
      opt.textContent = `${icon} ${a.name}  (${a.asset_type})  —  ${a.id}`;
      opt.dataset.assetType = a.asset_type;
      opt.dataset.status    = a.status;
      assetPicker.appendChild(opt);
    });

    loadAssetsStatus.textContent = `${d.total ?? assets.length} asset(s)`;
  } catch (err) {
    loadAssetsStatus.textContent = `Error: ${err.message}`;
    assetPicker.innerHTML = '<option value="">— failed to load —</option>';
  }
}

assetPicker.addEventListener("change", function () {
  const opt = this.options[this.selectedIndex];
  if (!this.value) {
    selectedAssetInfo.classList.add("hidden");
    if (state._fromPicker) {
      state.assetId     = null;
      state.assetType   = null;
      state.assetStatus = null;
      state._fromPicker = false;
      updateAssetStatusBadge("");
      assetNotice.classList.remove("ready");
      assetNoticeIcon.textContent = "⏳";
      assetNoticeText.textContent = "No asset selected. You can still generate without one.";
    }
    return;
  }

  const assetType = opt.dataset.assetType || "Image";
  const status    = opt.dataset.status || "";

  $("sel-asset-id").textContent   = this.value;
  $("sel-asset-type").textContent = assetType;
  const statusBadge = $("sel-asset-status");
  statusBadge.textContent = status;
  statusBadge.className   = `badge ${status}`;
  selectedAssetInfo.classList.remove("hidden");

  state.assetId     = this.value;
  state.assetType   = assetType;
  state.assetStatus = status;
  state._fromPicker = true;

  $("out-asset-id").textContent = this.value;
  assetResult.classList.remove("hidden");
  updateAssetStatusBadge(status);
});

// ── Register asset ───────────────────────────────────────────────
btnRegister.addEventListener("click", registerAsset);

async function registerAsset() {
  const imageUrl = imgUrlInput.value.trim();
  if (!imageUrl) return;

  state.imageUrl = imageUrl;
  btnRegister.disabled = true;
  btnRegister.textContent = "Registering…";
  assetTimeline.classList.remove("hidden");
  assetResult.classList.remove("hidden");
  setWorkflowStep(2);

  // ── Step 1: Create asset group (skip if an existing group was selected) ──
  if (state.groupId) {
    tlSet("tl-group", "done", `Reusing group: ${state.groupId}`);
  } else {
    const groupName = $("group-name").value.trim() || "My Portrait Group";
    const groupReq  = { name: groupName, description: "Trusted face assets for Seedance 2.0 video generation" };

    tlSet("tl-group", "active", "Creating asset group…");
    setInspector("req-group", {
      method: "POST",
      url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAssetGroup&Version=2024-01-01",
      auth: "HMAC-SHA256 AK/SK signature",
      body: { Name: groupName, Description: groupReq.description, GroupType: "AIGC", ProjectName: "default" },
    });

    try {
      const r = await fetch("/api/create-asset-group", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(groupReq),
      });
      const groupResp = await r.json();
      setInspector("res-group", groupResp);

      if (groupResp.error) throw new Error(JSON.stringify(groupResp.error));

      state.groupId = groupResp.id;
      $("out-group-id").textContent = state.groupId;
      tlSet("tl-group", "done", `Group ID: ${state.groupId}`);
    } catch (err) {
      tlSet("tl-group", "error", `Failed: ${err.message}`);
      resetRegisterButton();
      return;
    }
  }

  // ── Step 2: Create asset with public URL ────────────────────
  const assetName = $("asset-name").value.trim() || "Portrait Asset";
  const assetType = assetTypeSelect.value || "Image";
  tlSet("tl-upload", "active", `Registering ${assetType.toLowerCase()} asset…`);

  const assetBody = { group_id: state.groupId, name: assetName, url: imageUrl, asset_type: assetType };

  setInspector("req-asset", {
    method: "POST",
    url: "https://ark.ap-southeast-1.byteplusapi.com/?Action=CreateAsset&Version=2024-01-01",
    auth: "HMAC-SHA256 AK/SK signature",
    body: { GroupId: state.groupId, URL: imageUrl, AssetType: assetType, Name: assetName, ProjectName: "default" },
  });

  let assetResp;
  try {
    const r = await fetch("/api/create-asset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(assetBody),
    });
    assetResp = await r.json();
    setInspector("res-asset", assetResp);

    if (assetResp.error) throw new Error(JSON.stringify(assetResp.error));

    state.assetId     = assetResp.id;
    state.assetType   = assetResp.asset_type || assetType;
    state._fromPicker = false;
    $("out-asset-id").textContent = state.assetId;
    tlSet("tl-upload", "done", `${state.assetType} asset ID: ${state.assetId}`);
  } catch (err) {
    tlSet("tl-upload", "error", `Failed: ${err.message}`);
    resetRegisterButton();
    return;
  }

  // ── Step 3: Poll asset status ───────────────────────────────
  tlSet("tl-verify", "active", "Waiting for asset verification…");
  pollAssetStatus();
}

function updateAssetStatusBadge(status) {
  const badge = $("out-asset-status");
  badge.textContent = status;
  badge.className = `badge ${status}`;

  // API returns capitalized statuses: Active | Processing | Failed
  if (status === "Active") {
    state.assetStatus = "Active";
    assetNotice.classList.add("ready");
    assetNoticeIcon.textContent = "✓";
    const typeLabel = (state.assetType || "Asset").toLowerCase();
    assetNoticeText.textContent = `${typeLabel.charAt(0).toUpperCase()}${typeLabel.slice(1)} asset ready (ID: ${state.assetId})`;
    setWorkflowStep(3);
  } else if (status === "Failed") {
    assetNotice.classList.remove("ready");
    assetNoticeIcon.textContent = "✗";
    assetNoticeText.textContent = "Asset verification failed. You can still generate without it.";
  } else {
    assetNoticeIcon.textContent = "⏳";
    assetNoticeText.textContent = `Asset status: ${status}. Polling…`;
  }
}

function pollAssetStatus() {
  if (!state.assetId) return;
  let attempts = 0;

  const poll = async () => {
    attempts++;
    try {
      const r = await fetch(`/api/asset-status/${state.assetId}`);
      const d = await r.json();
      updateAssetStatusBadge(d.status);

      if (d.status === "Active") {
        tlSet("tl-verify", "done", "Asset verified and active");
        resetRegisterButton();
        return;
      }
      if (d.status === "Failed") {
        tlSet("tl-verify", "error", "Verification failed");
        resetRegisterButton();
        return;
      }

      tlSet("tl-verify", "active", `Attempt ${attempts} — status: ${d.status}`);
      if (attempts < 24) {
        state.assetPollTimer = setTimeout(poll, 5000);
      } else {
        tlSet("tl-verify", "active", "Still processing — you can generate video when asset is ready");
        resetRegisterButton();
      }
    } catch (err) {
      tlSet("tl-verify", "error", err.message);
      resetRegisterButton();
    }
  };

  state.assetPollTimer = setTimeout(poll, 3000);
}

function resetRegisterButton() {
  btnRegister.disabled = false;
  btnRegister.textContent = "Register Asset";
}

// ── Sample prompts ───────────────────────────────────────────────
document.querySelectorAll(".chip[data-prompt]").forEach(chip => {
  chip.addEventListener("click", () => {
    $("video-prompt").value = chip.dataset.prompt;
  });
});

// ── Generate video ───────────────────────────────────────────────
btnGenerate.addEventListener("click", generateVideo);

async function generateVideo() {
  const prompt  = $("video-prompt").value.trim();
  const modelId = $("model-id").value.trim();

  if (!prompt) {
    alert("Please enter a video prompt.");
    return;
  }

  btnGenerate.disabled = true;
  btnGenerate.textContent = "Submitting…";
  videoTimeline.classList.remove("hidden");
  taskIdRow.classList.remove("hidden");
  progressWrap.classList.remove("hidden");
  videoResult.classList.add("hidden");
  videoPlaceholder.classList.remove("hidden");
  setWorkflowStep(4);

  // ── Submit task ─────────────────────────────────────────────
  const assetType = state.assetType || "Image";
  const body = { prompt, model_id: modelId };
  if (state.assetId && state.assetStatus === "Active") {
    body.asset_id   = state.assetId;
    body.asset_type = assetType;
  }

  // Build the BytePlus-format payload preview for the inspector.
  // Seedance uses different type/role/url-container keys per modality.
  const REFERENCE_FIELDS = {
    Image: { type: "image_url", role: "reference_image" },
    Video: { type: "video_url", role: "reference_video" },
    Audio: { type: "audio_url", role: "reference_audio" },
  };
  const previewContent = [{ type: "text", text: prompt }];
  if (state.assetId && state.assetStatus === "Active") {
    const ref = REFERENCE_FIELDS[assetType] || REFERENCE_FIELDS.Image;
    previewContent.push({
      type: ref.type,
      role: ref.role,
      [ref.type]: { url: `asset://${state.assetId}` },
    });
  }
  const previewPayload = { model: modelId, content: previewContent, watermark: false };
  const ratioM = prompt.match(/--ratio\s+(\S+)/);
  const durM   = prompt.match(/--duration\s+(\d+)/);
  const resM   = prompt.match(/--resolution\s+(\S+)/);
  if (ratioM) previewPayload.ratio      = ratioM[1];
  if (durM)   previewPayload.duration   = parseInt(durM[1]);
  if (resM)   previewPayload.resolution = resM[1];

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

  // ── Poll task ───────────────────────────────────────────────
  tlSet("tl-poll", "active", "Video processing…");
  pollVideoTask();
}

function updateTaskBadge(status) {
  const badge = $("out-task-status");
  badge.textContent = status;
  badge.className   = `badge ${status}`;
}

let pollAttempts = 0;
const MAX_POLL = 72;  // ~12 min at 10s interval

function pollVideoTask() {
  pollAttempts = 0;

  const poll = async () => {
    pollAttempts++;
    const pct = Math.min(95, (pollAttempts / MAX_POLL) * 100);
    progressFill.style.width = `${pct}%`;
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
        const videoUrl = d._video_url;
        tlSet("tl-poll", "done", "Processing complete");
        tlSet("tl-done", "done", videoUrl || "Video ready");
        setWorkflowStep(5);
        showVideo(videoUrl);
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
  videoPlaceholder.classList.add("hidden");
  videoResult.classList.remove("hidden");
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
  btnGenerate.disabled = false;
  btnGenerate.textContent = "Generate Video";
}

// ── Helpers ──────────────────────────────────────────────────────
function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

// ── Init ─────────────────────────────────────────────────────────
checkApiConfig();
setWorkflowStep(1);
