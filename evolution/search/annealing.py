"""Chaotic simulated annealing with bounded cooling/reheating cycles."""

import math
import random

from ._numeric import json_state, positive, reflect, tuple_state, vector

# Exact smallest positive binary64 subnormal; available before math.ulp (3.9).
_MIN_POSITIVE_FLOAT = float.fromhex("0x0.0000000000001p-1022")


class ChaoticAnnealing:
    """Deterministic logistic proposals plus a Metropolis acceptance rule.

    A proposal consumes one schedule step, including hard-rejected proposals.
    accept() uses the most recently proposed temperature; callers must accept
    before proposing again. temperature reports the next proposal schedule step.
    Temperature is in objective-loss units. Checkpoints include the PRNG and
    logistic state, so JSON round trips reproduce subsequent proposals exactly.
    """

    def __init__(self, seed, dimensions, *, initial_temperature=0.1,
                 cooling=0.95, cycle_length=64, step_size=0.2):
        if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions < 1:
            raise ValueError("dimensions must be a positive integer")
        if isinstance(cycle_length, bool) or not isinstance(cycle_length, int) or cycle_length < 2:
            raise ValueError("cycle_length must be an integer >= 2")
        self.dimensions = dimensions
        self.initial_temperature = positive(initial_temperature, "initial_temperature")
        self.cooling = float(cooling)
        if not math.isfinite(self.cooling) or not 0 < self.cooling < 1:
            raise ValueError("cooling must be between zero and one")
        self.cycle_length = cycle_length
        self.step_size = positive(step_size, "step_size")
        if self.step_size > 1:
            raise ValueError("step_size must be <= 1")
        self._rng = random.Random(seed)
        self._chaos = self._rng.uniform(0.05, 0.95)
        self._recent = []
        self.iteration = 0
        self.chaos_resets = 0
        self._last_temperature = self.initial_temperature

    @property
    def temperature(self):
        return max(_MIN_POSITIVE_FLOAT, self.initial_temperature * max(1e-12, self.cooling ** (
            self.iteration % self.cycle_length)))

    def _next_chaos(self):
        value = 4.0 * self._chaos * (1.0 - self._chaos)
        # Floating-point logistic maps can collapse or enter short cycles.
        if value <= 1e-10 or value >= 1 - 1e-10 or any(
                abs(value - old) <= 1e-12 for old in self._recent):
            value = self._rng.uniform(0.05, 0.95)
            self._recent = []
            self.chaos_resets += 1
        self._chaos = value
        self._recent = (self._recent + [value])[-16:]
        return value

    def propose(self, theta):
        theta = vector(theta, self.dimensions)
        self._last_temperature = self.temperature
        scale = self.step_size * math.sqrt(self._last_temperature / self.initial_temperature)
        proposal = [reflect(value + scale * (2 * self._next_chaos() - 1))
                    for value in theta]
        self.iteration += 1
        return proposal

    def accept(self, current_loss, candidate_loss, hard_ok=True):
        if not hard_ok:
            return False
        current_loss, candidate_loss = float(current_loss), float(candidate_loss)
        if not math.isfinite(candidate_loss) or math.isnan(current_loss) or current_loss == -math.inf:
            return False
        if candidate_loss <= current_loss:
            return True
        probability = math.exp(max(-745.0, -(candidate_loss - current_loss) / self._last_temperature))
        return self._rng.random() < probability

    def state(self):
        return {
            "algorithm": "chaotic-annealing-v1", "dimensions": self.dimensions,
            "initial_temperature": self.initial_temperature, "cooling": self.cooling,
            "cycle_length": self.cycle_length, "step_size": self.step_size,
            "iteration": self.iteration, "chaos": self._chaos,
            "recent": list(self._recent), "chaos_resets": self.chaos_resets,
            "last_temperature": self._last_temperature,
            "rng_state": json_state(self._rng.getstate()),
        }

    @classmethod
    def from_state(cls, state):
        try:
            if not isinstance(state, dict):
                raise ValueError("annealing checkpoint must be an object")
            if state.get("algorithm") != "chaotic-annealing-v1":
                raise ValueError("unsupported annealing checkpoint")
            result = cls(0, state["dimensions"], initial_temperature=state["initial_temperature"],
                         cooling=state["cooling"], cycle_length=state["cycle_length"],
                         step_size=state["step_size"])
            for key in ("iteration", "chaos_resets"):
                if isinstance(state[key], bool) or not isinstance(state[key], int) or state[key] < 0:
                    raise ValueError("invalid annealing checkpoint counter")
                setattr(result, key, state[key])
            result._chaos = float(state["chaos"])
            result._recent = [float(item) for item in state["recent"]]
            if (not math.isfinite(result._chaos) or not 0 <= result._chaos <= 1 or
                    len(result._recent) > 16 or any(not math.isfinite(item) or not 0 <= item <= 1
                                                  for item in result._recent)):
                raise ValueError("invalid chaotic checkpoint")
            result._last_temperature = positive(state["last_temperature"], "last_temperature")
            if result._last_temperature > result.initial_temperature:
                raise ValueError("checkpoint temperature exceeds its initial temperature")
            expected_temperature = (result.initial_temperature if result.iteration == 0 else
                max(_MIN_POSITIVE_FLOAT, result.initial_temperature * max(1e-12,
                    result.cooling ** ((result.iteration - 1) % result.cycle_length))))
            if result._last_temperature != expected_temperature:
                raise ValueError("checkpoint temperature differs from its schedule")
            result._rng.setstate(tuple_state(state["rng_state"]))
            return result
        except (KeyError, TypeError, AttributeError, OverflowError) as error:
            raise ValueError("invalid annealing checkpoint") from error
