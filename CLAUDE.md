# Bayesian Teaching 研究项目

> **最后更新**: 2026-04-09

基于论文 "Bayesian Teaching Enables Probabilistic Reasoning in Large Language Models" (Qiu et al., 2026, Nature Communications)，研究如何提升 LLM 的概率推理能力。

---

## 项目结构（三个方向）

```
bayes/
├── meta-skill/          ← 【方向 1】NeurIPS 论文 "Compile Once, Reason Exactly"
│   ├── CLAUDE.md        ← ★ 这个方向的权威文档
│   ├── dsl/             # 概率 DSL（7 core ops + 3 macros）
│   ├── taskspec/        # TaskSpec IR + 确定性编译器
│   ├── inductor/        # LLM 归纳器
│   ├── verifier/        # 3-Gate 验证器
│   ├── solvers/         # Gold reference solvers
│   ├── baselines/       # PCD/PAL/Compile-time/E2E 实验
│   ├── tests/           # 测试套件
│   └── paper/           # NeurIPS 论文 (main.tex + Overleaf 同步)
│
├── phase1/              ← 【方向 1 的证据基础】23 策略旁路注入消融实验
│   ├── bayesian_sidecar.py    # 纯算法贝叶斯推理引擎
│   ├── prompt_injector.py     # 18 种注入策略
│   ├── run_sidecar_experiment.py  # 实验主脚本
│   └── sidecar_results/       # 170+ 实验结果文件
│
├── thesis/              ← 【方向 2】毕业大论文（全面，含所有历史）
│
├── compliance/          ← 【方向 3】LLM 依从性/注入格式研究（小发现）
│
├── data/                # 共享数据
│   ├── eval/interaction/    # flight.jsonl (624), hotel.jsonl (124)
│   ├── train/               # 训练数据
│   └── external/            # 外部数据集
│       ├── BLInD/           # BN 推断 900 题
│       ├── TextBandit/      # 多臂赌博机
│       └── DeLLMa/          # 农业决策（边界测试）
│
├── docs/                # 文档归档
│   ├── phase1-reports/      # Phase 1 实验报告（Obsidian 笔记）
│   ├── defense/             # 中期答辩
│   └── references/          # 引用论文
│
└── archive/             # 不再活跃的内容
    ├── server-experiments/  # 远程服务器实验
    └── early-scripts/       # 最早期的实验脚本
```

---

## 快速导航

| 你要做什么 | 去哪里 |
|-----------|--------|
| 了解 NeurIPS 论文的最新状态 | `meta-skill/CLAUDE.md` |
| 看 Phase 1 的 23 策略实验数据 | `phase1/sidecar_results/` |
| 运行 DSL 测试 | `cd meta-skill && python3 -m pytest tests/ -v` |
| 运行 PCD 诊断实验 | `cd meta-skill/baselines && python3 run_pcd_experiment.py` |
| 同步论文到 Overleaf | `cd meta-skill/paper && bash sync_overleaf.sh push` |
| 查看依从性研究 | `compliance/` |

---

## 编码规范

- 注释语言：中文
- 用 `python3` 不用 `python`
- 并发优先：asyncio + AsyncOpenAI
- API 统一走 OpenRouter
- 每个功能点完成后 git commit

## 飞书文档

- **文档 ID**: `AcOIdoE0Gop4mexsificXAWbnNg`
- **文件夹 Token**: `Y59JfVFEClsLKqdXViOcA3h6n0d`
