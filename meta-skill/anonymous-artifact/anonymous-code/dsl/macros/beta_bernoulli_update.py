"""Macro manifest: beta_bernoulli_update (多臂赌博机 family)

vision sketch — file-based registry, drop-in extensible.
扫描发现机制见 dsl/macros_library.py。
"""
from dsl.family_macros import beta_bernoulli_update as fn

METADATA = {
    "schema_version": "2026-04-28",
    "name": "beta_bernoulli_update",
    "family_tag": "conjugate_update",
    "op_composition": ["condition", "multiply"],
    "verified_by": "tests/test_dsl.py",
    "description": "Beta-Bernoulli 共轭更新（多臂赌博机后验，closed-form）",
    "added_at": "2026-03-01T00:00:00Z",
    "inducible": True,
}

__all__ = ["fn", "METADATA"]


if __name__ == "__main__":
    print(f"Macro: {METADATA['name']}")
    print(f"Family: {METADATA['family_tag']}")
    print(f"Composition: {METADATA['op_composition']}")
    print(f"Implementation: {fn.__module__}.{fn.__name__}")
