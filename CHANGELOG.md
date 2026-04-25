# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project will adhere to [Semantic Versioning](https://semver.org/) once
the public 1.0.0 release ships.

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
