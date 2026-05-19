const Graphs = (() => {
  let _jobId = null;
  let _activeTab = "resolution";

  function setJob(jobId) {
    _jobId = jobId;
    document.getElementById("results-section").style.display = "block";
    _showTab(_activeTab);
  }

  function showResult(result) {
    const kv = {
      "Optimal Z range": `${result.optimal_z_start} – ${result.optimal_z_end}`,
      "Slices analysed": result.resolution_metrics?.length ?? "—",
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

  function _showTab(name) {
    _activeTab = name;
    document.querySelectorAll(".graph-tab").forEach(t => {
      t.classList.toggle("active", t.dataset.tab === name);
    });
    if (!_jobId) return;
    const img = document.getElementById("graph-img");
    img.style.display = "block";
    img.src = `/api/jobs/${_jobId}/graphs/${name}?_=${Date.now()}`;
  }

  function bindTabs() {
    document.querySelectorAll(".graph-tab").forEach(t => {
      t.addEventListener("click", () => _showTab(t.dataset.tab));
    });
  }

  return { setJob, showResult, bindTabs };
})();
