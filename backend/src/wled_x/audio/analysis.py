"""Per-block audio analysis: RMS level, a small log-spaced band spectrum, and
a two-track onset detector (general transients plus a bass/kick-focused
track used for tempo tracking). numpy only -- this runs once per audio block
on the render loop's timescale, no room for a heavier DSP stack.

The onset detector is a log-compressed spectral-flux detector with an
adaptive (mean + k*stddev) threshold, rather than a flat multiple of the
running mean -- that's what makes it hold up across quiet and loud passages
instead of either flooding with false triggers or going deaf. Each track
also has its own refractory period so a single hit that spans two blocks
(common at a 1024-sample / 48kHz block size, ~21ms) can't double-trigger.

The bass track's onset timestamps additionally feed a light tempo tracker:
inter-onset intervals within a plausible BPM range are smoothed into a
`bpm` estimate, and `beat_phase` turns that into a continuous 0..1 ramp
that free-runs between hits and snaps back to 0 on every confirmed onset --
useful for effects that want to move smoothly with the music instead of
only reacting to individual hits.
"""

import time
from collections import deque
from dataclasses import dataclass, replace

import numpy as np

from wled_x.config import settings

NUM_BANDS = 16
_MIN_FREQ_HZ = 20.0
_BASS_MAX_FREQ_HZ = 200.0  # upper edge of the "bass/kick" band used for tempo tracking

_FLUX_HISTORY = 43  # ~1s of history at a 1024-sample block / 48kHz
_ONSET_THRESHOLD_FACTOR = 2.0  # local mean + this many local stddevs
_ONSET_DECAY_PER_BLOCK = 0.12
_REFRACTORY_SECONDS = 0.1  # fastest a single hit can retrigger the same track

_MIN_BPM = 70.0
_MAX_BPM = 190.0
_IBI_HISTORY = 8  # inter-onset intervals kept for tempo smoothing
_BPM_SMOOTHING = 0.25  # low-pass factor applied to each new tempo estimate


@dataclass
class AudioFrame:
    level: float
    bands: np.ndarray
    low: float
    mid: float
    high: float
    beat: float
    bass_onset: float = 0.0
    bpm: float = 0.0
    beat_phase: float = 0.0


class _OnsetTrack:
    """Adaptive-threshold spectral-flux onset detector with a refractory gate."""

    def __init__(
        self,
        history_len: int,
        threshold_factor: float,
        decay_per_block: float,
        refractory_seconds: float,
    ) -> None:
        self._history: deque[float] = deque(maxlen=history_len)
        self._threshold_factor = threshold_factor
        self._decay_per_block = decay_per_block
        self._refractory_seconds = refractory_seconds
        self.value = 0.0
        self.last_onset_time: float | None = None

    def update(self, flux: float, now: float) -> bool:
        """Feed one block's flux value; returns True if a new onset fired."""
        threshold = self._threshold()
        self._history.append(flux)

        past_refractory = (
            self.last_onset_time is None or now - self.last_onset_time >= self._refractory_seconds
        )
        if flux > threshold and flux > 1e-6 and past_refractory:
            self.value = 1.0
            self.last_onset_time = now
            return True

        self.value = max(self.value - self._decay_per_block, 0.0)
        return False

    def _threshold(self) -> float:
        if len(self._history) < 4:
            # Not enough context to judge a spike yet; require nothing so the
            # very first loud sound after startup/silence still registers.
            return 1e-6
        arr = np.asarray(self._history, dtype=np.float64)
        return float(np.mean(arr) + self._threshold_factor * np.std(arr))


class AudioAnalyzer:
    def __init__(
        self,
        sample_rate: int | None = None,
        num_bands: int = NUM_BANDS,
        flux_history: int = _FLUX_HISTORY,
        onset_threshold_factor: float = _ONSET_THRESHOLD_FACTOR,
        onset_decay_per_block: float = _ONSET_DECAY_PER_BLOCK,
        refractory_seconds: float = _REFRACTORY_SECONDS,
    ) -> None:
        self.sample_rate = sample_rate or settings.audio_sample_rate
        self.num_bands = num_bands
        self._onset_decay_per_block = onset_decay_per_block
        self._prev_spectrum: np.ndarray | None = None

        self._beat_track = _OnsetTrack(
            flux_history, onset_threshold_factor, onset_decay_per_block, refractory_seconds
        )
        self._bass_track = _OnsetTrack(
            flux_history, onset_threshold_factor, onset_decay_per_block, refractory_seconds
        )

        self._clock = 0.0
        self._ibi_history: deque[float] = deque(maxlen=_IBI_HISTORY)
        self._bpm = 0.0

        # Wall-clock (`time.monotonic()`) stamps for the last time each track
        # fired, plus the same linear onset decay expressed per real second
        # instead of per audio block. `project()` uses these to hand the render
        # loop a `beat`/`bass_onset`/`beat_phase` computed against the render
        # loop's own clock -- so those values stay smooth at 60 fps and don't
        # drift when audio blocks arrive late or get dropped, instead of being
        # frozen between the ~47 Hz `analyze()` calls.
        block_seconds = settings.audio_block_size / self.sample_rate
        self._onset_decay_per_second = onset_decay_per_block / max(block_seconds, 1e-6)
        self._beat_fired_wall: float | None = None
        self._bass_fired_wall: float | None = None

    def analyze(self, block: np.ndarray) -> AudioFrame:
        block = np.asarray(block, dtype=np.float32).reshape(-1)
        if block.size == 0:
            empty_bands = np.zeros(self.num_bands, dtype=np.float32)
            return AudioFrame(
                0.0,
                empty_bands,
                0.0,
                0.0,
                0.0,
                beat=self._beat_track.value,
                bass_onset=self._bass_track.value,
                bpm=self._bpm,
                beat_phase=self._beat_phase(),
            )

        level = float(np.sqrt(np.mean(np.square(block))))

        windowed = block * np.hanning(block.size).astype(np.float32)
        spectrum = np.abs(np.fft.rfft(windowed)) / block.size
        freqs = np.fft.rfftfreq(block.size, d=1.0 / self.sample_rate)

        bands = self._bin_bands(spectrum, freqs)
        third = max(self.num_bands // 3, 1)
        low = float(np.mean(bands[:third]))
        mid = float(np.mean(bands[third : 2 * third]))
        high = float(np.mean(bands[2 * third :]))

        self._clock += block.size / self.sample_rate
        self._update_onsets(spectrum, freqs, time.monotonic())

        return AudioFrame(
            level=level,
            bands=bands,
            low=low,
            mid=mid,
            high=high,
            beat=self._beat_track.value,
            bass_onset=self._bass_track.value,
            bpm=self._bpm,
            beat_phase=self._beat_phase(),
        )

    def _bin_bands(self, spectrum: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        nyquist = self.sample_rate / 2.0
        edges = np.geomspace(_MIN_FREQ_HZ, nyquist, self.num_bands + 1)
        bands = np.zeros(self.num_bands, dtype=np.float32)
        for i in range(self.num_bands):
            mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
            if np.any(mask):
                bands[i] = np.mean(spectrum[mask])
        return bands

    def _update_onsets(self, spectrum: np.ndarray, freqs: np.ndarray, now_wall: float) -> None:
        if self._prev_spectrum is None or self._prev_spectrum.shape != spectrum.shape:
            self._prev_spectrum = spectrum
            self._beat_track.value = max(self._beat_track.value - self._onset_decay_per_block, 0.0)
            self._bass_track.value = max(self._bass_track.value - self._onset_decay_per_block, 0.0)
            return

        # Log-compress before diffing: raw-magnitude flux is dominated by
        # whichever bins happen to carry the most energy (usually bass, just
        # from how music spectra are shaped), which drowns out real
        # transients elsewhere. Compression makes onsets comparable across
        # quiet and loud bins and across quiet and loud passages alike.
        compressed = np.log1p(spectrum * 50.0)
        prev_compressed = np.log1p(self._prev_spectrum * 50.0)
        diff = compressed - prev_compressed
        rectified = np.where(diff > 0, diff, 0.0)
        self._prev_spectrum = spectrum

        full_flux = float(np.sum(rectified))
        bass_mask = (freqs >= _MIN_FREQ_HZ) & (freqs < _BASS_MAX_FREQ_HZ)
        bass_flux = float(np.sum(rectified[bass_mask])) if np.any(bass_mask) else full_flux

        if self._beat_track.update(full_flux, self._clock):
            self._beat_fired_wall = now_wall
        prev_bass_onset_time = self._bass_track.last_onset_time
        if self._bass_track.update(bass_flux, self._clock):
            self._bass_fired_wall = now_wall
            self._register_tempo_onset(prev_bass_onset_time)

    def _register_tempo_onset(self, prev_onset_time: float | None) -> None:
        if prev_onset_time is None:
            return
        interval = self._clock - prev_onset_time
        if interval <= 0:
            return
        bpm = 60.0 / interval
        if not (_MIN_BPM <= bpm <= _MAX_BPM):
            return
        self._ibi_history.append(interval)
        target_bpm = 60.0 / float(np.median(self._ibi_history))
        if self._bpm <= 0:
            self._bpm = target_bpm
        else:
            self._bpm += _BPM_SMOOTHING * (target_bpm - self._bpm)

    def _beat_phase(self) -> float:
        if self._bpm <= 0 or self._bass_track.last_onset_time is None:
            return 0.0
        period = 60.0 / self._bpm
        return float(((self._clock - self._bass_track.last_onset_time) % period) / period)

    def project(self, frame: AudioFrame, now: float) -> AudioFrame:
        """Return `frame` with the time-varying beat fields recomputed for
        wall-clock instant `now` (a `time.monotonic()` value). `analyze()`
        only runs once per audio block (~47 Hz) and its `beat`/`bass_onset`/
        `beat_phase` are frozen in between; the render loop calls this every
        tick so those values move smoothly at render_fps and stay locked to
        real time even if blocks arrive late or are dropped. `level`, `bands`
        and the low/mid/high split are left as the last analyzed values."""
        return replace(
            frame,
            beat=self._decayed_since(self._beat_fired_wall, now),
            bass_onset=self._decayed_since(self._bass_fired_wall, now),
            beat_phase=self._beat_phase_at(now),
        )

    def _decayed_since(self, fired_wall: float | None, now: float) -> float:
        if fired_wall is None:
            return 0.0
        return max(0.0, 1.0 - self._onset_decay_per_second * (now - fired_wall))

    def _beat_phase_at(self, now: float) -> float:
        if self._bpm <= 0 or self._bass_fired_wall is None:
            return 0.0
        period = 60.0 / self._bpm
        return float(((now - self._bass_fired_wall) % period) / period)
