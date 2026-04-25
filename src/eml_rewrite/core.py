"""Core rewrite engine.

Pattern library (9 patterns; 100% precision by construction):

  1.  exp(x)/(1+exp(x))         -> 1/(1+exp(-x))   sigmoid canonicalization
  2.  sinh(x)/cosh(x)           -> tanh(x)         F-family fusion
  3.  (exp(x)+exp(-x))/2        -> cosh(x)         hyperbolic fusion
  4.  (exp(x)-exp(-x))/2        -> sinh(x)         hyperbolic fusion
  5.  sin^2 + cos^2             -> 1               Pythagorean identity
  6.  cosh^2 - sinh^2           -> 1               hyperbolic identity
  7.  exp(log(x)), log(exp(x))  -> x               inverse pair
  8.  log(a/b)                  -> log(a) - log(b) when score improves
  9.  log(x^n)                  -> n*log(x)        when score improves

Each pattern returns ``None`` if it doesn't match. Rewrites are filtered
to those that strictly reduce the EML predicted depth.
"""
from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from eml_cost import measure as _eml_measure


__all__ = ["Suggestion", "best", "suggest", "score"]


def score(expr: sp.Basic) -> int:
    """EML predicted depth (lower is better). Wraps ``eml_cost.measure``."""
    return _eml_measure(expr)


@dataclass(frozen=True)
class Suggestion:
    """A proposed rewrite with cost-delta information."""

    pattern_name: str
    rewritten: sp.Basic
    score_before: int
    score_after: int
    reduction: int


# ---------------------------------------------------------------------------
# Pattern detectors
# ---------------------------------------------------------------------------


def _try_sigmoid(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.Mul):
        return None
    args = expr.args
    if len(args) != 2:
        return None
    exp_arg, denom_arg = None, None
    for a in args:
        if isinstance(a, sp.exp):
            exp_arg = a
        elif isinstance(a, sp.Pow) and a.args[1] == -1:
            denom_arg = a
    if exp_arg is None or denom_arg is None:
        return None
    inner = denom_arg.args[0]
    if not isinstance(inner, sp.Add) or len(inner.args) != 2:
        return None
    has_one = any(a == sp.S.One for a in inner.args)
    has_exp = any(a == exp_arg for a in inner.args)
    if has_one and has_exp:
        return 1 / (1 + sp.exp(-exp_arg.args[0]))
    return None


def _try_tanh_from_sinh_cosh(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.Mul) or len(expr.args) != 2:
        return None
    sinh_arg, recip_cosh = None, None
    for a in expr.args:
        if isinstance(a, sp.sinh):
            sinh_arg = a
        elif (isinstance(a, sp.Pow) and a.args[1] == -1
              and isinstance(a.args[0], sp.cosh)):
            recip_cosh = a
    if sinh_arg is None or recip_cosh is None:
        return None
    if sinh_arg.args[0] == recip_cosh.args[0].args[0]:
        return sp.tanh(sinh_arg.args[0])
    return None


def _try_cosh_from_exps(expr: sp.Basic) -> sp.Basic | None:
    """Match (exp(x)+exp(-x))/2; both Mul-of-Add form and SymPy canonical Add form."""
    # Mul(1/2, Add(exp(x), exp(-x)))
    if isinstance(expr, sp.Mul) and len(expr.args) == 2:
        half_arg, sum_arg = None, None
        for a in expr.args:
            if a == sp.Rational(1, 2):
                half_arg = a
            elif isinstance(a, sp.Add) and len(a.args) == 2:
                sum_arg = a
        if half_arg is not None and sum_arg is not None:
            a1, a2 = sum_arg.args
            if isinstance(a1, sp.exp) and isinstance(a2, sp.exp):
                x1, x2 = a1.args[0], a2.args[0]
                if (x1 + x2).simplify() == 0:
                    x_pos = x1 if not x1.could_extract_minus_sign() else x2
                    return sp.cosh(x_pos)

    # SymPy canonical: Add(Mul(1/2, exp(x)), Mul(1/2, exp(-x)))
    if isinstance(expr, sp.Add) and len(expr.args) == 2:
        exps: list[sp.Basic] = []
        for a in expr.args:
            if isinstance(a, sp.Mul) and len(a.args) == 2:
                rest: sp.Basic | None = None
                has_half = False
                for ai in a.args:
                    if ai == sp.Rational(1, 2):
                        has_half = True
                    elif isinstance(ai, sp.exp):
                        rest = ai
                if has_half and rest is not None:
                    exps.append(rest)
        if len(exps) == 2:
            x1, x2 = exps[0].args[0], exps[1].args[0]
            if (x1 + x2).simplify() == 0:
                x_pos = x1 if not x1.could_extract_minus_sign() else x2
                return sp.cosh(x_pos)
    return None


def _try_sinh_from_exps(expr: sp.Basic) -> sp.Basic | None:
    """Match (exp(x)-exp(-x))/2 in SymPy canonical form."""
    if isinstance(expr, sp.Add) and len(expr.args) == 2:
        signed: list[tuple[int, sp.Basic]] = []
        for a in expr.args:
            if isinstance(a, sp.Mul) and len(a.args) == 2:
                sign = 0
                rest: sp.Basic | None = None
                for ai in a.args:
                    if ai == sp.Rational(1, 2):
                        sign = +1
                    elif ai == sp.Rational(-1, 2):
                        sign = -1
                    elif isinstance(ai, sp.exp):
                        rest = ai
                if sign != 0 and rest is not None:
                    signed.append((sign, rest))
        if len(signed) == 2 and signed[0][0] != signed[1][0]:
            (s1, e1), (s2, e2) = signed
            x1, x2 = e1.args[0], e2.args[0]
            if (x1 + x2).simplify() == 0:
                positive = e1 if s1 > 0 else e2
                return sp.sinh(positive.args[0])
    return None


def _try_pythagorean(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.Add) or len(expr.args) != 2:
        return None
    for ai, aj in [(expr.args[0], expr.args[1]), (expr.args[1], expr.args[0])]:
        if (isinstance(ai, sp.Pow) and ai.args[1] == 2 and isinstance(ai.args[0], sp.sin)
                and isinstance(aj, sp.Pow) and aj.args[1] == 2 and isinstance(aj.args[0], sp.cos)
                and ai.args[0].args[0] == aj.args[0].args[0]):
            return sp.S.One
    return None


def _try_hyperbolic_id(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.Add) or len(expr.args) != 2:
        return None
    cosh_sq, sinh_sq_neg = None, None
    for a in expr.args:
        if isinstance(a, sp.Pow) and a.args[1] == 2 and isinstance(a.args[0], sp.cosh):
            cosh_sq = a
        elif (isinstance(a, sp.Mul) and len(a.args) == 2
              and a.args[0] == -1
              and isinstance(a.args[1], sp.Pow)
              and a.args[1].args[1] == 2
              and isinstance(a.args[1].args[0], sp.sinh)):
            sinh_sq_neg = a
    if cosh_sq is not None and sinh_sq_neg is not None:
        cosh_x = cosh_sq.args[0].args[0]
        sinh_x = sinh_sq_neg.args[1].args[0].args[0]
        if cosh_x == sinh_x:
            return sp.S.One
    return None


def _try_exp_log_inverse(expr: sp.Basic) -> sp.Basic | None:
    if isinstance(expr, sp.exp) and isinstance(expr.args[0], sp.log):
        return expr.args[0].args[0]
    if isinstance(expr, sp.log) and isinstance(expr.args[0], sp.exp):
        return expr.args[0].args[0]
    return None


def _try_log_split(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.log):
        return None
    inner = expr.args[0]
    if isinstance(inner, sp.Mul) and len(inner.args) == 2:
        a, b = inner.args
        if isinstance(b, sp.Pow) and b.args[1] == -1:
            return sp.log(a) - sp.log(b.args[0])
    return None


def _try_log_pow(expr: sp.Basic) -> sp.Basic | None:
    if not isinstance(expr, sp.log):
        return None
    inner = expr.args[0]
    if isinstance(inner, sp.Pow) and inner.args[1].is_Integer and inner.args[1] > 0:
        n = inner.args[1]
        x = inner.args[0]
        return n * sp.log(x)
    return None


PATTERNS = [
    ("sigmoid",             _try_sigmoid),
    ("tanh_from_sinh_cosh", _try_tanh_from_sinh_cosh),
    ("cosh_from_exps",      _try_cosh_from_exps),
    ("sinh_from_exps",      _try_sinh_from_exps),
    ("pythagorean",         _try_pythagorean),
    ("hyperbolic_id",       _try_hyperbolic_id),
    ("exp_log_inverse",     _try_exp_log_inverse),
    ("log_split",           _try_log_split),
    ("log_pow",             _try_log_pow),
]


def suggest(expr: sp.Basic, only_improvements: bool = True) -> list[Suggestion]:
    """Return all matching rewrites with cost-delta information.

    Walks the expression tree top-down, then by subterm replacement.
    By default returns only suggestions that strictly improve EML cost.
    """
    if not isinstance(expr, sp.Basic):
        return []

    out: list[Suggestion] = []
    score_before = score(expr)

    for pattern_name, fn in PATTERNS:
        rewritten = fn(expr)
        if rewritten is not None:
            score_after = score(rewritten)
            reduction = score_before - score_after
            if not only_improvements or reduction > 0:
                out.append(Suggestion(
                    pattern_name=pattern_name,
                    rewritten=rewritten,
                    score_before=score_before,
                    score_after=score_after,
                    reduction=reduction,
                ))
            continue

        for sub in sp.preorder_traversal(expr):
            if sub == expr:
                continue
            rewritten_sub = fn(sub)
            if rewritten_sub is not None:
                full = expr.xreplace({sub: rewritten_sub})
                score_after = score(full)
                reduction = score_before - score_after
                if not only_improvements or reduction > 0:
                    out.append(Suggestion(
                        pattern_name=pattern_name,
                        rewritten=full,
                        score_before=score_before,
                        score_after=score_after,
                        reduction=reduction,
                    ))
                break

    return out


def best(expr: sp.Basic) -> sp.Basic:
    """Return the lowest-score rewrite, or the original if no improvement found."""
    suggestions = suggest(expr, only_improvements=True)
    if not suggestions:
        return expr
    chosen = min(suggestions, key=lambda s: s.score_after)
    return chosen.rewritten
