import numpy as np

from lumen.effects.geometry import led_positions, scene_bounds


def test_led_positions_distributes_evenly_along_a_straight_strip():
    result = led_positions([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], 5)
    assert np.allclose(result[:, 0], [0.0, 2.5, 5.0, 7.5, 10.0])


def test_reverse_flips_led_order_along_the_same_path():
    forward = led_positions([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], 5)
    backward = led_positions([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], 5, reverse=True)
    assert np.allclose(backward, forward[::-1])
    # LED 0 now sits at the far end instead of the near end.
    assert np.allclose(backward[0], [10.0, 0.0, 0.0])
    assert np.allclose(backward[-1], [0.0, 0.0, 0.0])


def test_reverse_is_a_noop_for_a_single_repeated_point():
    points = [(1.0, 1.0, 1.0), (1.0, 1.0, 1.0)]
    forward = led_positions(points, 4)
    backward = led_positions(points, 4, reverse=True)
    assert np.allclose(forward, backward)


def test_scene_bounds_spans_every_fixtures_points():
    bounds = scene_bounds(
        [
            [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
            [(1.0, -1.0, 3.0), (5.0, 4.0, 3.0)],
        ]
    )
    assert bounds is not None
    lo, hi = bounds
    assert np.allclose(lo, [0.0, -1.0, 0.0])
    assert np.allclose(hi, [5.0, 4.0, 3.0])


def test_scene_bounds_is_none_when_there_are_no_fixtures():
    assert scene_bounds([]) is None
