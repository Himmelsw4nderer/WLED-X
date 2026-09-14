"""One-off: rewrite the pre-merge per-axis position nodes in every stored
Effect graph to the single unified `position` node.

    position_x/y/z          -> position {space: "scene",  axis: x/y/z}
    local_x/y/z             -> position {space: "local",  axis: x/y/z}
    global_x/y/z            -> position {space: "meters", axis: x/y/z}
    distance_from_origin    -> position {space: "meters", axis: "xyz"}

Idempotent: graphs with nothing to change are left untouched. The old node
types still evaluate (they're kept as hidden back-compat shims), so this is a
cosmetic cleanup -- it just moves stored graphs onto the new node so they show
the space/axis dropdowns in the editor.

Run from the backend dir with the venv active:  python -m wled_x.migrate_positions
"""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from wled_x.db import engine, init_db
from wled_x.models.effect import Effect

LEGACY_POSITION_NODES: dict[str, tuple[str, str]] = {
    "position_x": ("scene", "x"),
    "position_y": ("scene", "y"),
    "position_z": ("scene", "z"),
    "local_x": ("local", "x"),
    "local_y": ("local", "y"),
    "local_z": ("local", "z"),
    "global_x": ("meters", "x"),
    "global_y": ("meters", "y"),
    "global_z": ("meters", "z"),
    "distance_from_origin": ("meters", "xyz"),
}


def migrate_graph(graph: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Returns (possibly-rewritten graph, number of nodes changed)."""
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return graph, 0

    changed = 0
    for node in nodes:
        mapping = LEGACY_POSITION_NODES.get(node.get("type", ""))
        if mapping is None:
            continue
        space, axis = mapping
        node["type"] = "position"
        node["data"] = {**(node.get("data") or {}), "space": space, "axis": axis}
        changed += 1
    return graph, changed


def migrate_session(session: Session) -> dict[str, int]:
    """Migrates every Effect in the session. Returns {effect_name: nodes_changed}
    for the ones that actually changed."""
    touched: dict[str, int] = {}
    for effect in session.exec(select(Effect)).all():
        graph, changed = migrate_graph(copy.deepcopy(effect.graph or {}))
        if changed:
            effect.graph = graph
            # graph is a plain JSON column with no Mutable tracking -- nudge
            # SQLAlchemy so the reassignment is actually flushed.
            flag_modified(effect, "graph")
            session.add(effect)
            touched[effect.name] = changed
    session.commit()
    return touched


if __name__ == "__main__":
    init_db()
    with Session(engine) as session:
        touched = migrate_session(session)
    if touched:
        print(f"Migrated {len(touched)} effect(s):")
        for name, count in touched.items():
            print(f"  - {name}: {count} position node(s) -> `position`")
    else:
        print("No legacy position nodes found, nothing to migrate.")
