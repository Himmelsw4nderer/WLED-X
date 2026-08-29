from wled_x.effects.phrase_clock import PhraseClock


def _beats(clock: PhraseClock, count: int, bpm: float = 120.0) -> list:
    """Feed `count` completed beats as a rising ramp that wraps each beat,
    returning the PhraseTick for every call."""
    ticks = []
    for _ in range(count):
        ticks.append(clock.tick(0.9, bpm))  # ramp near the top
        ticks.append(clock.tick(0.1, bpm))  # ... drops past 1.0 -> a beat
    return ticks


def test_counts_beats_and_wraps_the_phrase():
    clock = PhraseClock(phrase_beats=4, beats_per_bar=2)

    _beats(clock, 3)
    assert clock.total_beats == 3
    assert clock.phrase_beat == 3
    assert clock.phrase_index == 0
    assert clock.bar == 1  # beats_per_bar=2 -> beat 3 is in bar 1

    wrap_tick = _beats(clock, 1)[-1]
    assert wrap_tick.beat_advanced is True
    assert wrap_tick.phrase_wrapped is True
    assert clock.phrase_beat == 0
    assert clock.phrase_index == 1
    assert clock.total_beats == 4  # total keeps climbing across phrases


def test_bar_advanced_flag():
    clock = PhraseClock(phrase_beats=16, beats_per_bar=4)
    ticks = [t for t in _beats(clock, 8) if t.beat_advanced]
    # bar boundaries at beat 4 and beat 8
    assert [i for i, t in enumerate(ticks, start=1) if t.bar_advanced] == [4, 8]


def test_tempo_change_flag_but_not_on_first_lock():
    clock = PhraseClock()

    assert clock.tick(0.5, 0.0).tempo_changed is False  # not locked yet
    assert clock.tick(0.5, 128.0).tempo_changed is False  # first lock -> seed, not a change
    assert clock.tick(0.5, 131.0).tempo_changed is False  # small drift within tolerance
    changed = clock.tick(0.5, 140.0)  # +12 from the 128 anchor
    assert changed.tempo_changed is True
    # Re-anchored at 140: steady 140 is no longer a change.
    assert clock.tick(0.5, 140.0).tempo_changed is False


def test_reset_zeroes_counters_and_reanchors_bpm():
    clock = PhraseClock(phrase_beats=8)
    _beats(clock, 5, bpm=120.0)
    assert clock.phrase_beat == 5

    clock.reset()
    assert clock.total_beats == 0
    assert clock.phrase_beat == 0
    assert clock.phrase_index == 0
    # anchor moved to current bpm, so 120 stays quiet right after a reset
    assert clock.tick(0.5, 120.0).tempo_changed is False


def test_set_phrase_beats_keeps_position_in_range():
    clock = PhraseClock(phrase_beats=64)
    _beats(clock, 40)
    assert clock.phrase_beat == 40
    clock.set_phrase_beats(32)
    assert clock.phrase_beats == 32
    assert clock.phrase_beat == 8  # 40 % 32
