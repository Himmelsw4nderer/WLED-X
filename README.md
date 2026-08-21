# Lumen

A self-hosted lighting controller for [WLED](https://kno.wled.ge/) devices:
discover devices on your LAN, lay LED strips out in a 3D scene, build
audio-reactive effects from small composable nodes, and run shows live from a
web console.

See [`docs/architecture.md`](docs/architecture.md) for how the pieces fit
together.

## Requirements

- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/)
- Node 20+ and npm
- Linux with PipeWire or PulseAudio (for desktop-audio loopback capture) —
  the backend records from your default sink's `.monitor` source
- One or more WLED devices on the same LAN/subnet, with **Sync > Receive > DDP**
  enabled (Settings → Sync → "Receive DDP data")

## Running it

Backend (FastAPI on `:8000`):

```sh
cd backend
uv sync
uv run lumen
```

Frontend (Vite dev server on `:5173`, proxies API/WS calls to the backend):

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Project layout

- `backend/` — Python API, device discovery, audio analysis, effect engine, DDP output
- `frontend/` — React 3D builder, node-graph effect editor, live console
- `docs/` — architecture notes

## Status

Actively under construction.
