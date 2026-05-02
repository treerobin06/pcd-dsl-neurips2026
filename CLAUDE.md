# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **最后更新**: 2026-05-02

## 项目概述

基于 Qiu et al., 2026 (Nature Communications) 的 Bayesian Teaching 研究，探索如何提升 LLM 的概率推理能力。项目包含三个独立方向。

## 三个研究方向

| 方向 | 路径 | 状态 | 说明 |
|------|------|------|------|
| **NeurIPS 论文** | `meta-skill/` | 投稿收口中 | "Compile Once, Reason Exactly" — DSL + Compiler + Verifier；E2E 主实验已补，剩一致性审查/图表/最终编译 |
| **毕业大论文** | `thesis/` | 写作中 | 全面覆盖所有实验和分析 |
| **依从性研究** | `compliance/` | 独立小发现 | 注入格式对 LLM 依从性的影响 |

**当前核心工作在 `meta-skill/`，详见 `meta-skill/CLAUDE.md`。**

## 2026-05-02 当前 NeurIPS 状态

- `meta-skill/` 仍是当前唯一核心工作区。
- 已完成官方 NeurIPS 2026 模板更新：`neurips_2026.sty`、`neurips_2026.tex`、`checklist.tex`，并已推送到 Overleaf。
- 已完成单 family E2E 补实验：Flight、Hotel、TextBandit-style。
- 已完成全 family mixed E2E 全量：GPT-4o-mini，650 条。Raw mixed runner 为 Overall 598/650 = **92.0%**，Supported 548/600 = **91.3%**，Router 650/650 = **100.0%**；论文主表已删除全 100 的 Route acc. 列，并用 NB/HMM adversarial NL harder split 原始计数对齐（NB 110/120，HMM 98/100），保守 aggregate 改报 Overall 606/670 = **90.4%**，Supported 556/620 = **89.7%**。旧的 90/90=100 和 open-set 50/50=100 只作废弃 sanity，不进论文主叙事。
- `tests/test_compiler.py::test_roundtrip` schema bug 已修复，`python3 -m unittest tests.test_compiler -v` 当前 13/13 OK。
- 论文已补 E2E raw artifact provenance appendix，TaskSpec schema appendix 已加入 NB/HMM 字段，PAL/bnlearn 主文措辞已改为具体网络结果；Figure 1 已替换为 Imagen 架构图（router/scope gate + compile-once backend + reusable solver registry）；mixed 主表已删除 Route acc. 列并改报保守 aggregate 90.4% / 89.7%；verifier / composition / theory / LOO wording 已降调。
- Method 中 theorem-like 的 inductor/verifier/risk 公式已删除，改为 prose + Algorithm；保留 PCD metrics + DSL/op definitions 作为诊断和接口锚点。本地 `latexmk -g -pdf` 编译通过，`main.pdf` 30 页，无 undefined citation/reference/overfull；已推送到 Overleaf commit `8a2f917 Sync from local 2026-05-02 23:26`。最后还需 paper-claim-audit / citation audit / post-audit final clean compile / Overleaf push。
- 2026-05-02 全文审查后，bnlearn 的 Our DSL 100% 已从论文主证据链撤掉：Figure 3a 和 Appendix bnlearn 表只保留 PAL/Compute stress test；backend exactness 主 claim 限定为 Flight/BLInD 1,150 finite reference check。`verify_bnlearn_dsl_100.py` 已加参数和 invalid-gold skip，但 30q 验证在 Insurance 上过慢，未写进论文主结果。

## 目录结构

```
bayes/
├── meta-skill/              # NeurIPS 论文 + DSL 系统（有独立 CLAUDE.md）
├── phase1/                  # Phase 1 旁路注入消融实验（23 策略 × 624 样本）
├── thesis/                  # 毕业大论文
├── compliance/              # LLM 依从性研究
├── data/                    # 共享数据
│   ├── eval/interaction/    #   flight.jsonl (624), hotel.jsonl (124)
│   └── external/            #   BLInD/, TextBandit/, DeLLMa/
├── docs/                    # 文档归档
│   ├── phase1-reports/      #   Phase 1 实验报告（Obsidian 笔记）
│   ├── defense/             #   中期答辩
│   └── references/          #   引用论文
└── archive/                 # 不再活跃的内容
```

## 常用命令

```bash
# 本地测试（不需要 API，不需要 pytest——直接用 unittest）
cd meta-skill && python3 tests/test_dsl.py          # DSL 25 tests
cd meta-skill && python3 tests/test_compiler.py      # Compiler 13 tests
cd meta-skill && python3 tests/test_equivalence_full.py  # 1,150 实例等价性

# 需要 LLM API 的测试（通过 OpenRouter）
cd meta-skill && python3 tests/test_inductor_e2e.py
cd meta-skill && python3 tests/test_loo_induction.py

# 运行实验
cd meta-skill/baselines && python3 run_pcd_experiment.py --task both --model openai/gpt-4o-mini --n 200
cd meta-skill/baselines && python3 run_pal_experiment.py --task bn --model openai/gpt-4o-mini
cd meta-skill/baselines && python3 run_e2e_experiment.py
cd meta-skill && .venv/bin/python3 baselines/run_all_family_mixed_e2e.py --n-per-family 100 --n-unsupported 50 --concurrency 10 --model openai/gpt-4o-mini

# Overleaf 同步
cd meta-skill/paper && bash sync_overleaf.sh pull   # 拉取
cd meta-skill/paper && bash sync_overleaf.sh push   # 推送

# Phase 1 实验（旁路注入）
cd phase1 && python3 run_sidecar_experiment.py -m openai/gpt-4o-mini --strategies all --per-model 80
```

## 编码规范

- 注释语言：中文
- 用 `python3` 不用 `python`（macOS 没有 `python` 命令）
- 并发优先：asyncio + AsyncOpenAI
- API 统一走 OpenRouter（环境变量 `OPENROUTER_API_KEY`）
- 每个功能点完成后 git commit

## 关键依赖

- Python 3, numpy, httpx, openai (AsyncOpenAI), matplotlib
- 没有安装 pytest（测试文件使用 unittest，直接 `python3 tests/test_*.py` 运行）
- LaTeX 编译需要 pdflatex + bibtex

## 飞书文档

- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`
