# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project will adhere to [Semantic Versioning](https://semver.org/) once
the public 1.0.0 release ships.

## [0.5.1] — 2026-04-26 — bugfix: aggressive strategy AttributeError

### Fixed
- `pipeline.rewrite(strategy="aggressive")` crashed with
  `AttributeError: 'Suggestion' object has no attribute 'rule'` whenever
  a candidate suggestion both lowered cost AND verified-equivalent —
  the success-path log line accessed the wrong field name. The actual
  field on `Suggestion` is `pattern_name`. The 0.5.0 release shipped
  with the bug because mypy strict mode caught it only after publish.
  No public API change; only the log string is affected.

## [0.5.0] — 2026-04-26 — `to_canonical()` + `rewrite(strategy=...)` pipeline

### Added
- **`pipeline.to_canonical(expr)`**: thin wrapper over
  `eml_cost.canonicalize` returning a `CanonicalForm` (original,
  canonical, cost_before, cost_after, savings_pct).
- **`pipeline.rewrite(expr, strategy="canonical"|"optimal"|"aggressive")`**:
  end-to-end orchestrator with verified-equivalence gates. Each step
  must (1) lower or equal the cost and (2) verify equivalent before it
  is accepted into the chain. Returns a `RewriteResult` with the rule
  trail and a final `verified_equivalent` boolean.

## [0.4.0] — 2026-04-25 — `@costlimit_or_fix` + `render_test`

### Added
- **`@costlimit_or_fix(predicted_depth=N, max_path_r=N, pfaffian_r=N,
  max_search_steps=8)`**: backward-cost guarantor decorator. Same
  configuration surface as `eml_cost.costlimit`, but on over-budget
  return values it walks the rewrite graph (best-first, cost-monotone)
  looking for an equivalent under-budget form and silently substitutes
  the first one it finds. If no fix exists within budget, raises
  `CostFixFailed` (a `CostLimitExceeded` subclass) with the search
  trail attached so callers see what was tried. Substitution is sound
  by construction — the rewrite library's three-layer non-regression
  gates every step.
- **`CostFixFailed`** exception (exported). Adds `.search_trail:
  list[Step]` to the parent `CostLimitExceeded` payload.
- **`render_test(cx, name="...", precision=15) -> str`**: counterexample-
  driven test synthesizer. Takes a `Counterexample` from
  `find_counterexample` and emits a runnable pytest test source string
  that pins the disagreement as a permanent regression case. The
  rendered test uses `sp.S(srepr(...))` for round-trip-safe expression
  serialization (preserves symbol assumptions) and binds the
  substitution point by symbol name. Self-contained except for sympy.
- **`Counterexample.before_expr` / `Counterexample.after_expr`**: two
  new optional fields on the `Counterexample` dataclass (default `None`
  for backwards compatibility). `find_counterexample` now populates
  them so `render_test` can reference the original expressions without
  duplicate plumbing.

Use cases: cost contracts that auto-comply (no more brittle test
failures from unexpected expression growth), and property-based
testing that converts each found counterexample into a permanent
CI gate without manual transcription.

### Tests
- 8 new cases in `tests/test_fix.py` (`@costlimit_or_fix` happy
  path + failure path + trail capture + non-Basic passthrough +
  decorator-time validation).
- 9 new cases in `tests/test_synthesize.py` (`render_test` —
  including meta-tests that exec the generated source and confirm
  it asserts as expected).
- Full suite: 99 passing.

## [0.3.0] — 2026-04-25 — Bidirectional rewrites (`expand` / `expand_fully`)

### Added
- `expand(expr) -> list[Suggestion]`: returns equivalent forms with
  *higher* predicted cost — the opposite direction of `suggest()`.
  Useful for pedagogy ("show me what tanh really is"), paper writing
  (explicit form when canonical is too dense), test generation
  (synthesize ugly equivalents), and reverse-engineering.
- `expand_fully(expr, max_depth=6) -> Basic`: recursively applies
  `expand` until no more expansions apply or the depth budget is
  exhausted. For `tanh(x)` this walks
  `tanh → sinh/cosh → ((exp diff)/(exp sum))` in one call.
- `EXPANSION_PATTERNS` registry of the four reverse patterns:
  `tanh → sinh/cosh`, `cosh → (exp(x)+exp(-x))/2`,
  `sinh → (exp(x)-exp(-x))/2`, `1/(1+exp(-x)) → exp(x)/(1+exp(x))`.
  Patterns whose forward direction destroys information
  (Pythagorean identity, hyperbolic identity, exp/log inverse) are
  explicitly NOT reversed because the input → output mapping is
  not invertible.

### Tests
- 16 new cases in `tests/test_expansions.py`. Full suite: 82 passing.

## [0.2.1] — 2026-04-25 — CLI patch mode + IPython integration

### Added
- `eml-rewrite scan --as-patch FILE`: emits a unified diff
  (suitable for `git apply`) instead of the human-readable report.
  Uses AST source spans for exact in-place substitution, so
  whitespace differences between source and `ast.unparse` output
  don't cause silent skips. Stdout is git-apply-clean (no
  summary lines).
- `eml_rewrite.notebook` module with `%%eml_rewrite` cell magic.
  Load via `%load_ext eml_rewrite.notebook`; tagged cells print
  a rewrite report above their normal execution. IPython is not
  a hard dependency — module imports cleanly without it; the
  magic registers only when `load_ipython_extension` is called.

### Tests
- 1 new CLI test (`test_scan_as_patch_emits_unified_diff`) +
  8 new notebook tests (`tests/test_notebook.py`). Full suite:
  66 passing.

## [0.2.0] — 2026-04-25 — Cost-anneal interpolation path

### Added
- `path(start, end) -> list[Step] | None`: best-first search through
  rewrite-equivalent expressions with monotone-decrease cost gate.
  Returns the rewrite *sequence* that walks from one equivalent
  expression to another, step by step, with non-increasing cost
  at every step. Returns `None` when no path exists within the
  configured budget (default `max_steps=6`, `max_frontier=256`).
- `Step` frozen dataclass: `(pattern_name, expression, cost)`.
- Use cases: pedagogy ("why is the simplified form simpler?"),
  differential rewriting (explain a diff), reproducible
  simplification (save + replay a path).

### Tests
- 11 new cases in `tests/test_path.py`. Full suite: 57 passing.

## [0.1.1] — 2026-04-25 — Counterexample finder

### Added
- `find_counterexample(before, after) -> Counterexample | None`:
  when `verify_equivalence` rejects a rewrite, this returns the
  specific point at which the two sides diverge, both side's
  values, the kind of disagreement (`value_disagreement` or
  `domain_mismatch`), and a one-line note suitable for editor
  surfacing. Pairs with the existing `verify_equivalence` to
  convert "rewrite refused" into actionable feedback.
- `Counterexample` frozen dataclass exporting through the package.

### Tests
- 7 new cases in `tests/test_counterexample.py`. Full suite: 46 passing.

## [0.1.0] — 2026-04-25 — First stable release

**Status.** Stable beta. Patent pending.

### Highlights
- **Domain-gated acceptance** for the three rewrite patterns whose
  algebraic identity requires a positivity or reality assumption
  (`exp_log_inverse`, `log_split`, `log_pow`). The engine probes
  SymPy's assumption system before proposing the rewrite; rewrites
  whose required assumption cannot be established are rejected
  unless `include_conditional=True` is set.
- **Three-layer numerical verification** (cost gate + domain gate +
  numerical-equivalence gate). Sampling respects each free symbol's
  assumption profile; evaluation uses 30-digit precision via SymPy's
  `evalf`; a `simplify` fast-path short-circuits universal identities.
- **Conditional suggestion mode** (`include_conditional=True`) for
  editor / notebook UX — surfaces domain-sensitive rewrites with the
  requirement annotated rather than dropping them silently.
- **9 fusion patterns** in the library: sigmoid canonicalization,
  tanh-from-sinh-cosh, cosh/sinh-from-exps, Pythagorean and
  hyperbolic identities, exp/log inverse pairs, log-split, log-pow.

### Added vs 0.1.0a0
- `DomainRequirement` frozen dataclass; new `Suggestion` fields
  (`domain_required`, `domain_verified`, `numerically_verified`).
- `verify_equivalence(before, after)` public helper.
- `--include-conditional` flag on `scan` and `analyze` subcommands.
- 5 new CLI integration tests (scan, fix, analyze, --include-conditional,
  --help). Full suite: 39 passing.

### Changed
- `eml-cost` dependency pin bumped from `>=0.1.0a0` to `>=0.1.0`.
- `Development Status` classifier promoted from Alpha to Beta.

### Empirical anchor
Validated against three corpora (10,000 random expressions + 100
disguised forms + 50-expression demo catalog). The new domain gate
rejects 21 transformations the legacy structural-only filter would
have accepted; all 21 affect `exp_log_inverse` / `log_pow` on
symbols without a positivity assumption — i.e., rewrites that
would silently produce incorrect results on negative inputs. See
`patent-12/bench_domain_gating.py` in the private research repo.

## [0.1.0a0] — 2026-04-25 — Pre-release skeleton

Initial pre-release. 9 fusion patterns. Cost gate only. Patent
pending.
