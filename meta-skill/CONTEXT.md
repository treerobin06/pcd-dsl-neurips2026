# Meta-Skill 上下文索引

> **最后更新**: 2026-04-09
> **注意**: 项目的权威状态文档是 `meta-skill/CLAUDE.md`。本文件仅索引资源路径。

本文件索引 meta-skill 开发所需的所有已有资源，避免重复查找。

---

## 已有代码（可直接复用）

| 文件              | 路径                                                | 复用方式                                        |
| --------------- | ------------------------------------------------- | ------------------------------------------- |
| BayesianSidecar | `bayes/bayesclaudecode/bayesian_sidecar.py`       | 迁移为 `solvers/preference_solver.py` 的基础      |
| PromptInjector  | `bayes/bayesclaudecode/prompt_injector.py`        | 迁移为 `runner/injection.py`                   |
| 实验主脚本           | `bayes/bayesclaudecode/run_sidecar_experiment.py` | 迁移为 `runner/universal_runner.py`            |
| 工具函数            | `bayes/bayesclaudecode/utils.py`                  | 拆分到 `script_library/parse.py` 和 `format.py` |
| 测试              | `bayes/bayesclaudecode/test_bayesian_sidecar.py`  | 迁移到 `tests/`                                |

## 已有数据集

| 数据集 | 路径 | 格式 | 状态 |
|---|---|---|---|
| Flight (4 features) | `bayes/data/eval/interaction/flight.jsonl` | JSONL: reward_fn + rounds_numpy | 已完成实验 |
| Flight (2 features) | `bayes/data/eval/interaction/flight_2features.jsonl` | 同上 | 待跑 |
| Flight (3 features) | `bayes/data/eval/interaction/flight_3features.jsonl` | 同上 | 待跑 |
| Hotel | `bayes/data/eval/interaction/hotel.jsonl` | 同 flight（4 features: distance, price, rating, amenities） | 待跑 |
| Webshop | `bayes/data/eval/interaction/webshop/*.jsonl` | 不同格式: goal_attrs + goal_options + score | 暂不使用 |
| Flight (held-out) | `bayes/data/eval/heldout/flight_*.json` | JSON | 参考 |

## 外部数据集（需下载）

| 数据集 | GitHub | 格式 | Solver 类型 |
|---|---|---|---|
| TextBandit | `ChainedTears/TextBandit` | 自定义环境 | Beta-Bernoulli |
| BLInD | `HLR/BLInD` | CSV: contexts + query + answers + graph | BN 精确推断 |
| DeLLMa | `DeLLMa/DeLLMa` | Python + USDA/Yahoo 数据 | 经验概率 + EU |

## 已有实验结果（参考基线）

| 实验 | 关键数据 | 路径 |
|---|---|---|
| 23 策略完整排名 | GPT-4o-mini × 624 样本 | `bayes/bayesclaudecode/sidecar_results/` |
| Baseline 多模型 | 7+ 模型裸跑准确率 | 同上 |
| 27+ 可视化图表 | 各实验的图表 | `sidecar_results/charts/` |
| 逐样本详情 | _details.jsonl 文件 | `sidecar_results/` |

## 项目文档

| 文档 | 路径 | 内容 |
|---|---|---|
| 项目主 CLAUDE.md | `bayes/CLAUDE.md` | 完整项目概述、实验结果、代码结构 |
| 毕设计划 | `文档/毕设小论文_待办事项.md` | 5 个数据集选择、实验设计、论文结构 |
| 数据集调研 | `文档/相关概率推理数据集调研.md` | 9 个相关数据集的详细分析 |
| Phase 2 设计 | `文档/贝叶斯旁路注入-设计文档.md` | BayesianSidecar 架构 |
| COT 实验设计 | `文档/COT补充实验-设计文档.md` | 策略设计思路 |

## 各数据集的数据格式速查

### Flight/Hotel（线性偏好，结构完全一致）
```json
{
  "idx": 0,
  "reward_fn": [-1.0, -1.0, -1.0, -1.0],     // Ground truth 偏好权重
  "features": ["distance_to_downtown", "price", "rating", "amenities"],
  "rounds": [
    {
      "options": ["Hotel 1: distance...", "Hotel 2: ...", "Hotel 3: ..."],
      "user_idx": 2                             // 用户选了第 3 个
    }
    // ... 5 轮
  ],
  "rounds_numpy": [
    [[0.3, 0.5, 0.0, 0.5], [0.3, 0.8, 0.25, 0.75], [0.3, 0.3, 0.0, 0.25]],
    // ... 每轮 3 个选项 × N 个特征的归一化数值
  ]
}
```

### TextBandit（多臂赌博机）
```
环境配置: 2-5 个臂，每臂有固定未知成功概率 (30%-80%)
反馈格式: "Slot Machine X won" / "Slot Machine X lost"
一个 trial: 25 轮选择 + 反馈
评估指标: 最优臂选择率
```

### BLInD（贝叶斯网络查询）
```csv
contexts: "If purple event is False, then grey event is True with probability of 39%..."
query: "What is the probability that grey event is True given that purple event is False?"
answers: 0.39
graph: "('purple event',) -> grey event | () -> purple event"
depth: 2
```

### DeLLMa（不确定性决策）
```
任务: 选择种植哪种水果 / 投资哪只股票
输入: 历史数据（USDA 报告 / Yahoo Finance）+ 可能的未来状态
4 步流程:
  Step 1: 枚举可能状态 (e.g., 干旱/正常/湿润)
  Step 2: 估计状态概率 ← Sidecar 切入点
  Step 3: 估计每个 (动作, 状态) 的效用
  Step 4: argmax EU
数据规模: 120 实例/领域（农业 + 股票）
```

## SOTA 方法速查

| 数据集 | SOTA 方法 | SOTA 结果 | 直接算（baseline） | 提升幅度 |
|---|---|---|---|---|
| Flight | Bayesian Teaching (微调 Gemma 9B) | R5=76% | GPT-4o-mini=37% | +39pp |
| Hotel | Bayesian Teaching (微调 Gemma 9B) | R5=66% | - | - |
| TextBandit | Thompson Sampling | 51.1% | LLM ~31% | +20pp |
| BLInD | LLM→ProbLog→执行 | 97% | GPT-4 直接算 ~7% | +90pp |
| DeLLMa | DeLLMa-Pairs(64) | ~80% | Zero-Shot ~55% | +25pp |
