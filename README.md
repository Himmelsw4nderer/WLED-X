# WLED-X

A self-hosted lighting controller for [WLED](https://kno.wled.ge/) devices:
discover devices on your LAN, lay LED strips out in a 3D scene, build
audio-reactive effects from small composable nodes, and run shows live from a
web console.

See [`docs/architecture.md`](docs/architecture.md) for how the pieces fit
together.

## Requirements

- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/)
- Node 20+ and npm
- Linux with PipeWire or PulseAudio, plus the `parec` CLI (from
  `pulseaudio-utils`, or bundled with PipeWire's Pulse compatibility layer —
  already present if `pactl` works) for desktop-audio loopback capture. The
  backend records from your default sink's `.monitor` source; if `parec`
  isn't available it falls back to `sounddevice`/PortAudio, picking any input
  device with "monitor" in its name.
- One or more WLED devices on the same LAN/subnet, with **Sync > Receive > DDP**
  enabled (Settings → Sync → "Receive DDP data")

## Running it

Backend (FastAPI on `:8000`):

```sh
cd backend
uv sync
uv run wled-x
```

Frontend (Vite dev server on `:5173`, proxies API/WS calls to the backend):

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Packaged (AppImage)

`packaging/appimage/build.sh` builds a self-contained `WLED-X-*.AppImage`: a
production frontend build served by the backend itself (one process, one
port), a portable CPython with the backend's dependencies pip-installed into
it, and `libportaudio`/`libasound` bundled so it runs without Python, Node,
or `libportaudio2` preinstalled. Needs internet access (fetches a portable
Python build + `appimagetool`, cached under `packaging/appimage/build/` after
the first run), npm, and ImageMagick (`magick`, for the app icon):

```sh
./packaging/appimage/build.sh
```

Output lands in `packaging/appimage/dist/`. Launching it opens your browser
at the running console; app data (the SQLite DB) goes to
`~/.local/share/wled-x/`.

## Using it

1. **Gear** — scan the LAN (mDNS + a subnet fallback) for WLED units, or
   add one manually by IP. Make sure DDP receive is enabled on the device
   (see Requirements above).
2. **Room** — add fixtures: pick a device, set an LED count and a path (2+
   points in meters), and see the strip laid out in the 3D viewer.
3. **Patch** — build a node graph (position/time/audio/noise/math/color
   nodes feeding a final LED Color output) and optionally expose a few
   params as console sliders.
4. **Colors** — build named palettes (a handful of swatches each), then pull
   from one in an effect graph with the Scheme Color / Scheme Random Color
   nodes. Activating a scheme overrides those nodes across every effect at
   once.
5. **Show** — create a scene assigning effects to fixtures, activate it,
   then ride the exposed faders, master brightness, and the "hit" button for
   a pre-drop energy boost, all live against real desktop audio.

## Project layout

- `backend/` — Python API, device discovery, audio analysis, effect engine, DDP output
- `frontend/` — React 3D builder, node-graph effect editor, live console
- `docs/` — architecture notes

## Status

Core loop is working end-to-end: discovery, 3D fixture layout, node-graph
effects, audio-reactive rendering over DDP, and a live console. Ships with a
library of 20 built-in example effects (seeded on first run) to start from or
copy node patterns out of. Backend has pytest coverage; frontend test
coverage is in progress.
