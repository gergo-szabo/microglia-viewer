const Graphs = (() => {
  let _jobId = null;
  let _activeTab = "resolution";

  function setJob(jobId) {
    _jobId = jobId;
    document.getElementById("results-section").style.display = "block";
    _showOverlayControls();
    _loadThumbs();
  }

  function _loadThumbs() {
    ["resolution", "correlations", "coherences"].forEach(name => {
      const img = document.getElementById(`thumb-${name}`);
      img.src = `/api/jobs/${_jobId}/graphs/${name}?_=${Date.now()}`;
      img.onload = () => img.classList.add("loaded");
    });
  }

  function showResult(result) {
    const kv = {
      "Optimal Z range": `${result.optimal_z_start} – ${result.optimal_z_end}`,
      "Segmenter": result.segmenter_used,
    };
    const container = document.getElementById("result-kv-list");
    container.innerHTML = "";
    for (const [k, v] of Object.entries(kv)) {
      const row = document.createElement("div");
      row.className = "result-kv";
      row.innerHTML = `<span class="result-key">${k}</span><span class="result-val">${v}</span>`;
      container.appendChild(row);
    }
  }

  function _showOverlayControls() {
    const el = document.getElementById("overlay-controls");
    el.style.display = "block";
    Viewer.setOverlay(true);
    ["branches", "soma", "nucleus"].forEach(name => {
      const cb = document.getElementById(`mask-${name}`);
      cb.addEventListener("change", _onMaskChange);
    });
  }

  function _onMaskChange() {
    const selected = ["branches", "soma", "nucleus"]
      .filter(n => document.getElementById(`mask-${n}`).checked)
      .join(",");
    Viewer.setMasks(selected || "none");
  }

  function _openModal(name) {
    if (!_jobId) return;
    _activeTab = name;
    document.querySelectorAll(".graph-tab").forEach(t => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    const img = document.getElementById("graph-modal-img");
    img.src = `/api/jobs/${_jobId}/graphs/${name}?_=${Date.now()}`;
    document.getElementById("graph-modal").classList.add("open");
  }

  function _closeModal() {
    document.getElementById("graph-modal").classList.remove("open");
    document.querySelectorAll(".graph-tab").forEach(t => t.classList.remove("active"));
  }

  function bindTabs() {
    document.querySelectorAll(".graph-tab").forEach(t => {
      t.addEventListener("click", () => _openModal(t.dataset.tab));
    });
    document.getElementById("graph-modal-backdrop").addEventListener("click", _closeModal);
    document.getElementById("graph-modal-close").addEventListener("click", _closeModal);
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") _closeModal();
    });
  }

  return { setJob, showResult, bindTabs };
})();
