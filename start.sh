#!/usr/bin/env bash
# Starts the WLED-X backend (FastAPI, :8000) and frontend (Vite, :5173) together.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pids=()
cleanup() {
    trap - INT TERM EXIT
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait
}
trap cleanup INT TERM EXIT

(cd "$root/backend" && uv run wled-x) &
pids+=("$!")

(cd "$root/frontend" && npm run dev) &
pids+=("$!")

wait -n
