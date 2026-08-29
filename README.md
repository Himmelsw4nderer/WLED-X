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

## Using it

1. **Devices** — scan the LAN (mDNS + a subnet fallback) for WLED units, or
   add one manually by IP. Make sure DDP receive is enabled on the device
   (see Requirements above).
2. **Builder** — add fixtures: pick a device, set an LED count and a path (2+
   points in meters), and see the strip laid out in the 3D viewer.
3. **Effects** — build a node graph (position/time/audio/noise/math/color
   nodes feeding a final LED Color output) and optionally expose a few
   params as console sliders.
4. **Console** — create a scene assigning effects to fixtures, activate it,
   then ride the exposed faders, master brightness, and the "hit" button for
   a pre-drop energy boost, all live against real desktop audio.

## Project layout

- `backend/` — Python API, device discovery, audio analysis, effect engine, DDP output
- `frontend/` — React 3D builder, node-graph effect editor, live console
- `docs/` — architecture notes

## Status

Core loop is working end-to-end: discovery, 3D fixture layout, node-graph
effects, audio-reactive rendering over DDP, and a live console. Backend has
pytest coverage; frontend test coverage is in progress.
