"""Pure statistical helpers. No I/O. Every function here is unit-tested."""
from __future__ import annotations
import math
from typing import Iterable, Sequence
import numpy as np
from . import config as C


def wilson_lower(k: int, n: int, z: float = C.WILSON_Z) -> float:
    """Lower bound of the Wilson score interval for k/n (conservative 'bad-rate').
    Returns NaN when n == 0, never negative."""
    if n <= 0:
        return float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def modified_z(x: float, peers: Sequence[float], higher_is_worse: bool = True,
               mad_floor: float | None = None) -> tuple[float, float, float]:
    """NIST/SEMATECH (Iglewicz & Hoaglin) modified z-score: M = 0.6745 (x - median) / MAD.
    Oriented so that positive = worse. Returns (M, median, MAD_used)."""
    arr = np.asarray([p for p in peers if p is not None and not math.isnan(p)], dtype=float)
    if arr.size == 0 or x is None or math.isnan(x):
        return float("nan"), float("nan"), float("nan")
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    if mad_floor is not None:
        mad = max(mad, mad_floor)
    if mad <= 0:
        return 0.0, med, mad
    m = 0.6745 * (x - med) / mad
    return (m if higher_is_worse else -m), med, mad


def concern_from_modz(m: float) -> float:
    """Map oriented modified z to 0-100: M = 3.5 (NIST outlier line) -> 50, M >= 7 -> 100."""
    if m is None or math.isnan(m):
        return float("nan")
    return 100.0 * min(max(m, 0.0), C.MODZ_CAP) / C.MODZ_CAP


def power_mean(values: Iterable[float], weights: Iterable[float] | None = None,
               p: float = C.POWER_MEAN_P) -> float:
    """Weighted power mean. p > 1 limits dilution of one serious concern by clean ones.
    NaN values are skipped and weights renormalised."""
    vals = np.asarray(list(values), dtype=float)
    w = np.ones_like(vals) if weights is None else np.asarray(list(weights), dtype=float)
    mask = ~np.isnan(vals)
    if not mask.any():
        return float("nan")
    vals, w = vals[mask], w[mask]
    w = w / w.sum()
    return round(float(np.sum(w * np.power(vals, p)) ** (1.0 / p)), 9)   # round away float noise (e.g. 8e-16)


def poisson_p_zero(rate: float) -> float:
    """P(0 events) for a Poisson with the given expected count."""
    return math.exp(-max(rate, 0.0))


def binomial_se(p: float, n: int) -> float:
    """Sampling standard error of a proportion p with n trials (0 if undefined)."""
    if n <= 0 or p is None or math.isnan(p):
        return 0.0
    p = min(max(p, 1.0 / (2 * n)), 1 - 1.0 / (2 * n))   # continuity guard so p=0 still has sampling noise
    return math.sqrt(p * (1 - p) / n)


def binomial_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Exact sum; n is small (asset counts)."""
    if k <= 0:
        return 1.0
    return float(sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))
