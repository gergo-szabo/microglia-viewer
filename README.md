# Microglia Viewer

A browser-based tool for viewing and analysing microglia process movement in nd2 (Nikon) time-lapse microscopy files. Built for the [HUN-REN Institute of Experimental Medicine](https://koki.hun-ren.hu/en/) Laboratory of Neuroimmunology.

![screenshot placeholder](docs/screenshot.png)

## What it does

- **Open large nd2 files** in the browser with no memory bloat — images are loaded lazily and served as DZI tiles (like Google Maps for microscopy)
- **Navigate** through channels, z-slices, and timepoints with sliders
- **Run segmentation** — the AutoMD classical CV pipeline is included as the baseline (Otsu thresholding + morphological operations + distance transform), identifying branches, soma, and nucleus compartments
- **View segmentation overlays** on top of the raw image in real time
- **Quality-control graphs** — effective resolution, vertical correlation, and horizontal coherence per z-slice to identify the optimal imaging plane
- **YOLO plug-in point** — swap in a trained YOLO segmentation model with a single environment variable (no code changes)

## Background and source material

This tool is a Python/web rewrite of the analysis pipeline originally described in:

- **MMQT** (Microglia Motility Quantification Tool) — the original MATLAB implementation  
  Source: [isdneuroimaging/mmqt](https://github.com/isdneuroimaging/mmqt)

- **AutoMD** — a Python port of MMQT by Pollini Kristóf (thesis work, supervised by Kiss Dániel)  
  Source: [ChrisPollini/AutoMD](https://github.com/ChrisPollini/AutoMD)

The segmentation pipeline in this tool (`backend/pipeline/`) is a faithful port of AutoMD's algorithm:
1. 16-bit → 8-bit normalisation
2. Contrast inversion and enhancement (AutoMD darken + stretch operations)
3. Median blur for noise reduction
4. Z-slice quality selection via effective resolution and spatial correlation metrics
5. Otsu thresholding → morphological opening → distance transform for cell compartment detection

## Requirements

- Python 3.10+
- A Nikon `.nd2` microscopy file to analyse

## Installation

```bash
git clone https://github.com/gergo-szabo/microglia-viewer.git
cd microglia-viewer
pip install -r requirements.txt
```

That's it. No database, no Docker, no build step.

### Optional: YOLO segmentation backend

If you have a trained YOLO segmentation model (`.pt` weights), install `ultralytics`:

```bash
pip install ultralytics
```

Then set the weights path before starting the server (see [YOLO integration](#yolo-integration) below).

## Starting the server

```bash
python3 run.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

The server runs on port 8000 by default. Use environment variables to change settings:

```bash
MICROGLIA_DATA_DIR=/mnt/big-disk/nd2-files \
MICROGLIA_RESULTS_DIR=/mnt/big-disk/results \
MICROGLIA_WORKER_THREADS=8 \
python3 run.py
```

## Usage

### 1 — Load a file

Drag and drop an `.nd2` file onto the upload area in the left sidebar, or click to browse.  
The file is opened lazily — only the tiles you actually view are read from disk.

### 2 — Navigate the image

| Control | What it does |
|---------|-------------|
| Channel buttons | Switch between fluorescence channels (e.g. DAPI, ALX647) |
| Z slice slider | Move through z-planes |
| Timepoint slider | Move through timepoints (hidden for single-frame files) |
| Scroll wheel | Zoom in/out |
| Click and drag | Pan |

### 3 — Run analysis

1. Select a **segmenter** from the dropdown (`automd` is always available)
2. Click **Run Analysis**
3. A progress bar shows the pipeline steps: loading → preprocessing → stack analysis → segmentation → graphs
4. When complete, the **Results** panel shows the optimal z-range and quality metrics
5. Enable the **Show segmentation overlay** toggle to see branches (green), soma (red), and nucleus (cyan) overlaid on the image

### 4 — Inspect quality graphs

Three graphs are generated for the ALX647 channel:
- **Resolution** — 99th–1st percentile intensity per z-slice (threshold: 45)
- **Correlation** — Pearson correlation between consecutive z-slices (threshold: 0.78)
- **Coherence** — mean spatial coherence in 4 directions per slice

The optimal z-range is the longest contiguous run of slices passing all three thresholds.

## YOLO integration

The segmentation backend is pluggable. To use a trained YOLO model:

```bash
MICROGLIA_YOLO_WEIGHTS_PATH=/path/to/best.pt python3 run.py
```

Your model must be trained with three classes in this order:
- Class 0 → branches / processes (shown in green)
- Class 1 → soma / cell body (shown in red)
- Class 2 → nucleus (shown in cyan)

The `GET /api/segmenters` endpoint will show `"available": true` for YOLO when weights are loaded. Users can then select it from the segmenter dropdown in the UI.

To register a completely custom backend, add a class that inherits from `backend.pipeline.segmentation.base.SegmentationBackend` and call `register_segmenter("mymodel", MySegmenter)` at startup in `backend/main.py`.

## Configuration reference

All settings can be overridden with `MICROGLIA_` prefixed environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MICROGLIA_DATA_DIR` | `./data` | Directory for uploaded nd2 files |
| `MICROGLIA_RESULTS_DIR` | `./results` | Directory for saved segmentation results |
| `MICROGLIA_TILE_SIZE` | `256` | DZI tile size in pixels |
| `MICROGLIA_JPEG_QUALITY` | `85` | JPEG compression quality for base tiles |
| `MICROGLIA_TILE_CACHE_MAXSIZE` | `1024` | Max encoded tiles held in memory |
| `MICROGLIA_FRAME_CACHE_MAXSIZE` | `20` | Max raw frames held in memory |
| `MICROGLIA_WORKER_THREADS` | `4` | Thread pool size for analysis jobs |
| `MICROGLIA_MAX_UPLOAD_MB` | `4096` | Max upload file size |
| `MICROGLIA_YOLO_WEIGHTS_PATH` | _(none)_ | Path to YOLO `.pt` weights file |

## API

The tool exposes a REST API at `/api`. Interactive docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/files/upload` | Upload an nd2 file |
| `GET` | `/api/tiles/{id}/info.json` | Image dimensions for the tile viewer |
| `GET` | `/api/tiles/{id}/{level}/{col}_{row}.jpg` | Serve a DZI tile |
| `POST` | `/api/jobs` | Start an analysis job |
| `GET` | `/api/jobs/{id}/progress` | SSE stream of job progress |
| `GET` | `/api/jobs/{id}/results` | Get analysis results (JSON) |
| `GET` | `/api/segmenters` | List available segmentation backends |

## Project structure

```
backend/
  main.py                 FastAPI application
  pipeline/
    preprocessor.py       16→8bit, darken, contrast stretch, blur (AutoMD port)
    stack_analyser.py     z-slice quality metrics and optimal range detection
    runner.py             Pipeline orchestrator with progress callbacks
    segmentation/
      automd.py           Classical CV baseline (always available)
      yolo.py             YOLO stub (activated via env var)
  services/
    nd2_loader.py         nd2 file opening with dask lazy loading
    tile_cache.py         Two-level LRU cache (frames + encoded tiles)
    worker.py             Async/sync bridge to thread pool executor
  routers/
    files.py              Upload, list, delete nd2 files
    tiles.py              DZI tile serving (JPEG + PNG overlay)
    jobs.py               Analysis jobs and SSE progress
frontend/
  index.html              Single-page application
  static/js/
    viewer.js             OpenSeadragon tile viewer
    controls.js           Channel/Z/T navigation
    progress.js           SSE EventSource progress bar
    graphs.js             Analysis graph display
```

## Acknowledgements

- Csaba Cserép, Kiss Dániel, Pollini Kristóf — Laboratory of Neuroimmunology, [HUN-REN KOKI](https://koki.hun-ren.hu/en/)
- [OpenSeadragon](https://openseadragon.github.io/) for the tile-based image viewer
- [nd2](https://github.com/tlambert03/nd2) by Talley Lambert for nd2 file reading
- [MotilA](https://www.biorxiv.org/content/10.1101/2025.08.04.668426v1) for background on microglial motility quantification approaches
