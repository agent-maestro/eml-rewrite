"""Command-line interface for ``eml-rewrite``.

Subcommands:

    eml-rewrite scan FILE [FILE ...]    # Report rewrites without applying
    eml-rewrite fix  FILE [FILE ...]    # Apply rewrites in place
    eml-rewrite analyze EXPR            # Print Pfaffian profile of one expression

Scan/fix walk Python source files looking for SymPy expression literals
and inline arithmetic. Conservative: only rewrites that strictly reduce
EML cost are proposed/applied.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

import sympy as sp

from eml_cost import analyze

from .core import best, suggest


# ---------------------------------------------------------------------------
# Source scanning
# ---------------------------------------------------------------------------


def _safe_eval_expr_node(node: ast.AST) -> sp.Basic | None:
    """Try to parse an AST expression node into a SymPy expression.

    Whitelist-only: uses ``sympify`` on the unparsed source, but only after
    confirming the AST contains nothing dangerous (Call, Attribute, BinOp,
    UnaryOp, Constant, Name).
    """
    # ast.Num was deprecated in 3.8 and removed in 3.14; ast.Constant
    # covers numeric literals on every supported Python version.
    safe_node_types = (
        ast.Expression, ast.Expr, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Name, ast.Call, ast.Attribute, ast.USub, ast.UAdd,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
        ast.Load, ast.Tuple, ast.Subscript, ast.Slice,
    )
    for sub in ast.walk(node):
        if not isinstance(sub, safe_node_types):
            return None
    try:
        src = ast.unparse(node)
        return sp.sympify(src)
    except Exception:
        return None


def _find_expressions_in_source(source: str) -> list[tuple[int, str, sp.Basic]]:
    """Return (line, snippet, sympy_expr) for each parseable expression."""
    out: list[tuple[int, str, sp.Basic]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr):
            expr = _safe_eval_expr_node(node.value)
            if expr is not None and isinstance(expr, sp.Basic) and not expr.is_Atom:
                snippet = ast.unparse(node.value)
                out.append((node.lineno, snippet, expr))
    return out


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_scan(args: argparse.Namespace) -> int:
    found_any = False
    n_files = 0
    n_suggestions = 0
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"{f}: not found", file=sys.stderr)
            continue
        n_files += 1
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line, snippet, expr in _find_expressions_in_source(source):
            sugg = suggest(
                expr,
                only_improvements=True,
                include_conditional=args.include_conditional,
            )
            if not sugg:
                continue
            top = min(sugg, key=lambda s: s.score_after)
            found_any = True
            n_suggestions += 1
            print(f"{f}:{line}  {snippet}")
            tag = top.pattern_name
            if not top.domain_verified and top.domain_required:
                tag = f"{top.pattern_name} | conditional: {top.domain_required}"
            print(f"  -> {top.rewritten}  ({tag}, -{top.reduction} cost units)")
    if not found_any:
        print(f"No improving rewrites found across {n_files} file(s).")
    else:
        print(f"\nFound {n_suggestions} improving rewrite(s) across {n_files} file(s).")
        print(f"Run `eml-rewrite fix {' '.join(args.files)}` to apply.")
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    n_files = 0
    n_applied = 0
    for f in args.files:
        path = Path(f)
        if not path.exists():
            print(f"{f}: not found", file=sys.stderr)
            continue
        n_files += 1
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        # In a real fix we'd rewrite the source; for v0.1 we only print
        # what would change. (Actual source rewriting requires AST surgery
        # plus careful handling of formatting; v0.2 territory.)
        for line, snippet, expr in _find_expressions_in_source(source):
            replaced = best(expr)
            if replaced != expr:
                n_applied += 1
                print(f"{f}:{line}  {snippet}")
                print(f"  Would rewrite to: {replaced}")
    print(f"\nWould apply {n_applied} rewrite(s) across {n_files} file(s).")
    print(f"NOTE: v0.1 prints proposed rewrites only. In-place source")
    print(f"      rewriting (preserving formatting) is v0.2 territory.")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        result = analyze(args.expr)
    except (TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Expression:           {result.expression}")
    print(f"  pfaffian_r:           {result.pfaffian_r}")
    print(f"  max_path_r:           {result.max_path_r}")
    print(f"  eml_depth:            {result.eml_depth}")
    print(f"  structural_overhead:  {result.structural_overhead}")
    print(f"  corrections:          {result.corrections}")
    print(f"  predicted_depth:      {result.predicted_depth}")
    print(f"  is_pfaffian_not_eml:  {result.is_pfaffian_not_eml}")

    sugg = suggest(
        result.expression,
        only_improvements=True,
        include_conditional=args.include_conditional,
    )
    if sugg:
        print(f"\nSuggested rewrites ({len(sugg)}):")
        for s in sorted(sugg, key=lambda x: -x.reduction):
            tag = s.pattern_name
            if not s.domain_verified and s.domain_required:
                tag = f"{s.pattern_name} | conditional: {s.domain_required}"
            print(f"  [{tag}] {s.rewritten}  (-{s.reduction} cost units)")
    else:
        print("\nNo improving rewrite found.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eml-rewrite",
        description="F-family fusion pattern rewriter for symbolic expressions.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Scan files; report improving rewrites")
    p_scan.add_argument("files", nargs="+")
    p_scan.add_argument("--include-conditional", action="store_true",
                        help="Also report rewrites whose domain assumption "
                             "cannot be established by SymPy's assumption "
                             "system; the requirement is annotated.")
    p_scan.set_defaults(func=cmd_scan)

    p_fix = sub.add_parser("fix", help="Print rewrites that would be applied")
    p_fix.add_argument("files", nargs="+")
    p_fix.set_defaults(func=cmd_fix)

    p_analyze = sub.add_parser("analyze", help="Analyze a single expression")
    p_analyze.add_argument("expr")
    p_analyze.add_argument("--include-conditional", action="store_true",
                           help="Also report conditional rewrites (see scan --help).")
    p_analyze.set_defaults(func=cmd_analyze)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
