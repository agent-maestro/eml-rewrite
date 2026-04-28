# eml-rewrite — DEPRECATED

`eml-rewrite` has been consolidated into `eml-cost` as the
`eml_cost.rewrite` subpackage. The standalone distribution will
receive no further updates.

## Migration

```bash
pip uninstall eml-rewrite
pip install "eml-cost[rewrite]>=0.15.0"
```

Then update your imports:

```python
# OLD
from eml_rewrite import X

# NEW
from eml_cost.rewrite import X
```

## Why?

`eml-cost` now provides the full toolbelt — `cost`, `rewrite`,
`witness`, `explore`, `graph`, and `jupyter` subpackages — under
one install + one version line. See the
[`eml-cost` README](https://github.com/agent-maestro/eml-cost)
for details.

This package version (0.6.0) is a thin shim that re-exports
from `eml_cost.rewrite` and emits a `DeprecationWarning`. Your
existing code keeps working; you just see the migration notice
on import.
