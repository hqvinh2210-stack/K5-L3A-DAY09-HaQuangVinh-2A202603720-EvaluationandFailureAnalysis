"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np
from scipy import stats as scipy_stats

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge labels must have the same length")
    valid = {"PASS", "FAIL"}
    h = [str(label).strip().upper() for label in human]
    j = [str(label).strip().upper() for label in judge]
    if any(label not in valid for label in (*h, *j)):
        raise ValueError("labels must be PASS or FAIL")
    return {
        "tp": sum(a == POS and b == POS for a, b in zip(h, j)),
        "fp": sum(a != POS and b == POS for a, b in zip(h, j)),
        "fn": sum(a == POS and b != POS for a, b in zip(h, j)),
        "tn": sum(a != POS and b != POS for a, b in zip(h, j)),
    }


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision_denom = cm["tp"] + cm["fp"]
    recall_denom = cm["tp"] + cm["fn"]
    return (
        cm["tp"] / precision_denom if precision_denom else 0.0,
        cm["tp"] / recall_denom if recall_denom else 0.0,
    )


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if not n:
        raise ValueError("kappa is undefined for an empty sample")
    observed = (cm["tp"] + cm["tn"]) / n
    human_pos = (cm["tp"] + cm["fn"]) / n
    judge_pos = (cm["tp"] + cm["fp"]) / n
    expected = human_pos * judge_pos + (1.0 - human_pos) * (1.0 - judge_pos)
    if math.isclose(expected, 1.0, abs_tol=1e-12):
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (observed - expected) / (1.0 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    for name, value in (("observed_rate", observed_rate), ("sensitivity", sensitivity),
                        ("specificity", specificity)):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    denominator = sensitivity + specificity - 1.0
    if math.isclose(denominator, 0.0, abs_tol=1e-12):
        raise ValueError("Rogan-Gladen is undefined when sensitivity + specificity = 1")
    corrected = (observed_rate + specificity - 1.0) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    if len(a) == 0:
        raise ValueError("paired bootstrap needs at least one pair")
    if n_resamples <= 0 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid bootstrap configuration")
    left = np.asarray(a, dtype=float)
    right = np.asarray(b, dtype=float)
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("paired samples must be finite")
    delta = float(np.mean(left) - np.mean(right))
    if np.array_equal(left, right):
        return 0.0, 0.0, 0.0
    if len(left) == 1:
        return delta, delta, delta

    def mean_difference(x, y, axis=-1):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    result = scipy_stats.bootstrap(
        (left, right), mean_difference, paired=True, vectorized=True,
        n_resamples=n_resamples, method="percentile", confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    return delta, float(result.confidence_interval.low), float(result.confidence_interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_k(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_k(n, c, k)
    if c < k:
        return 0.0
    return math.comb(c, k) / math.comb(n, k)


def _validate_pass_k(n: int, c: int, k: int) -> None:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if n <= 0 or c < 0 or c > n or k <= 0 or k > n:
        raise ValueError("require n > 0, 0 <= c <= n and 1 <= k <= n")
