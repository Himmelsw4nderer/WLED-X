"""The console phrase-clock: one process-wide beat / phrase counter the whole
show runs against.

It reads the globally-selected audio source's `beat_phase` ramp and BPM (see
`AudioAnalyzer.project`), counts completed beats, groups them into phrases of a
configurable length (default 64 beats = 16 bars of 4/4), and flags when the
tempo has shifted far enough to count as a real change.

Deliberately *not* an effect-graph node: show-level automation (scene
playlists, and whatever else later) subscribes to it, while effect graphs only
ever see the raw `beat_phase` ramp. This is the logic that used to live in the
`beat_counter` node, promoted to a singleton.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lumen.api.schemas import PhraseClockState

# A beat_phase ramp that falls by more than this between two ticks has wrapped
# past 1.0 -- a beat just completed (or a detected onset re-synced the ramp
# backwards, which counts the same).
_WRAP_DROP = 0.5

DEFAULT_PHRASE_BEATS = 64
DEFAULT_BEATS_PER_BAR = 4
DEFAULT_BPM_TOLERANCE = 8.0


@dataclass
class PhraseTick:
    """What changed on the tick that produced this -- the playlist runner reads
    it to decide whether to advance."""

    beat_advanced: bool = False  # a new beat landed this tick
    bar_advanced: bool = False  # ... and it started a new bar
    phrase_wrapped: bool = False  # ... and it wrapped the phrase back to 0
    tempo_changed: bool = False  # BPM moved > tolerance from the phrase anchor


@dataclass
class PhraseClock:
    phrase_beats: int = DEFAULT_PHRASE_BEATS
    beats_per_bar: int = DEFAULT_BEATS_PER_BAR
    bpm_tolerance: float = DEFAULT_BPM_TOLERANCE

    bpm: float = 0.0
    total_beats: int = 0  # monotonic since the last reset()
    phrase_beat: int = 0  # 0 .. phrase_beats - 1
    phrase_index: int = 0  # completed phrases since reset()

    _prev_phase: float = field(default=0.0, repr=False)
    _anchor_bpm: float = field(default=0.0, repr=False)

    def reset(self) -> None:
        self.total_beats = 0
        self.phrase_beat = 0
        self.phrase_index = 0
        self._anchor_bpm = self.bpm

    def set_phrase_beats(self, n: int) -> None:
        self.phrase_beats = max(int(n), 1)
        self.phrase_beat %= self.phrase_beats

    @property
    def bar(self) -> int:
        return self.phrase_beat // max(self.beats_per_bar, 1)

    @property
    def phrase_phase(self) -> float:
        return self.phrase_beat / max(self.phrase_beats, 1)

    def tick(self, beat_phase: float, bpm: float) -> PhraseTick:
        self.bpm = float(bpm)
        result = PhraseTick()

        if (
            bpm > 0.0
            and self._anchor_bpm > 0.0
            and abs(bpm - self._anchor_bpm) > self.bpm_tolerance
        ):
            result.tempo_changed = True
            self._anchor_bpm = bpm
        elif self._anchor_bpm <= 0.0 and bpm > 0.0:
            # First real lock -- seed the anchor, don't call it a change.
            self._anchor_bpm = bpm

        if self._prev_phase - float(beat_phase) > _WRAP_DROP:
            self.total_beats += 1
            self.phrase_beat += 1
            result.beat_advanced = True
            if self.phrase_beat % max(self.beats_per_bar, 1) == 0:
                result.bar_advanced = True
            if self.phrase_beat >= self.phrase_beats:
                self.phrase_beat = 0
                self.phrase_index += 1
                result.phrase_wrapped = True
        self._prev_phase = float(beat_phase)
        return result

    def state(self) -> "PhraseClockState":
        # Imported here to keep this module free of any api/ dependency at
        # import time (schemas imports models, models import nothing here).
        from lumen.api.schemas import PhraseClockState

        return PhraseClockState(
            bpm=round(self.bpm, 2),
            total_beats=self.total_beats,
            phrase_beat=self.phrase_beat,
            phrase_index=self.phrase_index,
            phrase_beats=self.phrase_beats,
            bar=self.bar,
            phrase_phase=round(self.phrase_phase, 4),
        )
