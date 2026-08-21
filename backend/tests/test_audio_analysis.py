import numpy as np

from lumen.audio.analysis import NUM_BANDS, AudioAnalyzer


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
