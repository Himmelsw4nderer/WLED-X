from typing import Any

import numpy as np

from wled_x.api.schemas import NodeParam, NodeSocket, NodeTypeDescriptor
from wled_x.effects.graph import EvalContext, NodeDefinition, Value


def _hsv_to_rgb(h: Value, s: Value, v: Value) -> np.ndarray:
    h_arr, s_arr, v_arr = (np.asarray(x, dtype=np.float32) for x in (h, s, v))
    h_arr, s_arr, v_arr = np.broadcast_arrays(h_arr, s_arr, v_arr)
    hh = np.mod(h_arr, 1.0) * 6.0
    i = np.floor(hh).astype(np.int64) % 6
    f = hh - np.floor(hh)
    p = v_arr * (1.0 - s_arr)
    q = v_arr * (1.0 - s_arr * f)
    t = v_arr * (1.0 - s_arr * (1.0 - f))
    conditions = [i == k for k in range(6)]
    r = np.select(conditions, [v_arr, q, p, p, t, v_arr])
    g = np.select(conditions, [t, v_arr, v_arr, q, p, p])
    b = np.select(conditions, [p, p, t, v_arr, v_arr, q])
    return np.stack([r, g, b], axis=-1).astype(np.float32)


def _compute_hsv(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    h = inputs.get("h", data.get("h", 0.0))
    s = inputs.get("s", data.get("s", 1.0))
    v = inputs.get("v", data.get("v", 1.0))
    return _hsv_to_rgb(h, s, v)


def _compute_rgb(data: dict[str, Any], inputs: dict[str, Value], context: EvalContext) -> Value:
    r = inputs.get("r", data.get("r", 1.0))
    g = inputs.get("g", data.get("g", 1.0))
    b = inputs.get("b", data.get("b", 1.0))
    r_arr, g_arr, b_arr = (np.asarray(x, dtype=np.float32) for x in (r, g, b))
    r_arr, g_arr, b_arr = np.broadcast_arrays(r_arr, g_arr, b_arr)
    return np.stack([r_arr, g_arr, b_arr], axis=-1).astype(np.float32)


def _compute_color_ramp(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    stops = data.get("stops") or [
        {"pos": 0.0, "color": [0.0, 0.0, 0.0]},
        {"pos": 1.0, "color": [1.0, 1.0, 1.0]},
    ]
    stops_sorted = sorted(stops, key=lambda stop: float(stop["pos"]))
    xp = np.array([float(stop["pos"]) for stop in stops_sorted], dtype=np.float32)
    fp = np.array([stop["color"] for stop in stops_sorted], dtype=np.float32)

    position = inputs.get("position", data.get("position", 0.0))
    pos_arr = np.asarray(position, dtype=np.float32)
    scalar_input = pos_arr.ndim == 0
    pos_flat = np.atleast_1d(pos_arr)

    channels = [np.interp(pos_flat, xp, fp[:, channel]) for channel in range(3)]
    result = np.stack(channels, axis=-1).astype(np.float32)
    return result[0] if scalar_input else result


def _lerp_color(a: Value, b: Value, t: Value) -> np.ndarray:
    a_arr = np.asarray(a, dtype=np.float32)
    b_arr = np.asarray(b, dtype=np.float32)
    a_arr, b_arr = np.broadcast_arrays(a_arr, b_arr)
    t_arr = np.asarray(t, dtype=np.float32)
    if t_arr.ndim == 1 and a_arr.ndim == 2:
        t_arr = t_arr[:, None]
    return a_arr + (b_arr - a_arr) * t_arr


def _compute_mix_color(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    a = inputs.get("a", (0.0, 0.0, 0.0))
    b = inputs.get("b", (1.0, 1.0, 1.0))
    t = inputs.get("t", data.get("t", 0.5))
    return _lerp_color(a, b, t)


def _compute_led_color(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    return inputs.get("color", np.zeros((context.n, 3), dtype=np.float32))


def _kelvin_to_rgb(kelvin: np.ndarray) -> np.ndarray:
    """Blackbody color temperature -> linear-ish 0..1 RGB (Tanner Helland's
    widely-used polynomial fit to the Planckian locus). ~6500K reads as
    near-white, ~2800K as the warm amber of a halogen/incandescent lamp,
    ~10000K+ as cool blue daylight -- lets an effect be authored in "what
    color temperature is this fixture" terms instead of guessing RGB values
    by eye."""
    temp = np.clip(kelvin, 1000.0, 40000.0).astype(np.float64) / 100.0

    # np.where evaluates both branches everywhere, so e.g. the "cool" power()
    # branch runs even at low temp where its base (temp - 60) is negative and
    # its fractional exponent has no real result -- harmless since that
    # branch is discarded, but it'd otherwise spam RuntimeWarnings.
    with np.errstate(invalid="ignore"):
        red = np.where(
            temp <= 66.0,
            255.0,
            329.698727446 * np.power(temp - 60.0, -0.1332047592),
        )
        green = np.where(
            temp <= 66.0,
            99.4708025861 * np.log(temp) - 161.1195681661,
            288.1221695283 * np.power(temp - 60.0, -0.0755148492),
        )
        blue = np.where(
            temp >= 66.0,
            255.0,
            np.where(temp <= 19.0, 0.0, 138.5177312231 * np.log(temp - 10.0) - 305.0447927307),
        )

    rgb = np.stack([red, green, blue], axis=-1)
    return (np.clip(rgb, 0.0, 255.0) / 255.0).astype(np.float32)


def _compute_color_temperature(
    data: dict[str, Any], inputs: dict[str, Value], context: EvalContext
) -> Value:
    kelvin = np.asarray(inputs.get("kelvin", data.get("kelvin", 2800.0)), dtype=np.float32)
    return _kelvin_to_rgb(kelvin)


COLOR_NODES: dict[str, NodeDefinition] = {
    "hsv": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="hsv",
            category="color",
            label="HSV",
            inputs=[
                NodeSocket(key="h", type="field", label="H"),
                NodeSocket(key="s", type="field", label="S"),
                NodeSocket(key="v", type="field", label="V"),
            ],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[
                NodeParam(key="h", type="float", default=0.0, min=0.0, max=1.0),
                NodeParam(key="s", type="float", default=1.0, min=0.0, max=1.0),
                NodeParam(key="v", type="float", default=1.0, min=0.0, max=1.0),
            ],
        ),
        compute=_compute_hsv,
    ),
    "rgb": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="rgb",
            category="color",
            label="RGB",
            inputs=[
                NodeSocket(key="r", type="field", label="R"),
                NodeSocket(key="g", type="field", label="G"),
                NodeSocket(key="b", type="field", label="B"),
            ],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[
                NodeParam(key="r", type="float", default=1.0, min=0.0, max=1.0),
                NodeParam(key="g", type="float", default=1.0, min=0.0, max=1.0),
                NodeParam(key="b", type="float", default=1.0, min=0.0, max=1.0),
            ],
        ),
        compute=_compute_rgb,
    ),
    "color_ramp": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="color_ramp",
            category="color",
            label="Color Ramp",
            inputs=[NodeSocket(key="position", type="field", label="Position")],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[
                NodeParam(
                    key="stops",
                    type="color",
                    default=[
                        {"pos": 0.0, "color": [0.0, 0.0, 0.0]},
                        {"pos": 1.0, "color": [1.0, 1.0, 1.0]},
                    ],
                )
            ],
        ),
        compute=_compute_color_ramp,
    ),
    "mix_color": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="mix_color",
            category="color",
            label="Mix Color",
            inputs=[
                NodeSocket(key="a", type="color", label="A"),
                NodeSocket(key="b", type="color", label="B"),
                NodeSocket(key="t", type="field", label="T"),
            ],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[NodeParam(key="t", type="float", default=0.5, min=0.0, max=1.0)],
        ),
        compute=_compute_mix_color,
    ),
    "color_temperature": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="color_temperature",
            category="color",
            label="Color Temperature",
            inputs=[NodeSocket(key="kelvin", type="field", label="Kelvin")],
            outputs=[NodeSocket(key="value", type="color", label="Color")],
            params=[
                NodeParam(key="kelvin", type="float", default=2800.0, min=1000.0, max=12000.0),
            ],
        ),
        compute=_compute_color_temperature,
    ),
    "led_color": NodeDefinition(
        descriptor=NodeTypeDescriptor(
            type="led_color",
            category="output",
            label="LED Color",
            inputs=[NodeSocket(key="color", type="color", label="Color")],
        ),
        compute=_compute_led_color,
    ),
}
