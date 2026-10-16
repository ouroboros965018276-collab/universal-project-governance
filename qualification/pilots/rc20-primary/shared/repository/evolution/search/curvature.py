"""Conservative local quadratic curvature estimates from measured samples.

Hessian estimates are diagnostic evidence, never ground truth about a discrete
prompt search space. A negative direction is exposed only after coverage, fit,
leave-one-out prediction and eigenvector stability checks succeed.
"""

import math

from ._numeric import positive, vector


def local_sample_points(center, radius=0.2):
    """Return a deterministic, overdetermined local stencil in the unit cube.

    Evaluate these points with the same objective before fitting. At a boundary
    the remaining stencil may lack two-sided coverage; the fitter then abstains.
    """
    center = vector(center)
    radius = positive(radius, "radius")
    if len(center) > 12 or not 1e-8 <= radius <= 1:
        raise ValueError("curvature stencils support <= 12 dimensions and radius in [1e-8, 1]")
    points = [center]
    for dim in range(len(center)):
        for scale in (-1.0, -0.5, 0.5, 1.0):
            point = list(center)
            point[dim] += scale * radius
            if all(0 <= value <= 1 for value in point):
                points.append(point)
    for first in range(len(center)):
        for second in range(first + 1, len(center)):
            for one, two in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                point = list(center)
                point[first] += one * radius / math.sqrt(2)
                point[second] += two * radius / math.sqrt(2)
                if all(0 <= value <= 1 for value in point):
                    points.append(point)
    return points


def _features(offset):
    return ([1.0] + list(offset) + [0.5 * item * item for item in offset] +
            [offset[first] * offset[second] for first in range(len(offset))
             for second in range(first + 1, len(offset))])


def _solve(matrix, response):
    """Pivoted elimination, rejecting rank-deficient/ill-conditioned fits."""
    size = len(response)
    augmented = [list(row) + [value] for row, value in zip(matrix, response)]
    scale = max(abs(value) for row in matrix for value in row)
    if not math.isfinite(scale) or scale == 0:
        return None
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < scale * 1e-10:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        for item in range(column, size + 1):
            augmented[column][item] /= divisor
        for row in range(column + 1, size):
            factor = augmented[row][column]
            for item in range(column, size + 1):
                augmented[row][item] -= factor * augmented[column][item]
    result = [0.0] * size
    for row in range(size - 1, -1, -1):
        result[row] = augmented[row][size] - sum(
            augmented[row][column] * result[column] for column in range(row + 1, size))
    return result if all(math.isfinite(value) for value in result) else None


def _fit(rows, values, dimensions):
    width = len(rows[0])
    baseline = sum(value / len(values) for value in values)
    shifted = [value - baseline for value in values]
    if not all(math.isfinite(value) for value in shifted):
        return None
    matrix = [[sum(row[first] * row[second] for row in rows)
               for second in range(width)] for first in range(width)]
    response = [sum(row[column] * value for row, value in zip(rows, shifted))
                for column in range(width)]
    coefficients = _solve(matrix, response)
    if coefficients is None:
        return None
    predictions = [baseline + sum(one * two for one, two in zip(row, coefficients))
                   for row in rows]
    residual = math.hypot(*(prediction - value for prediction, value in zip(predictions, values))) / math.sqrt(len(values))
    hessian = [[0.0] * dimensions for _ in range(dimensions)]
    for dim in range(dimensions):
        hessian[dim][dim] = coefficients[1 + dimensions + dim]
    index = 1 + 2 * dimensions
    for first in range(dimensions):
        for second in range(first + 1, dimensions):
            hessian[first][second] = hessian[second][first] = coefficients[index]
            index += 1
    eigenvalue, direction = _smallest_eigenpair(hessian)
    return dict(coefficients=coefficients, baseline=baseline, residual=residual,
                eigenvalue=eigenvalue, direction=direction)


def _smallest_eigenpair(matrix):
    """Jacobi rotations for a real symmetric small Hessian."""
    size = len(matrix)
    values = [list(row) for row in matrix]
    vectors = [[float(first == second) for second in range(size)] for first in range(size)]
    magnitude = max(abs(value) for row in values for value in row)
    for _ in range(100 * size * size):
        if size == 1:
            break
        first, second = max(((one, two) for one in range(size) for two in range(one + 1, size)),
                            key=lambda pair: abs(values[pair[0]][pair[1]]))
        off = values[first][second]
        if abs(off) <= max(1e-15, magnitude * 1e-12):
            break
        angle = 0.5 * math.atan2(2 * off, values[second][second] - values[first][first])
        cosine, sine = math.cos(angle), math.sin(angle)
        one, two = values[first][first], values[second][second]
        values[first][first] = cosine * cosine * one - 2 * sine * cosine * off + sine * sine * two
        values[second][second] = sine * sine * one + 2 * sine * cosine * off + cosine * cosine * two
        values[first][second] = values[second][first] = 0.0
        for row in range(size):
            if row not in (first, second):
                a, b = values[row][first], values[row][second]
                values[row][first] = values[first][row] = cosine * a - sine * b
                values[row][second] = values[second][row] = sine * a + cosine * b
            a, b = vectors[row][first], vectors[row][second]
            vectors[row][first], vectors[row][second] = cosine * a - sine * b, sine * a + cosine * b
    index = min(range(size), key=lambda item: values[item][item])
    return values[index][index], [row[index] for row in vectors]


def negative_curvature_candidates(samples, center, radius=0.2):
    """Fit and validate a local Hessian; return two directions or abstain.

    The returned eigenvalue is the measured quadratic estimate (or None when no
    estimate exists). Rejection never replaces a positive value with a negative
    one. Diagnostics explain each conservative rejection and include fit checks.
    """
    center = vector(center)
    radius = positive(radius, "radius")
    diagnostics = {"trusted": False, "reason": "unverified", "sample_count": 0,
                   "dimensions": len(center), "ignored_outside_radius": 0}
    result = {"candidates": [], "eigenvalue": None, "diagnostics": diagnostics}

    def reject(reason):
        diagnostics["reason"] = reason
        return result

    dimensions = len(center)
    if dimensions > 12 or not 1e-8 <= radius <= 1:
        return reject("unsupported_dimensions_or_radius")
    measured = {}
    try:
        for point, value in samples:
            point, value = vector(point, dimensions), float(value)
            if not math.isfinite(value):
                return reject("nonfinite_sample")
            distance = math.sqrt(sum((one - two) ** 2 for one, two in zip(point, center)))
            if distance > radius * (1 + 1e-8):
                diagnostics["ignored_outside_radius"] += 1
                continue
            measured.setdefault(tuple(point), []).append(value)
    except (TypeError, ValueError, OverflowError):
        return reject("invalid_sample")
    points = sorted(measured)
    # Repeated measurements count as one geometric observation.
    values = [sum(value / len(measured[point]) for value in measured[point]) for point in points]
    diagnostics["sample_count"] = len(points)
    parameters = 1 + dimensions + dimensions * (dimensions + 1) // 2
    diagnostics["fit_parameters"] = parameters
    if len(points) < parameters + max(2, dimensions):
        return reject("insufficient_samples")
    offsets = [[(value - origin) / radius for value, origin in zip(point, center)] for point in points]
    if any(min(row[dim] for row in offsets) > -0.25 or max(row[dim] for row in offsets) < 0.25
           for dim in range(dimensions)):
        return reject("insufficient_two_sided_coverage")
    rows = [_features(row) for row in offsets]
    fit = _fit(rows, values, dimensions)
    if fit is None:
        return reject("rank_deficient_or_ill_conditioned")
    result["eigenvalue"] = fit["eigenvalue"] / (radius * radius)
    if not math.isfinite(result["eigenvalue"]):
        result["eigenvalue"] = None
        return reject("nonfinite_fit")
    baseline = sum(value / len(values) for value in values)
    variation = math.hypot(*(value - baseline for value in values)) / math.sqrt(len(values))
    scale = max(variation, 1e-12)
    relative_rmse = fit["residual"] / scale
    diagnostics.update(rmse=fit["residual"], relative_rmse=relative_rmse,
                       direction=list(fit["direction"]))
    if not math.isfinite(relative_rmse) or relative_rmse > 0.1:
        return reject("quadratic_fit_error")
    threshold = max(1e-10, variation * 1e-6, 8 * fit["residual"])
    if fit["eigenvalue"] >= -threshold:
        return reject("no_significant_negative_curvature")
    checks = sorted({round(index * (len(points) - 1) / min(7, len(points) - 1))
                     for index in range(min(8, len(points)))})
    minimum_alignment, maximum_error, maximum_change = 1.0, 0.0, 0.0
    for omitted in checks:
        partial = _fit([row for index, row in enumerate(rows) if index != omitted],
                       [value for index, value in enumerate(values) if index != omitted], dimensions)
        if partial is None:
            return reject("unstable_leave_one_out_fit")
        prediction = partial["baseline"] + sum(one * two for one, two in
                                              zip(rows[omitted], partial["coefficients"]))
        maximum_error = max(maximum_error, abs(prediction - values[omitted]) / scale)
        minimum_alignment = min(minimum_alignment, abs(sum(
            one * two for one, two in zip(fit["direction"], partial["direction"]))))
        maximum_change = max(maximum_change, abs(partial["eigenvalue"] - fit["eigenvalue"]) /
                             abs(fit["eigenvalue"]))
        if partial["eigenvalue"] >= -threshold:
            minimum_alignment = 0.0
    diagnostics.update(leave_one_out_checks=len(checks),
                       max_prediction_error=maximum_error,
                       min_direction_alignment=minimum_alignment,
                       max_eigenvalue_change=maximum_change)
    if maximum_error > 0.15 or minimum_alignment < 0.9 or maximum_change > 0.5:
        return reject("unstable_curvature_direction")
    direction = fit["direction"]
    step = min([radius] + [min(origin, 1 - origin) / abs(value)
                           for origin, value in zip(center, direction) if abs(value) > 1e-12])
    if step < radius * 0.25:
        return reject("insufficient_boundary_room")
    result["candidates"] = [[max(0.0, min(1.0, origin + sign * step * value))
                             for origin, value in zip(center, direction)] for sign in (-1, 1)]
    diagnostics.update(trusted=True, reason="trusted_negative_curvature", step=step)
    return result
