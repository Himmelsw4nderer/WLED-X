"""Desktop audio loopback capture.

On PipeWire/PulseAudio (this project's target platform, see README) shells
out to `parec` reading the default sink's `.monitor` source directly. This is
more reliable than going through `sounddevice`/PortAudio: PortAudio's ALSA
hostapi (the one available on a stock PipeWire install) has no concept of a
Pulse ".monitor" source at all, so `sounddevice.query_devices()` never sees
one there even though `pactl` does. Falls back to a `sounddevice` InputStream
(picking any device with "monitor" in its name, else the system default
input) when `parec` isn't available -- non-Linux or Pulse-less setups.
"""

import asyncio
import contextlib
import logging
import shutil

import numpy as np
import sounddevice as sd

from lumen.config import settings

logger = logging.getLogger(__name__)


def _select_fallback_device() -> tuple[int | None, int]:
    devices = sd.query_devices()

    if settings.audio_device:
        needle = settings.audio_device.lower()
        for index, info in enumerate(devices):
            if info["max_input_channels"] > 0 and needle in info["name"].lower():
                return index, info["max_input_channels"]
        logger.warning(
            "configured audio_device %r not found among input devices, falling back",
            settings.audio_device,
        )

    for index, info in enumerate(devices):
        if info["max_input_channels"] > 0 and "monitor" in info["name"].lower():
            return index, info["max_input_channels"]

    logger.warning("no '.monitor' loopback input device found, falling back to the default input")
    return None, 1


async def _default_monitor_source() -> str | None:
    if settings.audio_device:
        return settings.audio_device
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl",
            "get-default-sink",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except OSError:
        return None
    sink = stdout.decode().strip()
    return f"{sink}.monitor" if sink else None


class AudioCapture:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=8)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._loop.create_task(self._start_async())

    async def _start_async(self) -> None:
        try:
            if shutil.which("parec") and await self._start_pulse():
                return
        except Exception:
            logger.exception("pulse audio capture failed, falling back to PortAudio")
        self._start_sounddevice()

    async def _start_pulse(self) -> bool:
        source = await _default_monitor_source()
        if not source:
            return False
        self._proc = await asyncio.create_subprocess_exec(
            "parec",
            "--device",
            source,
            "--rate",
            str(settings.audio_sample_rate),
            "--channels",
            "1",
            "--format",
            "float32le",
            "--raw",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._read_task = asyncio.create_task(self._read_pulse())
        logger.info("capturing desktop audio via parec from %s", source)
        return True

    async def _read_pulse(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        stdout = self._proc.stdout
        block_bytes = settings.audio_block_size * 4  # float32le, mono
        try:
            while True:
                data = await stdout.readexactly(block_bytes)
                self._enqueue(np.frombuffer(data, dtype=np.float32).copy())
        except (asyncio.IncompleteReadError, asyncio.CancelledError):
            return
        except Exception:
            logger.exception("parec read loop failed")

    def _start_sounddevice(self) -> None:
        device, channels = _select_fallback_device()
        channels = max(min(channels, 2), 1)
        self._stream = sd.InputStream(
            samplerate=settings.audio_sample_rate,
            blocksize=settings.audio_block_size,
            device=device,
            channels=channels,
            dtype="float32",
            callback=self._sd_callback,
        )
        self._stream.start()

    def _sd_callback(self, indata: np.ndarray, frames: int, time_info: object, status: int) -> None:
        if status:
            logger.debug("audio callback status: %s", status)
        mono = (
            indata.mean(axis=1, dtype=np.float32) if indata.ndim > 1 else indata.astype(np.float32)
        )
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._enqueue, mono.copy())

    def _enqueue(self, block: np.ndarray) -> None:
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        self._queue.put_nowait(block)

    def stop(self) -> None:
        if self._read_task is not None:
            self._read_task.cancel()
            self._read_task = None
        if self._proc is not None:
            with contextlib.suppress(ProcessLookupError):
                self._proc.terminate()
            self._proc = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    async def get(self) -> np.ndarray:
        return await self._queue.get()


capture = AudioCapture()
