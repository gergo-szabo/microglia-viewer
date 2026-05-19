const Progress = (() => {
  let _source = null;

  function watch(jobId, onDone, onError) {
    stop();

    const wrap = document.getElementById("progress-wrap");
    const label = document.getElementById("progress-label");
    const bar = document.getElementById("progress-bar-inner");

    wrap.style.display = "block";
    label.textContent = "Starting...";
    bar.style.width = "0%";

    _source = new EventSource(`/api/jobs/${jobId}/progress`);

    _source.addEventListener("progress", (e) => {
      const d = JSON.parse(e.data);
      label.textContent = d.message || d.step || "";
      bar.style.width = d.pct + "%";
    });

    _source.addEventListener("complete", (e) => {
      const d = JSON.parse(e.data);
      bar.style.width = "100%";
      label.textContent = "Complete";
      stop();
      wrap.style.display = "none";
      onDone && onDone(d.data);
    });

    _source.addEventListener("error", (e) => {
      let msg = "Analysis failed";
      try { msg = JSON.parse(e.data).message || msg; } catch {}
      label.textContent = msg;
      bar.style.width = "0%";
      stop();
      onError && onError(msg);
    });

    _source.onerror = () => {
      // SSE connection error — fallback poll
      stop();
      _poll(jobId, onDone, onError, label, bar);
    };
  }

  function _poll(jobId, onDone, onError, label, bar) {
    const iv = setInterval(async () => {
      try {
        const job = await API.getJob(jobId);
        label.textContent = job.message || job.step || job.status;
        bar.style.width = job.progress + "%";
        if (job.status === "complete") {
          clearInterval(iv);
          wrap.style.display = "none";
          onDone && onDone(await API.getResults(jobId));
        } else if (job.status === "failed") {
          clearInterval(iv);
          onError && onError(job.error || "Failed");
        }
      } catch {}
    }, 1000);
  }

  function stop() {
    if (_source) { _source.close(); _source = null; }
  }

  return { watch, stop };
})();
