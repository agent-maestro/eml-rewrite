# eml-rewrite

**Stable beta. Patent pending.** Source-available; see LICENSE.

F-family fusion pattern rewriter for symbolic expressions. Detects
equivalent rewrites that strictly reduce predicted EML cost (per
[`eml-cost`](https://github.com/almaguer1986/eml-cost)). The library's
headline guarantee: every proposed rewrite clears three independent
gates (cost, domain, numerical equivalence) before it's surfaced to
the caller.

## Installation

```bash
pip install eml-rewrite
```

`eml-cost` is installed as a dependency.

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
#             score_before=3, score_after=2, reduction=1,
#             domain_required="", domain_verified=True,
#             numerically_verified=True)]

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

## Real-world examples

### Scanning a SciPy-style script

```python
# stats.py
from sympy import Symbol, exp, log
x = Symbol("x", positive=True)
log(x ** 4)                  # gets flagged: log_pow rewrite available
exp(x) / (1 + exp(x))        # gets flagged: sigmoid canonicalization
```

```bash
$ eml-rewrite scan stats.py
stats.py:3  log(x**4)
  -> 4*log(x)  (log_pow, -0 cost units)
stats.py:4  exp(x)/(exp(x) + 1)
  -> 1/(1 + exp(-x))  (sigmoid, -1 cost units)

Found 2 improving rewrite(s) across 1 file(s).
```

### Fixing a PyTorch-flavored model definition

```python
# model.py — math written by hand for clarity, then auto-canonicalized
from sympy import Symbol, exp, sinh, cosh
x = Symbol("x", real=True, positive=True)
sinh(x) / cosh(x)            # → tanh(x)
exp(x) / (1 + exp(x))        # → 1/(1 + exp(-x))
```

```bash
$ eml-rewrite fix model.py
model.py:3  sinh(x)/cosh(x)
  Would rewrite to: tanh(x)
model.py:4  exp(x)/(exp(x) + 1)
  Would rewrite to: 1/(1 + exp(-x))

Would apply 2 rewrite(s) across 1 file(s).
NOTE: v0.1 prints proposed rewrites only.
```

### Surfacing conditional rewrites for editor / notebook UX

```bash
$ eml-rewrite analyze "log(x**4)" --include-conditional
Expression:           log(x**4)
  pfaffian_r:           1
  ...

Suggested rewrites (1):
  [log_pow | conditional: x > 0] 4*log(x)  (-0 cost units)
```

The `conditional:` annotation appears when the rewrite's domain
requirement (here, `x > 0`) cannot be established by SymPy's
assumption system. Without `--include-conditional`, the rewrite
is silently rejected. With it, the requirement is annotated so the
caller can prompt or confirm.

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

## Non-regression: three layers

Every rewrite returned with `only_improvements=True` is required to
clear three independent gates before being surfaced to the caller.

### 1. Cost gate

```python
for s in suggest(expr, only_improvements=True):
    assert s.score_after < s.score_before
```

Strict EML cost reduction (per `eml-cost`'s `measure`) — the
historical headline guarantee. Suggestions whose post-rewrite cost is
not strictly lower are filtered out before return.

### 2. Domain gate

A subset of the rewrites in the library are valid only on a restricted
input domain. Examples:

| Pattern | Identity | Valid when |
|---|---|---|
| `log(x^n) -> n*log(x)` | real-valued log identity | `x > 0` |
| `log(a/b) -> log(a) - log(b)` | log split | `a > 0` and `b > 0` |
| `exp(log(x)) -> x` | inverse pair | `x > 0` |
| `log(exp(x)) -> x` | inverse pair (branch correctness) | `x` real |

For these patterns, the engine probes SymPy's assumption system
against the relevant subexpression (`expr.is_positive`,
`expr.is_real`). A rewrite is accepted only when the assumption
required for soundness is established by the assumption system. So:

```python
import sympy as sp
from eml_rewrite import suggest

# Unconstrained symbol — no positivity assumption available.
u = sp.Symbol("u")
suggest(sp.log(u**2))           # []  (log_pow rejected; would silently
                                #      produce a complex value for u<0)

# Same expression with a positive symbol — accepted.
x = sp.Symbol("x", positive=True)
suggest(sp.log(x**2), only_improvements=False)
# [Suggestion(pattern_name='log_pow', rewritten=2*log(x),
#             domain_required='x > 0', domain_verified=True, ...)]

# Conditional mode: surface the rewrite WITH the requirement annotated
# rather than dropping it silently. Useful for editor / notebook UI.
suggest(sp.log(u**2), only_improvements=False, include_conditional=True)
# [Suggestion(pattern_name='log_pow', rewritten=2*log(u),
#             domain_required='u > 0', domain_verified=False, ...)]
```

### 3. Numerical-equivalence gate

After the structural and domain gates pass, the engine evaluates both
the original and the rewritten expression at sample points drawn from
regions consistent with each free symbol's SymPy assumptions
(positive, negative, near-zero, moderately large). Evaluation runs at
30 decimal digits via SymPy's `evalf`, with a fast path that
short-circuits when SymPy's `simplify` proves the identity directly
— this avoids false positives on rewrites that *improve* numerical
stability (e.g., `cosh(x)^2 - sinh(x)^2 -> 1` at large `x`, where
float-precision evaluation of the original collapses to zero from
catastrophic cancellation).

A rewrite that disagrees on any probed point — including a one-sided
domain error indicating the rewrite changes the domain of definition
— is rejected. Set `numerical_verify=False` only for benchmarking
the structural+domain layers in isolation.

### Verifying equivalence directly

```python
from eml_rewrite import verify_equivalence
import sympy as sp

u = sp.Symbol("u")
verify_equivalence(sp.log(u**2), 2 * sp.log(u))
# False  (disagrees on u<0)

verify_equivalence(sp.sin(u)**2 + sp.cos(u)**2, sp.S.One)
# True   (universal identity)
```

## Links

- Project home: [monogate.org](https://monogate.org)
- Source: [github.com/almaguer1986/eml-rewrite](https://github.com/almaguer1986/eml-rewrite)
- Package: [pypi.org/project/eml-rewrite](https://pypi.org/project/eml-rewrite/)
- Companion: [eml-cost](https://github.com/almaguer1986/eml-cost) (required dependency)

## License

`PROPRIETARY-PRE-RELEASE`. See LICENSE.
