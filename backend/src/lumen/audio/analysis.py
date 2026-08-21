"""Per-block audio analysis: RMS level, a small log-spaced band spectrum, and
a spectral-flux onset ("beat") detector. numpy only -- this runs once per
audio block on the render loop's timescale, no room for a heavier DSP stack.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from lumen.config import settings

NUM_BANDS = 16
_MIN_FREQ_HZ = 20.0
_FLUX_HISTORY = 43  # ~1s of history at a 1024-sample block / 48kHz
_BEAT_THRESHOLD_FACTOR = 1.5
_BEAT_DECAY_PER_BLOCK = 0.12


@dataclass
class AudioFrame:
    level: float
    bands: np.ndarray
    low: float
    mid: float
    high: float
    beat: float


class AudioAnalyzer:
    def __init__(
        self,
        sample_rate: int | None = None,
        num_bands: int = NUM_BANDS,
        flux_history: int = _FLUX_HISTORY,
        beat_threshold_factor: float = _BEAT_THRESHOLD_FACTOR,
        beat_decay_per_block: float = _BEAT_DECAY_PER_BLOCK,
    ) -> None:
        self.sample_rate = sample_rate or settings.audio_sample_rate
        self.num_bands = num_bands
        self._beat_threshold_factor = beat_threshold_factor
        self._beat_decay_per_block = beat_decay_per_block
        self._prev_spectrum: np.ndarray | None = None
        self._flux_history: deque[float] = deque(maxlen=flux_history)
        self._beat = 0.0

    def analyze(self, block: np.ndarray) -> AudioFrame:
        block = np.asarray(block, dtype=np.float32).reshape(-1)
        if block.size == 0:
            empty_bands = np.zeros(self.num_bands, dtype=np.float32)
            return AudioFrame(0.0, empty_bands, 0.0, 0.0, 0.0, self._beat)

        level = float(np.sqrt(np.mean(np.square(block))))

        windowed = block * np.hanning(block.size).astype(np.float32)
        spectrum = np.abs(np.fft.rfft(windowed)) / block.size
        freqs = np.fft.rfftfreq(block.size, d=1.0 / self.sample_rate)

        bands = self._bin_bands(spectrum, freqs)
        third = max(self.num_bands // 3, 1)
        low = float(np.mean(bands[:third]))
        mid = float(np.mean(bands[third : 2 * third]))
        high = float(np.mean(bands[2 * third :]))

        self._beat = self._update_beat(spectrum)

        return AudioFrame(level=level, bands=bands, low=low, mid=mid, high=high, beat=self._beat)

    def _bin_bands(self, spectrum: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        nyquist = self.sample_rate / 2.0
        edges = np.geomspace(_MIN_FREQ_HZ, nyquist, self.num_bands + 1)
        bands = np.zeros(self.num_bands, dtype=np.float32)
        for i in range(self.num_bands):
            mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
            if np.any(mask):
                bands[i] = np.mean(spectrum[mask])
        return bands

    def _update_beat(self, spectrum: np.ndarray) -> float:
        if self._prev_spectrum is None or self._prev_spectrum.shape != spectrum.shape:
            self._prev_spectrum = spectrum
            return max(self._beat - self._beat_decay_per_block, 0.0)

        diff = spectrum - self._prev_spectrum
        flux = float(np.sum(diff[diff > 0]))
        self._prev_spectrum = spectrum

        baseline = float(np.mean(self._flux_history)) if self._flux_history else 0.0
        threshold = baseline * self._beat_threshold_factor + 1e-6
        self._flux_history.append(flux)

        if flux > threshold and flux > 1e-6:
            return 1.0
        return max(self._beat - self._beat_decay_per_block, 0.0)
