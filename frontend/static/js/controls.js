const Controls = (() => {
  let _file = null;
  let _channel = 0, _t = 0, _z = 0;

  function setFile(fileInfo) {
    _file = fileInfo;
    _channel = 0; _t = 0; _z = 0;

    // Channel buttons
    const cb = document.getElementById("channel-btns");
    cb.innerHTML = "";
    (fileInfo.channels || []).forEach((name, i) => {
      const btn = document.createElement("button");
      btn.className = "channel-btn" + (i === 0 ? " active" : "");
      btn.textContent = name || `CH${i}`;
      btn.dataset.ch = i;
      btn.addEventListener("click", () => {
        document.querySelectorAll(".channel-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        _channel = i;
        _reload();
      });
      cb.appendChild(btn);
    });

    // Z slider
    const zMax = Math.max((fileInfo.sizes.Z || 1) - 1, 0);
    _setupSlider("z-slider", "z-val", zMax, 0, v => { _z = v; _reload(); });

    // T slider
    const tMax = Math.max((fileInfo.sizes.T || 1) - 1, 0);
    const tRow = document.getElementById("t-row");
    tRow.style.display = tMax > 0 ? "flex" : "none";
    _setupSlider("t-slider", "t-val", tMax, 0, v => { _t = v; _reload(); });

    // Overlay
    const ov = document.getElementById("overlay-toggle");
    ov.checked = false;
    ov.addEventListener("change", () => Viewer.setOverlay(ov.checked));

    _reload();
  }

  function _setupSlider(sliderId, valId, max, initial, onChange) {
    const slider = document.getElementById(sliderId);
    const valEl = document.getElementById(valId);
    slider.max = max;
    slider.value = initial;
    valEl.textContent = initial;
    slider.oninput = () => {
      const v = parseInt(slider.value);
      valEl.textContent = v;
      onChange(v);
    };
  }

  function _reload() {
    if (!_file) return;
    Viewer.loadFrame(_file.id, _channel, _t, _z);
    document.getElementById("sb-channel").textContent =
      `CH${_channel}  T=${_t}  Z=${_z}`;
  }

  function get() { return { channel: _channel, t: _t, z: _z }; }

  return { setFile, get };
})();
