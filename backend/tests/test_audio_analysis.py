import numpy as np

from wled_x.audio.analysis import NUM_BANDS, AudioAnalyzer, _OnsetTrack


def _sine_block(
    freq: float, sample_rate: int = 48000, n: int = 1024, amplitude: float = 0.5
) -> np.ndarray:
    t = np.arange(n) / sample_rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_rms_level_in_sane_range():
    analyzer = AudioAnalyzer(sample_rate=48000)
    frame = analyzer.analyze(_sine_block(1000.0, amplitude=0.5))
    assert 0.0 < frame.level < 1.0
    assert abs(frame.level - 0.5 / np.sqrt(2)) < 0.05


def test_bands_shape():
    analyzer = AudioAnalyzer(sample_rate=48000)
    frame = analyzer.analyze(_sine_block(1000.0))
    assert frame.bands.shape == (NUM_BANDS,)


def test_energy_concentrated_in_low_band():
    analyzer = AudioAnalyzer(sample_rate=48000)
    frame = analyzer.analyze(_sine_block(100.0))
    assert frame.low > frame.high
    assert np.argmax(frame.bands) < NUM_BANDS // 2


def test_energy_concentrated_in_high_band():
    analyzer = AudioAnalyzer(sample_rate=48000)
    frame = analyzer.analyze(_sine_block(15000.0))
    assert frame.high > frame.low


def test_silence_produces_zero_level_and_no_beat():
    analyzer = AudioAnalyzer(sample_rate=48000)
    frame = analyzer.analyze(np.zeros(1024, dtype=np.float32))
    assert frame.level == 0.0
    assert frame.beat == 0.0


def test_beat_pulses_on_sudden_onset():
    analyzer = AudioAnalyzer(sample_rate=48000)
    silence = np.zeros(1024, dtype=np.float32)
    for _ in range(5):
        analyzer.analyze(silence)
    frame = analyzer.analyze(_sine_block(1000.0, amplitude=0.9))
    assert frame.beat > 0.0


def test_bass_onset_pulses_on_low_frequency_thump():
    analyzer = AudioAnalyzer(sample_rate=48000)
    silence = np.zeros(1024, dtype=np.float32)
    for _ in range(5):
        analyzer.analyze(silence)
    frame = analyzer.analyze(_sine_block(80.0, amplitude=0.9))
    assert frame.bass_onset > 0.0


def test_onset_track_refractory_period_blocks_immediate_retrigger():
    # A single physical hit can spike flux across two consecutive ~21ms
    # blocks; the refractory gate should only let the first one count as
    # an onset, since it's actually the same hit.
    track = _OnsetTrack(
        history_len=43, threshold_factor=1.0, decay_per_block=0.12, refractory_seconds=0.1
    )
    for _ in range(4):
        track.update(0.0, now=0.0)  # seed enough history for a real threshold

    assert track.update(10.0, now=0.5) is True
    assert track.update(10.0, now=0.51) is False  # still within the 0.1s refractory window

    assert track.update(10.0, now=0.65) is True  # refractory has elapsed


def test_bpm_converges_for_a_steady_bass_pulse():
    analyzer = AudioAnalyzer(sample_rate=48000)
    silence = np.zeros(1024, dtype=np.float32)
    thump = _sine_block(80.0, amplitude=0.9)

    frame = None
    for _ in range(6):
        frame = analyzer.analyze(thump)
        for _ in range(22):  # ~0.49s of silence between thumps -> ~122 bpm
            frame = analyzer.analyze(silence)

    assert frame is not None
    assert 90.0 < frame.bpm < 150.0
    assert 0.0 <= frame.beat_phase < 1.0
