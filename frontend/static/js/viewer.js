const Viewer = (() => {
  let _osd = null;
  let _overlayLayer = null;
  let _currentFile = null;
  let _channel = 0, _t = 0, _z = 0;
  let _overlayVisible = false;
  let _masks = "branches,soma,nucleus";
  let _tileInfo = null;

  function init(containerId) {
    _osd = OpenSeadragon({
      id: containerId,
      prefixUrl: "https://cdn.jsdelivr.net/npm/openseadragon@4.1/build/openseadragon/images/",
      showNavigator: true,
      navigatorPosition: "BOTTOM_RIGHT",
      navigatorSizeRatio: 0.18,
      animationTime: 0.25,
      blendTime: 0.1,
      minZoomImageRatio: 0.5,
      maxZoomPixelRatio: 8,
      visibilityRatio: 0.3,
      defaultZoomLevel: 0,
      gestureSettingsMouse: { scrollToZoom: true },
      showFullPageControl: false,
      debugMode: false,
    });

    _osd.addHandler("canvas-press", (e) => {
      const vp = _osd.viewport;
      const pt = vp.pointFromPixel(e.position);
      const imgPt = vp.viewportToImageCoordinates(pt);
      if (_tileInfo) {
        document.getElementById("sb-coord").textContent =
          `x=${Math.round(imgPt.x)}, y=${Math.round(imgPt.y)}`;
      }
    });
  }

  function _makeTileSource(fileId, channel, t, z, info, layer) {
    const baseUrl = layer === "overlay"
      ? `/api/tiles/${fileId}/overlay`
      : `/api/tiles/${fileId}`;
    const ext = layer === "overlay" ? "png" : "jpg";
    const extra = layer === "overlay"
      ? `?channel=${channel}&t=${t}&z=${z}&masks=${_masks}`
      : `?channel=${channel}&t=${t}&z=${z}`;
    return {
      width: info.width,
      height: info.height,
      tileSize: info.tile_size,
      minLevel: 0,
      maxLevel: info.max_level,
      getTileUrl(level, x, y) {
        return `${baseUrl}/${level}/${x}_${y}.${ext}${extra}`;
      },
    };
  }

  async function loadFrame(fileId, channel, t, z) {
    if (!_osd) return;

    let savedCenter = null, savedZoom = null;
    if (_currentFile === fileId && _osd.world.getItemCount() > 0) {
      savedCenter = _osd.viewport.getCenter();
      savedZoom = _osd.viewport.getZoom();
    }

    _currentFile = fileId;
    _channel = channel;
    _t = t;
    _z = z;

    try {
      _tileInfo = await API.getTileInfo(fileId, channel, t, z);
    } catch (e) {
      Toast.show("Could not load tile info: " + e.message, true);
      return;
    }

    const src = _makeTileSource(fileId, channel, t, z, _tileInfo, "base");
    if (savedCenter !== null) {
      _osd.addOnceHandler("open", () => {
        _osd.viewport.zoomTo(savedZoom, null, true);
        _osd.viewport.panTo(savedCenter, true);
      });
    }
    _osd.open(src);
    _overlayLayer = null;

    document.getElementById("sb-dim").textContent =
      `${_tileInfo.width}×${_tileInfo.height}`;

    if (_overlayVisible) {
      _loadOverlay();
    }
  }

  function _loadOverlay() {
    if (!_osd || !_currentFile || !_tileInfo) return;
    const src = _makeTileSource(_currentFile, _channel, _t, _z, _tileInfo, "overlay");
    if (_overlayLayer !== null) {
      _osd.world.removeItem(_osd.world.getItemAt(1));
      _overlayLayer = null;
    }
    _osd.addTiledImage({
      tileSource: src,
      opacity: 0.75,
      index: 1,
      success(e) { _overlayLayer = e.item; },
    });
  }

  function setOverlay(visible) {
    _overlayVisible = visible;
    if (visible && _currentFile) {
      _loadOverlay();
    } else if (_overlayLayer) {
      _osd.world.removeItem(_overlayLayer);
      _overlayLayer = null;
    }
  }

  function refreshOverlay() {
    if (_overlayVisible && _currentFile) {
      if (_overlayLayer) {
        _osd.world.removeItem(_overlayLayer);
        _overlayLayer = null;
      }
      _loadOverlay();
    }
  }

  function setMasks(masks) {
    _masks = masks;
    refreshOverlay();
  }

  return { init, loadFrame, setOverlay, refreshOverlay, setMasks };
})();
