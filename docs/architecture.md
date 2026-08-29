# WLED-X architecture

WLED-X is a WLED lighting controller: discover WLED devices, lay LED fixtures
out in a 3D scene, build audio-reactive effects from small function nodes,
and drive shows from a live console.

## Components

```
backend/   Python (FastAPI + SQLModel), package `wled_x`
  src/wled_x/
    config.py      Settings (env-driven): db path, host/port, DDP port, audio device
    db.py          SQLModel engine + session dependency
    models/         DB tables: Device, Fixture, Effect, Scene
    api/
      schemas.py    Pydantic request/response DTOs (never expose DB models directly)
      routes_*.py   REST CRUD per resource
      ws.py         WebSocket connection hub used for live pixel preview + console control
      nodes_registry.py  GET endpoint describing available effect-graph node types
    discovery/      WLED mDNS (_wled._tcp.local.) + subnet scan, WLED JSON API client
    output/         DDP (Distributed Display Protocol) UDP sender, device pixel-buffer manager
    audio/          Desktop audio loopback capture (PipeWire monitor source) + FFT/beat analysis
    effects/         Node graph model + vectorized numpy executor + built-in node library
    console/        Live console state (master brightness, active scene, param overrides, "hype" decay)
    main.py         FastAPI app factory + render-loop task

frontend/  React + TypeScript + Vite
  src/
    api/            REST client + typed WebSocket client
    types/          TS mirrors of backend schemas
    store/          zustand stores (devices, fixtures, effects, console)
    pages/
      DevicesPage       discovered WLED devices -> add to project
      BuilderPage        3D scene builder/viewer (react-three-fiber) for fixture placement
      EffectEditorPage   node-graph effect editor (reactflow) matching backend node registry
      ConsolePage        live performance console
```

## Data model

- **Device**: a physical WLED unit (ip, mac, reported led_count, discovery source).
- **Fixture**: a named LED run mapped onto a Device's pixel buffer at `start_channel`,
  positioned in 3D as a polyline of control points (2 points = a straight strip; more
  points allow bent/curved runs later). LEDs are distributed along the polyline by arc length.
- **Effect**: a node graph (`nodes` + `edges`, reactflow-shaped) plus a list of
  `exposed_params` that become adjustable sliders in the editor and console.
- **Scene**: one or more `(fixtures, effect, param overrides, brightness)` assignments;
  one active scene renders at a time in v1.

## Render pipeline

1. Audio thread captures desktop audio (PipeWire monitor source) and computes
   FFT bands, RMS level and a simple onset/beat pulse at ~60Hz.
2. The render loop evaluates the active scene's node graph(s) once per frame,
   vectorized over each fixture's LED positions (numpy arrays, not per-pixel
   Python loops).
3. Console overrides (master brightness, per-param overrides, decaying "hype"
   value for pre-drop buildups) are merged in before the final color write.
4. Per-device pixel buffers are assembled from their fixtures' output and sent
   over DDP UDP to each WLED device. The same frame is also broadcast over the
   `/ws/live` WebSocket for the browser's 3D preview and console meters.

## Node graph socket types

- `scalar` — one number, broadcasts to all LEDs (time, audio band, hype, constants)
- `field` — one float per LED (position components, index, noise, math results)
- `color` — one RGB triple per LED (0..1), final `LedColor` node output

Kept to three socket kinds deliberately: it covers every effect in v1 without
a type system agents have to fight.
