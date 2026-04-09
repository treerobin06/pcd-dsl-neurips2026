# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **最后更新**: 2026-04-09

## 项目概述

基于 Qiu et al., 2026 (Nature Communications) 的 Bayesian Teaching 研究，探索如何提升 LLM 的概率推理能力。项目包含三个独立方向。

## 三个研究方向

| 方向 | 路径 | 状态 | 说明 |
|------|------|------|------|
| **NeurIPS 论文** | `meta-skill/` | 核心进行中 | "Compile Once, Reason Exactly" — DSL + Compiler + Verifier |
| **毕业大论文** | `thesis/` | 写作中 | 全面覆盖所有实验和分析 |
| **依从性研究** | `compliance/` | 独立小发现 | 注入格式对 LLM 依从性的影响 |

**当前核心工作在 `meta-skill/`，详见 `meta-skill/CLAUDE.md`。**

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
cd meta-skill && python3 tests/test_equivalence_full.py  # 1,200 实例等价性

# 需要 LLM API 的测试（通过 OpenRouter）
cd meta-skill && python3 tests/test_inductor_e2e.py
cd meta-skill && python3 tests/test_loo_induction.py
cd meta-skill && python3 tests/test_gate3_ablation.py

# 运行实验
cd meta-skill/baselines && python3 run_pcd_experiment.py --task both --model openai/gpt-4o-mini --n 200
cd meta-skill/baselines && python3 run_pal_experiment.py --task bn --model openai/gpt-4o-mini
cd meta-skill/baselines && python3 run_e2e_experiment.py

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
