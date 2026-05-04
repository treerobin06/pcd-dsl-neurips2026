"""Macro manifest: softmax_pref_likelihood (偏好学习 family)

vision sketch — file-based registry, drop-in extensible.
扫描发现机制见 dsl/macros_library.py。
"""
from dsl.family_macros import softmax_pref_likelihood as fn

METADATA = {
    "schema_version": "2026-04-28",
    "name": "softmax_pref_likelihood",
    "family_tag": "hypothesis_enumeration",
    "op_composition": ["enumerate_hypotheses", "multiply", "normalize"],
    "verified_by": "tests/test_dsl.py + tests/test_equivalence_full.py",
    "description": "Softmax 偏好似然更新（用户从 N 选项选择 → 更新偏好向量后验）",
    "added_at": "2026-03-01T00:00:00Z",
    "inducible": True,
}

__all__ = ["fn", "METADATA"]


if __name__ == "__main__":
    print(f"Macro: {METADATA['name']}")
    print(f"Family: {METADATA['family_tag']}")
    print(f"Composition: {METADATA['op_composition']}")
    print(f"Implementation: {fn.__module__}.{fn.__name__}")
