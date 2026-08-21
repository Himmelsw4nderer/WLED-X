from lumen.api.schemas import ConsoleState
from lumen.effects.engine import RenderLoop
from lumen.models.effect import Effect


def test_two_instances_of_the_same_node_type_are_overridden_independently():
    # Regression test: the console override key used to be "{effect_id}:{param_key}",
    # so two nodes exposing a param with the same name (e.g. two Constant nodes both
    # exposing "value") collided onto the same override -- moving one console slider
    # silently moved both. Key now includes node_id.
    effect = Effect(
        id=1,
        name="two constants",
        graph={"nodes": [], "edges": []},
        exposed_params=[
            {"node_id": "c1", "param_key": "value", "label": "A", "min": 0, "max": 1, "default": 0},
            {"node_id": "c2", "param_key": "value", "label": "B", "min": 0, "max": 1, "default": 0},
        ],
    )
    console_state = ConsoleState(param_overrides={"1:c1:value": 0.2, "1:c2:value": 0.8})

    loop = RenderLoop()
    overrides = loop._resolve_param_overrides(effect, {"params": {}}, console_state)

    assert overrides[("c1", "value")] == 0.2
    assert overrides[("c2", "value")] == 0.8
