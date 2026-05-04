"""DSL macro registry extension hooks.

This optional module sketches a file-based macro registry for future extensions.
It is not imported by the main DSL package and is not required by the inductor,
compiler, verifier, or the reported experiments.

Each macro can live in ``dsl/macros/<name>.py`` with a constant ``METADATA``
dictionary and a callable ``fn`` implementation. At load time, this module scans
that directory and registers available macro manifests.
"""

import os
import glob
import time
import importlib
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional, Any


_HERE = os.path.dirname(os.path.abspath(__file__))
MACROS_DIR = os.path.join(_HERE, "macros")
_PACKAGE = "dsl.macros"


@dataclass
class MacroEntry:
    """Family macro 注册项 — 对应 dsl/macros/<name>.py 一个文件。

    fn 是运行时 callable（不进 to_dict 序列化），其余字段来自 manifest 文件
    的 METADATA dict。
    """
    name: str
    family_tag: str
    op_composition: List[str]
    verified_by: str
    description: str = ""
    added_at: str = ""
    inducible: bool = True
    schema_version: str = "2026-04-28"
    fn: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("fn", None)  # callable 不可序列化
        return d


# In-memory registry (loaded via _scan_registry on import)
FAMILY_REGISTRY: Dict[str, MacroEntry] = {}


def _scan_registry() -> None:
    """启动时扫描 dsl/macros/*.py → importlib → 读 METADATA + fn → 注册"""
    global FAMILY_REGISTRY
    if not os.path.isdir(MACROS_DIR):
        return

    pattern = os.path.join(MACROS_DIR, "*.py")
    for path in sorted(glob.glob(pattern)):
        fname = os.path.basename(path)
        if fname.startswith("_"):  # 跳过 __init__.py 等
            continue
        module_name = fname[:-3]  # strip .py
        full_module = f"{_PACKAGE}.{module_name}"

        try:
            mod = importlib.import_module(full_module)
        except Exception as e:
            print(f"[macros_library] Warning: failed to import {full_module}: {e}")
            continue

        meta = getattr(mod, "METADATA", None)
        fn = getattr(mod, "fn", None)
        if meta is None or fn is None:
            print(f"[macros_library] Skipping {full_module}: missing METADATA or fn")
            continue

        # 容忍 manifest 多余字段（向前兼容 schema 演化）
        known = {f for f in MacroEntry.__dataclass_fields__}
        entry_kwargs = {k: v for k, v in meta.items() if k in known}
        entry = MacroEntry(fn=fn, **entry_kwargs)
        FAMILY_REGISTRY[entry.name] = entry


def list_inducible_macros() -> List[MacroEntry]:
    """LLM Inductor prompt 渲染用的"可推荐"清单"""
    return [m for m in FAMILY_REGISTRY.values() if m.inducible]


def list_by_family(family_tag: str) -> List[MacroEntry]:
    """按 family_tag 查 macros"""
    return [m for m in FAMILY_REGISTRY.values() if m.family_tag == family_tag]


def register_macro_file(
    name: str,
    family_tag: str,
    op_composition: List[str],
    verified_by: str,
    description: str = "",
    inducible: bool = True,
    implementation_import: str = "",
) -> str:
    """生成 dsl/macros/<name>.py 文件骨架——self-evolving 入口（future work）。

    使用场景：LLM Inductor 解出新 family + Verifier 通过后，调用本接口
    生成新的 macro manifest 文件。若 implementation_import 提供（如
    "dsl.family_macros.foo"），fn 重导出已有函数；否则生成 NotImplementedError
    stub 等待手填。

    Args:
        name: macro 唯一 id（对应 .py 文件名，必须为 valid Python identifier）
        family_tag: inference family 标签
        op_composition: 由哪些 core ops 组合
        verified_by: 验证 evidence 来源
        description: 一行描述（Inductor prompt 渲染用）
        inducible: LLM Inductor 是否可见此 macro
        implementation_import: 已有 fn 的 dotted path（如
            "dsl.family_macros.softmax_pref_likelihood"）

    Returns:
        生成的文件路径

    Raises:
        ValueError: 文件已存在
    """
    if not os.path.isdir(MACROS_DIR):
        os.makedirs(MACROS_DIR)

    target = os.path.join(MACROS_DIR, f"{name}.py")
    if os.path.exists(target):
        raise ValueError(f"Macro file '{target}' already exists.")

    if implementation_import:
        mod, fn_name = implementation_import.rsplit(".", 1)
        impl_block = f"from {mod} import {fn_name} as fn"
    else:
        impl_block = (
            "# Implement fn using the typed core operations before registering this macro.\n"
            "from dsl.core_ops import (\n"
            "    condition, multiply, marginalize, normalize,\n"
            "    enumerate_hypotheses, expectation, argmax,\n"
            ")\n\n"
            "def fn(*args, **kwargs):\n"
            f"    raise NotImplementedError('Macro {name!r} fn not yet implemented.')"
        )

    added_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    content = f'''"""Macro manifest: {name} (auto-generated)"""
{impl_block}

METADATA = {{
    "schema_version": "2026-04-28",
    "name": "{name}",
    "family_tag": "{family_tag}",
    "op_composition": {op_composition!r},
    "verified_by": "{verified_by}",
    "description": "{description}",
    "added_at": "{added_at}",
    "inducible": {inducible},
}}

__all__ = ["fn", "METADATA"]
'''
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return target


# 启动时扫描
_scan_registry()


if __name__ == "__main__":
    print(f"DSL Macros Registry — {len(FAMILY_REGISTRY)} manifests in {MACROS_DIR}\n")
    for m in FAMILY_REGISTRY.values():
        impl = f"{m.fn.__module__}.{m.fn.__name__}" if m.fn else "(none)"
        print(f"  {m.name}")
        print(f"    family_tag    = {m.family_tag}")
        print(f"    op_composition= {m.op_composition}")
        print(f"    verified_by   = {m.verified_by}")
        print(f"    description   = {m.description}")
        print(f"    fn            = {impl}")
        print(f"    added_at      = {m.added_at}")
        print(f"    inducible     = {m.inducible}\n")

    print("[ok] Scanned dsl/macros/ — Python module per file registry loaded.")
    print("To add a macro: drop a .py file in dsl/macros/ following the schema.")
