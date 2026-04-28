# DSL Macros — Self-evolving Library (Vision Sketch)

⚠️ **VISION SKETCH** — 未连接主流程。详见 [`../macros_library.py`](../macros_library.py)。

## 设计哲学

启发自 Claude `skill-creator` 的 file-based registry 架构 + Python module per file 设计：

- 每个 macro 是 **drop-in Python module**（`dsl/macros/<name>.py`）
- 模块顶部 `METADATA` dict（常量）+ `fn` callable
- 加新 macro = 扔一个 `.py` 进本目录，**无需改 macros_library.py / __init__.py**
- `dsl.macros_library._scan_registry()` 启动时 importlib 扫描加载

这是 paper framing pillar 3（self-evolving library）的具象化骨架。
真正跑 self-evolution 实验是 future work（毕业大论文 / 后续 paper）。

## 加新 macro 流程

1. 在本目录新建 `<name>.py`
2. 模块结构：
   ```python
   """Macro manifest: <name> (...)"""
   from dsl.family_macros import your_function as fn  # 或自己定义 fn
   
   METADATA = {
       "schema_version": "2026-04-28",
       "name": "<name>",
       "family_tag": "<family>",
       "op_composition": [...],
       "verified_by": "<test path>",
       "description": "...",
       "added_at": "<ISO 8601>",
       "inducible": True,
   }
   __all__ = ["fn", "METADATA"]
   ```
3. 启动时自动扫描发现，无需改其他代码

可以用 `dsl.macros_library.register_macro_file(...)` 接口自动生成模板。

## METADATA Schema

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 当前 `"2026-04-28"` |
| `name` | string | macro 唯一 id（应与文件名一致） |
| `family_tag` | string | inference family 标签 |
| `op_composition` | list[string] | 由哪些 7 core ops 组合 |
| `verified_by` | string | 验证 evidence（test path / paper section） |
| `description` | string | 一行描述（Inductor prompt 渲染时给 LLM 看） |
| `added_at` | string | ISO-8601 UTC 时间戳 |
| `inducible` | bool | LLM Inductor 推荐时是否可见 |

`fn` callable 由 Python module 直接提供，不需要 dotted-path string。

## 当前 manifests (3)

- [`softmax_pref_likelihood.py`](softmax_pref_likelihood.py) — 偏好学习（hypothesis_enumeration）
- [`beta_bernoulli_update.py`](beta_bernoulli_update.py) — 多臂赌博机（conjugate_update）
- [`ve_query.py`](ve_query.py) — BN 变量消除（variable_elimination）

## Self-evolving 路径（vision · future work）

```
1. 用户给新任务 → LLM Inductor 看 registry → 决定 reuse 已有 macro 或 compose 新组合
2. 若 compose → 用 7 core ops 写 spec → 2-Gate Verifier 通过
3. register_macro_file() 沉淀为新 .py 文件 drop in 本目录
4. 第二次同 family 任务 → registry hit → 直接 reuse macro，零 LLM compose 成本
```

详见 paper Discussion section + `../macros_library.py` `register_macro_file()` 接口。

## 与 Claude skill-creator 的对比

| 维度 | Claude skill-creator | DSL macros |
|---|---|---|
| 元数据格式 | Markdown frontmatter (YAML) | Python `METADATA` dict |
| 实现位置 | 同 skill 目录或 plugin | 同 .py 文件 (`fn` callable) |
| 注册机制 | plugin marketplace + `~/.claude/skills/` | drop-in `dsl/macros/<name>.py` |
| 调用方式 | LLM 决定 invoke skill | LLM Inductor 决定 reuse macro |
| 可发现性 | 启动时扫描 + 描述渲染进 prompt | 启动时 importlib + 描述渲染进 Inductor prompt |
| 类型安全 | Markdown is string | Python const + IDE 补全 |

核心相同：**file-based, drop-in extensible registry, no central code changes for new entries**。

DSL macros 选择 Python module 而非 JSON/Markdown，理由：metadata + 实现同处、
IDE 类型安全、可加 docstring/examples/自测、fn 直接是 callable 不需要 dotted-path resolve。
