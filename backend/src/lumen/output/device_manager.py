"""Interface contract between the render loop (lumen.effects.engine) and the
physical device output (lumen.output.ddp + lumen.discovery).

The render loop calls `push_frame` once per rendered frame with one uint8
(N, 3) RGB array per device id; this module is responsible for turning that
into DDP UDP packets addressed to each device's IP and tracking online state.
Implemented in full by the discovery/output work; this stub exists so the
effects engine has something concrete to import against while that work is
in progress.
"""

import numpy as np


async def push_frame(pixel_buffers: dict[int, np.ndarray]) -> None:
    """pixel_buffers: device_id -> (N, 3) uint8 RGB array, one row per LED."""
    raise NotImplementedError
