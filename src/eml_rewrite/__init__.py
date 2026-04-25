"""eml-rewrite — F-family fusion pattern rewriter.

Detects equivalent rewrites of symbolic expressions that strictly reduce
predicted EML cost (per ``eml-cost``). Provable non-regression: every
proposed rewrite either improves the cost or is filtered out.

Public API:

    >>> from eml_rewrite import suggest, best
    >>> import sympy as sp
    >>> x = sp.Symbol("x", real=True)
    >>> best(sp.exp(x) / (1 + sp.exp(x)))
    1/(1 + exp(-x))
    >>> # sigmoid pattern recognized; cost reduced from 3 to 2.

Command-line:

    $ eml-rewrite scan mycode.py
    $ eml-rewrite fix mycode.py
"""
from __future__ import annotations

from .core import (
    DomainRequirement,
    NO_REQUIREMENT,
    Suggestion,
    best,
    score,
    suggest,
    verify_equivalence,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "best",
    "suggest",
    "score",
    "Suggestion",
    "DomainRequirement",
    "NO_REQUIREMENT",
    "verify_equivalence",
]
