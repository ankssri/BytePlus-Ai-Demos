/* Seedance 2.0 Portrait Video Demo — Frontend Logic */
"use strict";

// ── State ────────────────────────────────────────────────────────
const state = {
  imageFile: null,
  imageBase64: null,
  groupId: null,
  assetId: null,
  assetStatus: null,
  taskId: null,
  pollTimer: null,
  assetPollTimer: null,
};

// ── DOM refs ─────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dropZone         = $("drop-zone");
const faceInput        = $("face-input");
const imgPreviewWrap   = $("image-preview-wrap");
const imgPreview       = $("image-preview");
const imgMeta          = $("image-meta");
const imgError         = $("image-error");
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
const progressWrap     = $("progress-wrap");
const progressFill     = $("progress-fill");
const progressLabel    = $("progress-label");

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
    if (d.api_key_configured) {
      badge.textContent = "API Connected ✓";
      badge.className = "api-badge ok";
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
function tlSet(id, state, detail) {
  const item = $(id);
  if (!item) return;
  item.className = `tl-item ${state}`;
  const d = item.querySelector(".tl-detail");
  if (d) d.textContent = detail;
}

// ── Image drop / upload ─────────────────────────────────────────
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleImageFile(file);
});
faceInput.addEventListener("change", () => {
  if (faceInput.files[0]) handleImageFile(faceInput.files[0]);
});
$("btn-clear-image").addEventListener("click", clearImage);

async function handleImageFile(file) {
  imgError.classList.add("hidden");

  const formData = new FormData();
  formData.append("image", file);

  // Local preview first
  const reader = new FileReader();
  reader.onload = e => {
    imgPreview.src = e.target.result;
    imgPreviewWrap.classList.remove("hidden");
    dropZone.classList.add("hidden");
  };
  reader.readAsDataURL(file);

  // Validate via backend
  const r = await fetch("/api/validate-image", { method: "POST", body: formData });
  const d = await r.json();

  if (!d.valid) {
    showError(imgError, d.message);
    clearImage();
    return;
  }

  state.imageFile = file;

  // Render meta chips
  imgMeta.innerHTML = "";
  if (d.meta) {
    const items = [
      `${d.meta.width}×${d.meta.height}`,
      d.meta.format,
      `Ratio ${d.meta.aspect_ratio}`,
    ];
    items.forEach(txt => {
      const chip = document.createElement("span");
      chip.className = "meta-chip";
      chip.textContent = txt;
      imgMeta.appendChild(chip);
    });
  }

  btnRegister.disabled = false;
  setWorkflowStep(2);
}

function clearImage() {
  state.imageFile = null;
  imgPreviewWrap.classList.add("hidden");
  dropZone.classList.remove("hidden");
  imgPreview.src = "";
  imgMeta.innerHTML = "";
  imgError.classList.add("hidden");
  btnRegister.disabled = true;
  faceInput.value = "";
  setWorkflowStep(1);
}

// ── Register asset ───────────────────────────────────────────────
btnRegister.addEventListener("click", registerAsset);

async function registerAsset() {
  if (!state.imageFile) return;

  btnRegister.disabled = true;
  btnRegister.textContent = "Registering…";
  assetTimeline.classList.remove("hidden");
  assetResult.classList.remove("hidden");
  setWorkflowStep(2);

  // ── Step 1: Create asset group ──────────────────────────────
  const groupName = $("group-name").value.trim() || "My Portrait Group";
  const groupReq  = { name: groupName, description: "Trusted face assets for Seedance 2.0 video generation" };

  tlSet("tl-group", "active", "Creating asset group…");
  setInspector("req-group", {
    method: "POST",
    url: "https://ark.ap-southeast.bytepluses.com/api/v3/assets/groups",
    body: groupReq,
  });

  let groupResp;
  try {
    const r = await fetch("/api/create-asset-group", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(groupReq),
    });
    groupResp = await r.json();
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

  // ── Step 2: Upload asset ────────────────────────────────────
  const assetName = $("asset-name").value.trim() || "Portrait Asset";
  tlSet("tl-upload", "active", "Uploading image…");

  const formData = new FormData();
  formData.append("group_id", state.groupId);
  formData.append("name", assetName);
  formData.append("image", state.imageFile);

  setInspector("req-asset", {
    method: "POST",
    url: "https://ark.ap-southeast.bytepluses.com/api/v3/assets",
    body: { group_id: state.groupId, name: assetName, content_type: "image", url: "<base64 data URI>" },
  });

  let assetResp;
  try {
    const r = await fetch("/api/create-asset", { method: "POST", body: formData });
    assetResp = await r.json();
    setInspector("res-asset", assetResp);

    if (assetResp.error) throw new Error(JSON.stringify(assetResp.error));

    state.assetId = assetResp.id;
    state.assetStatus = assetResp.status;
    $("out-asset-id").textContent = state.assetId;
    updateAssetStatusBadge(assetResp.status);
    tlSet("tl-upload", "done", `Asset ID: ${state.assetId}`);
  } catch (err) {
    tlSet("tl-upload", "error", `Failed: ${err.message}`);
    resetRegisterButton();
    return;
  }

  // ── Step 3: Poll asset status ───────────────────────────────
  tlSet("tl-verify", "active", "Waiting for verification…");
  pollAssetStatus();
}

function updateAssetStatusBadge(status) {
  const badge = $("out-asset-status");
  badge.textContent = status;
  badge.className = `badge ${status}`;

  if (status === "active") {
    assetNotice.classList.add("ready");
    assetNoticeIcon.textContent = "✓";
    assetNoticeText.textContent = `Portrait asset ready (ID: ${state.assetId})`;
    setWorkflowStep(3);
  } else if (status === "failed") {
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
      state.assetStatus = d.status;
      updateAssetStatusBadge(d.status);

      if (d.status === "active") {
        tlSet("tl-verify", "done", "Asset verified and active");
        resetRegisterButton();
        return;
      }
      if (d.status === "failed") {
        tlSet("tl-verify", "error", "Verification failed");
        resetRegisterButton();
        return;
      }

      tlSet("tl-verify", "active", `Attempt ${attempts} — status: ${d.status}`);
      if (attempts < 24) {
        state.assetPollTimer = setTimeout(poll, 5000);
      } else {
        tlSet("tl-verify", "active", "Still processing — generating video when ready");
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
  btnRegister.textContent = "Register Portrait Asset";
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
  const body = { prompt, model_id: modelId };
  if (state.assetId && state.assetStatus === "active") {
    body.asset_id = state.assetId;
  }

  setInspector("req-video", {
    method: "POST",
    url: "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks",
    body,
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
