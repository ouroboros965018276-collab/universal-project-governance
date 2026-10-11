"""Numerical search regressions using synthetic measured objectives only."""

import copy
import json
import math
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.version_info >= (3, 10):
    from evolution.search import (AdaptiveDE, ChaoticAnnealing, local_sample_points,
                                  negative_curvature_candidates)


def sphere(point):
    return sum((value - 0.35) ** 2 for value in point)


@unittest.skipIf(sys.version_info < (3, 10), "optional offline optimizer requires Python 3.10+")
class ChaoticAnnealingTests(unittest.TestCase):
    def test_worse_moves_are_possible_but_hard_failures_are_never_accepted(self):
        search = ChaoticAnnealing(19, 2, initial_temperature=1)
        self.assertTrue(any(search.accept(0, 0.01) for _ in range(20)))
        self.assertFalse(any(search.accept(0, -1, hard_ok=False) for _ in range(20)))
        self.assertFalse(search.accept(0, math.nan))
        self.assertFalse(search.accept(math.nan, 0))
        self.assertFalse(search.accept(0, math.inf))
        self.assertTrue(search.accept(math.inf, 0))

    def test_reflection_cooling_reheat_and_logistic_cycle_reset(self):
        search = ChaoticAnnealing(20, 2, cycle_length=4)
        temperatures = []
        for _ in range(9):
            temperatures.append(search.temperature)
            proposal = search.propose([0.0, 1.0])
            self.assertTrue(all(0 <= value <= 1 for value in proposal))
        self.assertLess(temperatures[3], temperatures[0])
        self.assertEqual(temperatures[4], temperatures[0])
        state = search.state()
        state["chaos"] = 0.75  # An exact logistic fixed point must trigger a reset.
        state["recent"] = [0.75]
        restored = ChaoticAnnealing.from_state(state)
        restored.propose([0.5, 0.5])
        self.assertGreater(restored.chaos_resets, search.chaos_resets)

    def test_json_resume_reproduces_proposals_and_acceptance(self):
        search = ChaoticAnnealing(2, 3)
        for _ in range(7):
            search.propose([0.4, 0.5, 0.6])
            search.accept(1, 1.1)
        restored = ChaoticAnnealing.from_state(json.loads(json.dumps(search.state(), allow_nan=False)))
        for _ in range(100):
            self.assertEqual(search.propose([0.2, 0.5, 0.9]), restored.propose([0.2, 0.5, 0.9]))
            self.assertEqual(search.accept(1, 1.03), restored.accept(1, 1.03))
        self.assertEqual(search.state(), restored.state())

    def test_invalid_parameters_and_checkpoint_are_rejected(self):
        for dimensions in (0, -1, True, 1.2):
            with self.assertRaises(ValueError):
                ChaoticAnnealing(1, dimensions)
        search = ChaoticAnnealing(1, 2)
        for point in ([math.nan, 0], [math.inf, 0], [1.01, 0], [0.5]):
            with self.assertRaises(ValueError):
                search.propose(point)
        state = search.state()
        state["chaos"] = math.nan
        with self.assertRaises(ValueError):
            ChaoticAnnealing.from_state(state)

    def test_subnormal_temperature_still_has_finite_bounded_proposals(self):
        search = ChaoticAnnealing(1, 1, initial_temperature=5e-324)
        for _ in range(100):
            self.assertTrue(all(math.isfinite(value) and 0 <= value <= 1
                                for value in search.propose([0.5])))
            self.assertFalse(search.accept(0, 1))


@unittest.skipIf(sys.version_info < (3, 10), "optional offline optimizer requires Python 3.10+")
class DifferentialEvolutionTests(unittest.TestCase):
    def make_search(self):
        rng = random.Random(31)
        population = [[rng.random() for _ in range(3)] for _ in range(18)]
        return AdaptiveDE(41, population, [sphere(point) for point in population])

    def test_jade_improves_measured_sphere_and_adapts(self):
        search = self.make_search()
        initial = min(search.losses)
        for _ in range(60):
            candidates = search.propose()
            self.assertTrue(all(0 <= value <= 1 for point in candidates for value in point))
            prior = list(search.losses)
            search.select(candidates, [sphere(point) for point in candidates])
            self.assertTrue(all(new <= old for new, old in zip(search.losses, prior)))
            self.assertLessEqual(len(search.archive), len(search.population))
        self.assertLess(min(search.losses), initial * 0.001)
        self.assertLess(min(search.losses), 1e-6)
        self.assertNotEqual((search.mu_f, search.mu_cr), (0.5, 0.5))

    def test_hard_rejected_generation_does_not_adapt_or_archive(self):
        search = self.make_search()
        before = copy.deepcopy(search.population)
        candidates = search.propose()
        search.select(candidates, [math.inf] * len(candidates))
        self.assertEqual(search.population, before)
        self.assertEqual(search.archive, [])
        self.assertEqual((search.mu_f, search.mu_cr), (0.5, 0.5))

    def test_json_resume_including_pending_generation(self):
        search = self.make_search()
        candidates = search.propose()
        restored = AdaptiveDE.from_state(json.loads(json.dumps(search.state(), allow_nan=False)))
        for item in (search, restored):
            item.select(candidates, [sphere(point) for point in candidates])
        for _ in range(8):
            candidates = search.propose()
            self.assertEqual(candidates, restored.propose())
            scores = [sphere(point) for point in candidates]
            search.select(candidates, scores)
            restored.select(candidates, scores)
        self.assertEqual(search.state(), restored.state())
        state = AdaptiveDE(1, [[0.1], [0.2], [0.3], [0.4]], [math.inf] * 4).state()
        json.dumps(state, allow_nan=False)
        self.assertEqual(AdaptiveDE.from_state(state).losses, [math.inf] * 4)

    def test_bad_dimensions_nan_and_mismatched_selection_fail(self):
        with self.assertRaises(ValueError):
            AdaptiveDE(1, [[0], [0], [0]], [0, 0, 0])
        with self.assertRaises(ValueError):
            AdaptiveDE(1, [[0], [0, 1], [0], [0]], [0] * 4)
        search = self.make_search()
        candidates = search.propose()
        with self.assertRaises(RuntimeError):
            search.propose()
        with self.assertRaises(ValueError):
            search.select(candidates, [math.nan] * len(candidates))
        modified = copy.deepcopy(candidates)
        modified[0][0] = 1 - modified[0][0]
        with self.assertRaises(ValueError):
            search.select(modified, [0] * len(candidates))
        search.select(candidates, [math.inf] * len(candidates))


@unittest.skipIf(sys.version_info < (3, 10), "optional offline optimizer requires Python 3.10+")
class CurvatureTests(unittest.TestCase):
    def measured(self, objective, center=None, radius=0.2):
        center = center or [0.5, 0.5]
        return [(point, objective(point)) for point in local_sample_points(center, radius)]

    def test_saddle_returns_both_measured_descent_directions(self):
        objective = lambda point: (point[0] - 0.5) ** 2 - 2 * (point[1] - 0.5) ** 2
        result = negative_curvature_candidates(self.measured(objective), [0.5, 0.5])
        self.assertTrue(result["diagnostics"]["trusted"], result)
        self.assertAlmostEqual(result["eigenvalue"], -4, places=7)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertTrue(all(objective(point) < 0 for point in result["candidates"]))
        self.assertGreaterEqual(result["diagnostics"]["min_direction_alignment"], 0.99)

    def test_rotated_saddle_recovers_cross_partial_and_eigenvector(self):
        objective = lambda point: 3 * (point[0] - 0.5) * (point[1] - 0.5)
        result = negative_curvature_candidates(self.measured(objective), [0.5, 0.5])
        self.assertTrue(result["diagnostics"]["trusted"], result)
        self.assertAlmostEqual(result["eigenvalue"], -3, places=7)
        self.assertTrue(all(objective(point) < -0.05 for point in result["candidates"]))

    def test_convex_constant_insufficient_and_nan_samples_abstain(self):
        convex = negative_curvature_candidates(self.measured(sphere), [0.5, 0.5])
        self.assertEqual(convex["candidates"], [])
        self.assertGreater(convex["eigenvalue"], 0)
        constant = negative_curvature_candidates(self.measured(lambda point: 1), [0.5, 0.5])
        self.assertEqual(constant["diagnostics"]["reason"], "no_significant_negative_curvature")
        insufficient = negative_curvature_candidates([([0.5, 0.5], 0)], [0.5, 0.5])
        self.assertEqual(insufficient["diagnostics"]["reason"], "insufficient_samples")
        invalid = negative_curvature_candidates([([0.5, 0.5], math.nan)], [0.5, 0.5])
        self.assertEqual(invalid["diagnostics"]["reason"], "nonfinite_sample")

    def test_duplicate_and_one_sided_coverage_do_not_fake_evidence(self):
        duplicate = negative_curvature_candidates([([0.5, 0.5], 0)] * 30, [0.5, 0.5])
        self.assertEqual(duplicate["diagnostics"]["reason"], "insufficient_samples")
        objective = lambda point: -(point[0] ** 2) + point[1] ** 2
        samples = self.measured(objective, [0.0, 0.5])
        result = negative_curvature_candidates(samples, [0.0, 0.5])
        self.assertFalse(result["diagnostics"]["trusted"])
        self.assertEqual(result["candidates"], [])

    def test_rank_deficiency_and_nonquadratic_noise_abstain(self):
        points = [[0.5 + index * 0.02, 0.5 + index * 0.02] for index in range(-6, 7)]
        rank = negative_curvature_candidates([(point, -(point[0] - 0.5) ** 2) for point in points],
                                             [0.5, 0.5])
        self.assertEqual(rank["diagnostics"]["reason"], "rank_deficient_or_ill_conditioned")
        rng = random.Random(17)
        samples = [(point, rng.uniform(-1, 1)) for point in local_sample_points([0.5, 0.5])]
        noisy = negative_curvature_candidates(samples, [0.5, 0.5])
        self.assertFalse(noisy["diagnostics"]["trusted"])
        self.assertEqual(noisy["candidates"], [])

    def test_one_dimensional_negative_curvature_and_boundary_validation(self):
        objective = lambda point: -(point[0] - 0.5) ** 2
        result = negative_curvature_candidates(self.measured(objective, [0.5]), [0.5])
        self.assertTrue(result["diagnostics"]["trusted"], result)
        self.assertAlmostEqual(result["eigenvalue"], -2, places=7)
        for center, radius in (([math.nan], 0.2), ([0.5], 0), ([0.5], math.inf)):
            with self.assertRaises(ValueError):
                local_sample_points(center, radius)

    def test_low_fit_error_cannot_replace_stable_direction_evidence(self):
        rng = random.Random(2)
        samples = [(point, -(point[0] - 0.5) ** 2 - 1.00001 * (point[1] - 0.5) ** 2 +
                    rng.uniform(-0.0001, 0.0001)) for point in local_sample_points([0.5, 0.5])]
        result = negative_curvature_candidates(samples, [0.5, 0.5])
        self.assertLess(result["diagnostics"]["relative_rmse"], 0.01)
        self.assertLess(result["eigenvalue"], 0)
        self.assertEqual(result["diagnostics"]["reason"], "unstable_curvature_direction")
        self.assertEqual(result["candidates"], [])


if __name__ == "__main__":
    unittest.main()
