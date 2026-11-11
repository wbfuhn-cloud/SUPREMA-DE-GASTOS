"""Respuestas JSON estándar incluso con métricas numéricas ausentes."""
import math
from collections.abc import Mapping
from flask.json.provider import DefaultJSONProvider


def finite_json(value):
    if isinstance(value, Mapping):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, 'item'):
        return finite_json(value.item())
    return value


class FiniteJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs['allow_nan'] = False
        return super().dumps(finite_json(obj), **kwargs)
