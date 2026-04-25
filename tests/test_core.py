"""Core API and pattern tests."""
from __future__ import annotations

import sympy as sp

from eml_rewrite import Suggestion, best, score, suggest


x = sp.Symbol("x", real=True, positive=True)
y = sp.Symbol("y", real=True, positive=True)


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------


def test_score_returns_int() -> None:
    assert isinstance(score(sp.exp(x)), int)


def test_score_lower_is_simpler() -> None:
    full = sp.sin(x) ** 2 + sp.cos(x) ** 2
    assert score(full) > score(sp.S.One)


# ---------------------------------------------------------------------------
# Pattern recognition (each must produce a Suggestion with reduction > 0)
# ---------------------------------------------------------------------------


def test_sigmoid_pattern_recognized() -> None:
    expr = sp.exp(x) / (1 + sp.exp(x))
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "sigmoid" for s in sugg)


def test_tanh_from_sinh_cosh_recognized() -> None:
    expr = sp.sinh(x) / sp.cosh(x)
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "tanh_from_sinh_cosh" for s in sugg)


def test_pythagorean_recognized() -> None:
    expr = sp.sin(x) ** 2 + sp.cos(x) ** 2
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "pythagorean" for s in sugg)


def test_hyperbolic_id_recognized() -> None:
    expr = sp.cosh(x) ** 2 - sp.sinh(x) ** 2
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "hyperbolic_id" for s in sugg)


def test_cosh_from_exps_recognized() -> None:
    expr = (sp.exp(x) + sp.exp(-x)) / 2
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "cosh_from_exps" for s in sugg)


def test_sinh_from_exps_recognized() -> None:
    expr = (sp.exp(x) - sp.exp(-x)) / 2
    sugg = suggest(expr, only_improvements=True)
    assert any(s.pattern_name == "sinh_from_exps" for s in sugg)


# ---------------------------------------------------------------------------
# Provable non-regression (THE patent-relevant claim)
# ---------------------------------------------------------------------------


def test_no_regression_across_panel() -> None:
    """Every Suggestion returned with only_improvements=True has score_after < score_before."""
    panel = [
        sp.exp(x) / (1 + sp.exp(x)),
        sp.sinh(x) / sp.cosh(x),
        sp.sin(x) ** 2 + sp.cos(x) ** 2,
        sp.cosh(x) ** 2 - sp.sinh(x) ** 2,
        (sp.exp(x) + sp.exp(-x)) / 2,
        (sp.exp(x) - sp.exp(-x)) / 2,
        sp.exp(sp.log(x)),
        # Cases with no improvement available
        sp.exp(x),
        sp.sin(x),
        sp.tan(x),
        sp.exp(sp.exp(x)),
        sp.log(1 + sp.exp(x)),
        x ** 5,
    ]
    for expr in panel:
        for s in suggest(expr, only_improvements=True):
            assert s.score_after < s.score_before, (
                f"Regression on {expr}: pattern={s.pattern_name} "
                f"before={s.score_before} after={s.score_after}"
            )


def test_best_non_regressing() -> None:
    """best(expr) never returns an expression with higher score."""
    panel = [
        sp.exp(x) / (1 + sp.exp(x)),
        sp.exp(x),
        sp.sin(x) ** 2 + sp.cos(x) ** 2,
        sp.exp(sp.exp(x)),
        x + y,
        sp.tan(x),
    ]
    for expr in panel:
        before = score(expr)
        after = score(best(expr))
        assert after <= before, f"Regression: {expr} -> {best(expr)} ({before} -> {after})"


def test_best_returns_original_when_no_improvement() -> None:
    expr = sp.exp(sp.exp(x))  # nothing in pattern library matches
    assert best(expr) == expr


# ---------------------------------------------------------------------------
# Suggestion dataclass shape
# ---------------------------------------------------------------------------


def test_suggestion_is_frozen() -> None:
    s = Suggestion(
        pattern_name="x", rewritten=sp.S.One,
        score_before=5, score_after=3, reduction=2,
    )
    import pytest
    with pytest.raises(Exception):
        s.score_before = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Reductions on hand-checked cases
# ---------------------------------------------------------------------------


def test_pythagorean_reduction_at_least_3() -> None:
    """sin^2 + cos^2 should reduce by at least 3 cost units."""
    sugg = suggest(sp.sin(x) ** 2 + sp.cos(x) ** 2, only_improvements=True)
    pyth = next((s for s in sugg if s.pattern_name == "pythagorean"), None)
    assert pyth is not None
    assert pyth.reduction >= 3


def test_sigmoid_reduces_score() -> None:
    expr = sp.exp(x) / (1 + sp.exp(x))
    rewritten = best(expr)
    assert score(rewritten) < score(expr)
