"""Macro manifest: ve_query (BN variable elimination family)

vision sketch — file-based registry, drop-in extensible.
扫描发现机制见 dsl/macros_library.py。
"""
from dsl.family_macros import ve_query as fn

METADATA = {
    "schema_version": "2026-04-28",
    "name": "ve_query",
    "family_tag": "variable_elimination",
    "op_composition": ["condition", "multiply", "marginalize", "normalize"],
    "verified_by": "tests/test_equivalence_full.py + baselines/verify_bnlearn_dsl_100.py",
    "description": "变量消除查询 P(query | evidence)（贝叶斯网络精确推断）",
    "added_at": "2026-03-01T00:00:00Z",
    "inducible": True,
}

__all__ = ["fn", "METADATA"]


if __name__ == "__main__":
    print(f"Macro: {METADATA['name']}")
    print(f"Family: {METADATA['family_tag']}")
    print(f"Composition: {METADATA['op_composition']}")
    print(f"Implementation: {fn.__module__}.{fn.__name__}")
