/* Main application bootstrap */
document.addEventListener("DOMContentLoaded", async () => {
  Viewer.init("osd-container");
  Graphs.bindTabs();

  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const uploadStatus = document.getElementById("upload-status");
  const fileList = document.getElementById("file-list");
  const btnRun = document.getElementById("btn-run");

  let _activeFileId = null;
  let _segmenterName = "automd";

  // ── Upload ───────────────────────────────────────────
  dropzone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => handleUpload(fileInput.files[0]));

  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("drag-over"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const f = e.dataTransfer.files[0];
    if (f) handleUpload(f);
  });

  async function handleUpload(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".nd2")) {
      Toast.show("Only .nd2 files are supported", true);
      return;
    }
    uploadStatus.textContent = `Uploading ${file.name}…`;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const info = await API.uploadFile(fd);
      uploadStatus.textContent = "";
      Toast.show(`Loaded: ${info.filename}`);
      await refreshFileList();
      activateFile(info);
    } catch (e) {
      uploadStatus.textContent = "";
      Toast.show("Upload failed: " + e.message, true);
    }
  }

  // ── File list ────────────────────────────────────────
  async function refreshFileList() {
    const files = await API.listFiles();
    fileList.innerHTML = "";
    if (files.length === 0) {
      fileList.innerHTML = '<div style="color:var(--text2);font-size:12px;padding:4px 2px;">No files loaded</div>';
      return;
    }
    files.forEach(f => {
      const el = document.createElement("div");
      el.className = "file-item" + (f.id === _activeFileId ? " active" : "");
      el.dataset.id = f.id;

      const sz = Object.entries(f.sizes).map(([k,v]) => `${k}:${v}`).join(" ");
      el.innerHTML = `
        <div class="file-name" title="${f.filename}">${f.filename}</div>
        <div class="file-meta">${sz} · ${f.channels.join(", ")}</div>
        <button class="file-delete" title="Delete">×</button>
      `;
      el.querySelector(".file-delete").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete ${f.filename}?`)) return;
        try {
          await API.deleteFile(f.id);
          if (_activeFileId === f.id) _activeFileId = null;
          await refreshFileList();
        } catch (err) { Toast.show("Delete failed: " + err.message, true); }
      });
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("file-delete")) return;
        activateFile(f);
      });
      fileList.appendChild(el);
    });
  }

  function activateFile(fileInfo) {
    _activeFileId = fileInfo.id;
    document.querySelectorAll(".file-item").forEach(el => {
      el.classList.toggle("active", el.dataset.id === fileInfo.id);
    });
    Controls.setFile(fileInfo);
    btnRun.disabled = false;
    document.getElementById("results-section").style.display = "none";
    document.getElementById("progress-wrap").style.display = "none";
    document.getElementById("graph-img").style.display = "none";
  }

  // ── Segmenter selection ──────────────────────────────
  const segSelect = document.getElementById("segmenter-select");
  try {
    const segs = await API.getSegmenters();
    segSelect.innerHTML = "";
    segs.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s.name;
      opt.textContent = s.name + (s.available ? "" : " (unavailable)");
      opt.disabled = !s.available;
      segSelect.appendChild(opt);
    });
  } catch {}
  segSelect.addEventListener("change", () => { _segmenterName = segSelect.value; });

  // ── Run analysis ─────────────────────────────────────
  btnRun.addEventListener("click", async () => {
    if (!_activeFileId) return;
    btnRun.disabled = true;

    const { channel, t, z } = Controls.get();
    try {
      const job = await API.createJob({
        file_id: _activeFileId,
        channel_dapi: 0,
        channel_alx: channel,
        t,
        segmenter: _segmenterName,
        segmenter_params: {},
      });

      Progress.watch(
        job.id,
        (result) => {
          btnRun.disabled = false;
          Toast.show("Analysis complete");
          Graphs.setJob(job.id);
          Graphs.showResult(result);
          Viewer.refreshOverlay();
        },
        (err) => {
          btnRun.disabled = false;
          Toast.show("Analysis failed: " + err, true);
        }
      );
    } catch (e) {
      btnRun.disabled = false;
      Toast.show("Could not start job: " + e.message, true);
    }
  });

  // ── Initial load ─────────────────────────────────────
  await refreshFileList();
  btnRun.disabled = true;
  document.getElementById("sb-version").textContent = "Microglia Viewer v0.1";
});
