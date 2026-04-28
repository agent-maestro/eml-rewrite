"""Shim sanity test — verify the deprecation re-export works."""
import pytest


def test_shim_imports_with_deprecation_warning():
    with pytest.warns(DeprecationWarning, match="eml-rewrite is deprecated"):
        import eml_rewrite
    assert hasattr(eml_rewrite, "__version__")
    assert eml_rewrite.__version__ == "0.6.0"
