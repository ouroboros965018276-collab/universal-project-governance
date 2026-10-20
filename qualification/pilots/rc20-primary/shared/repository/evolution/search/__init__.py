"""Dependency-free, bounded numerical proposals for the offline optimizer.

These searches never evaluate an objective or authorize a deployment. Parameters
are normalized to [0, 1]; a caller supplies measured losses and hard constraints.
"""

from .annealing import ChaoticAnnealing
from .differential import AdaptiveDE
from .curvature import local_sample_points, negative_curvature_candidates

__all__ = [
    "ChaoticAnnealing", "AdaptiveDE", "local_sample_points",
    "negative_curvature_candidates",
]
