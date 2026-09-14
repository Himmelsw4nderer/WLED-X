"""Resolves the console's active ColorScheme into the numpy array
EvalContext.color_scheme carries -- one shared helper so the render loop and
the effect editor's debug preview can't drift onto different fallback
behavior for "no scheme picked yet"."""

import numpy as np
from sqlmodel import Session

from wled_x.effects.graph import DEFAULT_COLOR_SCHEME
from wled_x.models.color_scheme import ColorScheme


def resolve_scheme_colors(session: Session, scheme_id: int | None) -> np.ndarray:
    if scheme_id is not None:
        scheme = session.get(ColorScheme, scheme_id)
        if scheme is not None and scheme.colors:
            return np.asarray(scheme.colors, dtype=np.float32).reshape(-1, 3)
    return DEFAULT_COLOR_SCHEME
