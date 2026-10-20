"""JADE current-to-pbest/1 differential evolution with a bounded archive."""

import math
import random

from ._numeric import json_state, loss, reflect, tuple_state, vector


class AdaptiveDE:
    """Maintain one population of the same structural genotype.

    The controller must pool different structures separately. Rejected hard
    constraints may be supplied as +inf losses and can never enter the archive.
    """

    def __init__(self, seed, population, losses, *, p=0.2, learning_rate=0.1):
        self.population = [vector(item) for item in population]
        if len(self.population) < 4:
            raise ValueError("differential evolution needs at least four individuals")
        self.dimensions = len(self.population[0])
        if any(len(item) != self.dimensions for item in self.population):
            raise ValueError("population structures must have equal dimensions")
        self.losses = [loss(value) for value in losses]
        if len(self.losses) != len(self.population):
            raise ValueError("one loss is required per individual")
        self.p, self.learning_rate = float(p), float(learning_rate)
        if not 0 < self.p <= 1 or not 0 < self.learning_rate <= 1:
            raise ValueError("p and learning_rate must be in (0, 1]")
        self.mu_f = self.mu_cr = 0.5
        self.archive = []
        self.generation = 0
        self._rng = random.Random(seed)
        self._pending = None

    def _factor(self):
        for _ in range(1000):
            factor = self.mu_f + 0.1 * math.tan(math.pi * (self._rng.random() - 0.5))
            if factor > 0:
                return min(1.0, factor)
        return self.mu_f

    def propose(self):
        if self._pending is not None:
            raise RuntimeError("select the pending generation before proposing again")
        size = len(self.population)
        ranked = sorted(range(size), key=self.losses.__getitem__)
        best = ranked[:max(2, math.ceil(self.p * size))]
        union = self.population + self.archive
        candidates, factors, crossovers = [], [], []
        for index, current in enumerate(self.population):
            factor = self._factor()
            crossover = max(0.0, min(1.0, self._rng.gauss(self.mu_cr, 0.1)))
            pbest = self.population[self._rng.choice(best)]
            first = self._rng.choice([item for item in range(size) if item != index])
            second = self._rng.choice([item for item in range(len(union))
                                       if item != index and item != first])
            mutant = [reflect(value + factor * (elite - value) + factor * (one - two))
                      for value, elite, one, two in zip(
                          current, pbest, self.population[first], union[second])]
            mandatory = self._rng.randrange(self.dimensions)
            candidates.append([mutant[dim] if dim == mandatory or self._rng.random() < crossover
                               else current[dim] for dim in range(self.dimensions)])
            factors.append(factor)
            crossovers.append(crossover)
        self._pending = {"candidates": candidates, "factors": factors, "crossovers": crossovers}
        return [list(item) for item in candidates]

    def select(self, candidates, losses):
        if self._pending is None:
            raise RuntimeError("propose a generation before selection")
        candidates = [vector(item, self.dimensions) for item in candidates]
        values = [loss(value) for value in losses]
        if candidates != self._pending["candidates"] or len(values) != len(self.population):
            raise ValueError("selection must match the pending generation")
        successful_f, successful_cr = [], []
        for index, (candidate, value) in enumerate(zip(candidates, values)):
            if math.isfinite(value) and value < self.losses[index]:
                # Infeasible parents carry no successful measured evidence.
                if math.isfinite(self.losses[index]):
                    self.archive.append(self.population[index])
                self.population[index] = candidate
                self.losses[index] = value
                successful_f.append(self._pending["factors"][index])
                successful_cr.append(self._pending["crossovers"][index])
        if successful_f:
            rate = self.learning_rate
            self.mu_f = (1 - rate) * self.mu_f + rate * (
                sum(item * item for item in successful_f) / sum(successful_f))
            self.mu_cr = (1 - rate) * self.mu_cr + rate * (
                sum(successful_cr) / len(successful_cr))
        while len(self.archive) > len(self.population):
            del self.archive[self._rng.randrange(len(self.archive))]
        self._pending = None
        self.generation += 1

    def state(self):
        return {
            "algorithm": "adaptive-de-jade-v1", "population": [list(p) for p in self.population],
            "losses": [value if math.isfinite(value) else None for value in self.losses],
            "p": self.p, "learning_rate": self.learning_rate,
            "mu_f": self.mu_f, "mu_cr": self.mu_cr,
            "archive": [list(item) for item in self.archive], "generation": self.generation,
            "pending": None if self._pending is None else {
                key: [list(item) if isinstance(item, list) else item for item in values]
                for key, values in self._pending.items()},
            "rng_state": json_state(self._rng.getstate()),
        }

    @classmethod
    def from_state(cls, state):
        if state.get("algorithm") != "adaptive-de-jade-v1":
            raise ValueError("unsupported differential-evolution checkpoint")
        result = cls(0, state["population"], [math.inf if value is None else value
                                             for value in state["losses"]],
                     p=state["p"], learning_rate=state["learning_rate"])
        result.mu_f, result.mu_cr = float(state["mu_f"]), float(state["mu_cr"])
        if not 0 < result.mu_f <= 1 or not 0 <= result.mu_cr <= 1:
            raise ValueError("invalid adaptation checkpoint")
        result.archive = [vector(item, result.dimensions) for item in state["archive"]]
        if len(result.archive) > len(result.population):
            raise ValueError("checkpoint archive exceeds population size")
        result.generation = state["generation"]
        if isinstance(result.generation, bool) or not isinstance(result.generation, int) or result.generation < 0:
            raise ValueError("invalid generation checkpoint")
        pending = state["pending"]
        if pending is not None:
            candidates = [vector(item, result.dimensions) for item in pending["candidates"]]
            factors = [float(item) for item in pending["factors"]]
            crossovers = [float(item) for item in pending["crossovers"]]
            if (any(len(items) != len(result.population) for items in (candidates, factors, crossovers)) or
                    any(not 0 < item <= 1 for item in factors) or
                    any(not 0 <= item <= 1 for item in crossovers)):
                raise ValueError("invalid pending-generation checkpoint")
            result._pending = dict(candidates=candidates, factors=factors, crossovers=crossovers)
        result._rng.setstate(tuple_state(state["rng_state"]))
        return result
