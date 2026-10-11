"""Small shared numerical and checkpoint primitives; no optional dependencies."""

import math


def vector(values, dimensions=None):
    result = [float(value) for value in values]
    if not result or (dimensions is not None and len(result) != dimensions):
        raise ValueError("parameter vector has the wrong dimensions")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in result):
        raise ValueError("parameters must be finite and normalized to [0, 1]")
    return result


def positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be positive and finite")
    return value


def loss(value):
    value = float(value)
    if math.isnan(value) or value == -math.inf:
        raise ValueError("loss must be finite or positive infinity")
    return value


def reflect(value):
    """Reflect an arbitrary finite value into the unit interval."""
    value %= 2.0
    return value if value <= 1 else 2.0 - value


def json_state(value):
    return [json_state(item) for item in value] if isinstance(value, tuple) else value


def tuple_state(value):
    return tuple(tuple_state(item) for item in value) if isinstance(value, list) else value
