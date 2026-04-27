"""
DSL Self-evolving Library Registry — VISION SKETCH (2026-04-28)

⚠️ **THIS FILE IS A VISION SKETCH, NOT CONNECTED TO MAIN PIPELINE.** ⚠️

Tree 2026-04-28 决策: self-evolving 是 paper 第 3 根 framing pillar 的
**愿景 / future work**，不是已实现的 feature。本模块**故意不导出**到 dsl/__init__.py，
inductor / compiler / verifier 主流程不依赖它。论文里只在 Figure 1 / Discussion
提一嘴 "the architecture supports persistent macro library evolution"，
不写独立实验或 evaluation Section。

保留本文件用途：
- Paper 可引用 `dsl/macros_library.py` 作为 architecture sketch reference
- 后续真做 self-evolution 实验时（毕业大论文 / 后续 paper），从这个 stub 起步
- 让 reader 理解 "registry interface" 长什么样

设计哲学（vision，非已实现）：
- 7 core ops 是稳定基石（type-checked、verified-correct）
- Family macros 由 core ops 组合而来，每个登记为可复用 unit
- 新 family / op 加入时，registry 持久化进 macros_registry.json
- LLM Inductor 看到 registry → 知道库里有什么可复用 → 不必每次重头组合

两层进化（vision）：
- Family layer: 新 family 解出 + verifier 通过 → 沉淀新 macro → register
- Op layer:    新 op 提出 + 形式化 + verified → 加入 core set
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Any


_HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(_HERE, "macros_registry.json")


@dataclass
class MacroEntry:
    """Family macro 注册项。

    一个 macro 由这些定义：
    - name / family_tag
    - op_composition: 哪些 core ops 组合而来（self-evolving evidence）
    - verified_by: 验证 evidence（test 路径 / paper section / 数值等价证明）
    - added_at: 注册时间 ISO8601 UTC
    """
    name: str
    family_tag: str
    op_composition: List[str]
    verified_by: str
    description: str = ""
    added_at: str = ""
    inducible: bool = True  # LLM Inductor prompt 渲染时是否对外可见

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MacroEntry":
        return cls(**d)


# Bootstrap — 现有 3 个 macro（dsl/family_macros.py 已实现）
_BUILTIN_MACROS: List[MacroEntry] = [
    MacroEntry(
        name="softmax_pref_likelihood",
        family_tag="hypothesis_enumeration",
        op_composition=["enumerate_hypotheses", "multiply", "normalize"],
        verified_by="tests/test_dsl.py + tests/test_equivalence_full.py",
        description="Softmax 偏好似然更新（用户从 N 选项选择 → 更新偏好向量后验）",
        added_at="2026-03-01T00:00:00Z",
        inducible=True,
    ),
    MacroEntry(
        name="beta_bernoulli_update",
        family_tag="conjugate_update",
        op_composition=["condition", "multiply"],
        verified_by="tests/test_dsl.py",
        description="Beta-Bernoulli 共轭更新（多臂赌博机后验，closed-form）",
        added_at="2026-03-01T00:00:00Z",
        inducible=True,
    ),
    MacroEntry(
        name="ve_query",
        family_tag="variable_elimination",
        op_composition=["condition", "multiply", "marginalize", "normalize"],
        verified_by="tests/test_equivalence_full.py + baselines/verify_bnlearn_dsl_100.py",
        description="变量消除查询 P(query | evidence)（贝叶斯网络精确推断）",
        added_at="2026-03-01T00:00:00Z",
        inducible=True,
    ),
]


FAMILY_REGISTRY: Dict[str, MacroEntry] = {m.name: m for m in _BUILTIN_MACROS}


def register_macro(
    name: str,
    fn: Optional[Callable],
    family_tag: str,
    op_composition: List[str],
    verified_by: str,
    description: str = "",
    inducible: bool = True,
    persist: bool = True,
) -> MacroEntry:
    """注册新 family macro 到 registry——self-evolving library 核心入口。

    使用场景：LLM Inductor 解出新 family + Verifier 通过 后，
    沉淀为 macro 调用本接口注册。下次同 family 任务可直接复用。

    Args:
        name: macro 名字（必须 unique）
        fn: 实现 callable（注册时不验证 signature；运行时由 caller 自行 lookup
            到 dsl namespace 调用——callable 本身不写进 JSON）
        family_tag: inference family 标签（hypothesis_enumeration /
            conjugate_update / variable_elimination / 自定义新 tag）
        op_composition: 由哪些 core ops 组合而来（registry 透明性 + Inductor
            prompt 复用提示依据）
        verified_by: 验证 evidence 来源
        description: 一行描述（Inductor prompt 渲染时给 LLM 看）
        inducible: LLM Inductor 看到这个 macro 时是否可推荐
        persist: 是否同步写入 dsl/macros_registry.json

    Returns:
        新登记的 MacroEntry

    Raises:
        ValueError: name 已存在 (避免覆盖已 verified macro)
    """
    if name in FAMILY_REGISTRY:
        raise ValueError(
            f"Macro '{name}' already registered. "
            f"Use unique name or update via separate API (not yet implemented)."
        )

    entry = MacroEntry(
        name=name,
        family_tag=family_tag,
        op_composition=list(op_composition),
        verified_by=verified_by,
        description=description,
        added_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        inducible=inducible,
    )
    FAMILY_REGISTRY[name] = entry

    if persist:
        _save_registry()

    return entry


def list_inducible_macros() -> List[MacroEntry]:
    """LLM Inductor prompt 渲染用的"可推荐"清单"""
    return [m for m in FAMILY_REGISTRY.values() if m.inducible]


def list_by_family(family_tag: str) -> List[MacroEntry]:
    """按 family_tag 查 macros"""
    return [m for m in FAMILY_REGISTRY.values() if m.family_tag == family_tag]


def _save_registry() -> None:
    """持久化 FAMILY_REGISTRY → macros_registry.json"""
    payload = {
        "version": 1,
        "schema_version": "2026-04-28",
        "n_macros": len(FAMILY_REGISTRY),
        "macros": [m.to_dict() for m in FAMILY_REGISTRY.values()],
    }
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _load_registry() -> None:
    """从 macros_registry.json 加载（若文件存在），覆盖 in-memory 状态"""
    global FAMILY_REGISTRY
    if not os.path.exists(REGISTRY_PATH):
        return
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)
    macros = [MacroEntry.from_dict(d) for d in payload.get("macros", [])]
    FAMILY_REGISTRY = {m.name: m for m in macros}


# 模块加载时自动恢复持久化状态
_load_registry()


if __name__ == "__main__":
    print(f"DSL Macros Registry — {len(FAMILY_REGISTRY)} macros")
    print(f"Path: {REGISTRY_PATH}\n")
    for m in FAMILY_REGISTRY.values():
        print(f"  {m.name}")
        print(f"    family_tag    = {m.family_tag}")
        print(f"    op_composition= {m.op_composition}")
        print(f"    verified_by   = {m.verified_by}")
        print(f"    description   = {m.description}")
        print(f"    added_at      = {m.added_at}")
        print(f"    inducible     = {m.inducible}\n")

    if not os.path.exists(REGISTRY_PATH):
        _save_registry()
        print(f"[bootstrap] Wrote initial registry to {REGISTRY_PATH}")
    else:
        print(f"[ok] Registry already persisted at {REGISTRY_PATH}")
