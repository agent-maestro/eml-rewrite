# eml-rewrite

**Pre-release alpha. Patent pending.** Source-available; see LICENSE.

F-family fusion pattern rewriter for symbolic expressions. Detects
equivalent rewrites that strictly reduce predicted EML cost (per
[`eml-cost`](https://github.com/almaguer1986/eml-cost)). The library's
headline guarantee: every proposed rewrite either improves the cost
or is filtered out.

## Installation

```bash
pip install --pre eml-rewrite
```

The `--pre` flag is required while we're on `0.1.0a0`. `eml-cost` is
installed as a dependency.

For local development:

```bash
git clone https://github.com/almaguer1986/eml-rewrite
cd eml-rewrite
pip install -e ".[dev]"
pytest
```

## Library API

```python
from eml_rewrite import suggest, best, score, Suggestion
import sympy as sp

x = sp.Symbol("x", real=True)

# Find improving rewrites (only those that strictly improve)
sugg = suggest(sp.exp(x) / (1 + sp.exp(x)))
# [Suggestion(pattern_name="sigmoid",
#             rewritten=1/(1 + exp(-x)),
#             score_before=3, score_after=2, reduction=1)]

# Pick the lowest-score rewrite, or original if no improvement
best(sp.sinh(x) / sp.cosh(x))
# tanh(x)

best(sp.exp(sp.exp(x)))
# exp(exp(x))   <- original; nothing in library matches
```

## Pattern library (9)

1. `exp(x)/(1+exp(x))` -> `1/(1+exp(-x))` — sigmoid canonicalization
2. `sinh(x)/cosh(x)` -> `tanh(x)` — F-family fusion
3. `(exp(x)+exp(-x))/2` -> `cosh(x)` — hyperbolic fusion (cosh)
4. `(exp(x)-exp(-x))/2` -> `sinh(x)` — hyperbolic fusion (sinh)
5. `sin(x)^2 + cos(x)^2` -> `1` — Pythagorean identity
6. `cosh(x)^2 - sinh(x)^2` -> `1` — hyperbolic identity
7. `exp(log(x))`, `log(exp(x))` -> `x` — inverse pair
8. `log(a/b)` -> `log(a) - log(b)` — when score improves
9. `log(x^n)` -> `n*log(x)` — when score improves

## Command line

```
eml-rewrite scan FILE [FILE ...]    # report rewrites without applying
eml-rewrite fix  FILE [FILE ...]    # show rewrites that would be applied
eml-rewrite analyze "exp(sin(x))"   # full Pfaffian profile + suggestions
```

Example:

```
$ eml-rewrite analyze "exp(x)/(1 + exp(x))"
Expression:           exp(x)/(exp(x) + 1)
  pfaffian_r:           1
  max_path_r:           1
  eml_depth:            2
  structural_overhead:  2
  corrections:          Corrections(c_osc=0, c_composite=0, delta_fused=0)
  predicted_depth:      3
  is_pfaffian_not_eml:  False

Suggested rewrites (1):
  [sigmoid] 1/(1 + exp(-x))  (-1 cost units)
```

## Provable non-regression

The library's contract:

```python
for expr in any_collection:
    for s in suggest(expr, only_improvements=True):
        assert s.score_after < s.score_before  # always
```

Every rewrite returned with `only_improvements=True` strictly reduces
the EML predicted depth (per `eml-cost`'s `measure`). The test suite
validates this on a curated panel; the engine filters non-improvements
before returning them.

## Links

- Project home: [monogate.org](https://monogate.org)
- Source: [github.com/almaguer1986/eml-rewrite](https://github.com/almaguer1986/eml-rewrite)
- Package: [pypi.org/project/eml-rewrite](https://pypi.org/project/eml-rewrite/)
- Companion: [eml-cost](https://github.com/almaguer1986/eml-cost) (required dependency)

## License

`PROPRIETARY-PRE-RELEASE`. See LICENSE.
