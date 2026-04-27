# Next Session 路线图（2026-04-28+）

**入口**: 接续 PR #1 (`review/2026-04-23-audit-findings`) 在 commit `28be556` 之后。

**总预估**: 6-9 天 / $8-25 API（well below CLAUDE.md $100 阈值）

**当前状态**: Phase B 全部完成 + Phase A 大部分完成 + dsl/core_ops 数学正确性确认。还差 C4 / C2 实验设计修复 + 数字一致性 + Mixed E2E + Phase D 论文重写 + Phase E 终审。

---

## Pre-flight: 接续前必看

1. `cat meta-skill/CLAUDE.md` 第六章——完整 todo + 历史决策
2. `cat meta-skill/paper/audits/2026-04-24-root-cause-retrospective.md`——元根因 + 防御机制
3. `cat meta-skill/paper/audits/2026-04-23-master-plan.md`——原计划 + 12 决策点
4. `cat meta-skill/paper/audits/2026-04-23-codex-review.md`——Codex 3 轮意见
5. `git log --oneline -15`——看已 commit 历史

---

## Task 1 — C4 Gate 3 假独立（🔴 0.5-1 天 / $0.5）

**问题**: `verifier/gates.py` 的 `_gate3_xxx` 用 `compile_solver(spec)` 既当 candidate 又当 reference——self-verification，等于空 gate。

**修法**:
1. Read `verifier/gates.py` `_gate3_bn` / `_gate3_preference` 函数
2. 引入独立 gold:
   - BN: `pgmpy.inference.VariableElimination`（pgmpy 现已修好可用，import `_pgmpy_compat` 即可）
   - Preference: `phase1.bayesian_sidecar.BayesianSidecar`（已知正确）
   - Bandit: 数学等价的独立实现（sidestep 因为 reward 随机性）
3. 写 unit test: 错的 spec 应触发 Gate 3 fail
4. 跑 `tests/test_gate3_ablation.py`（C7 顺便修：加 dump_json 到 baselines/results/）
5. 跑 `tests/test_loo_induction.py` 6 数据集 → 看真实 X/6（不再是 vacuous 6/6）

**关键文件**:
- `verifier/gates.py:280-400` (Gate 3 各 family 的实现)
- `tests/test_loo_induction.py`

**预期结果**: 真实 LOO 数字（可能 4/6 或 5/6 而非 vacuous 6/6）。

**Smoke 先做**: 1 个 LOO 数据集（如 Hotel）跑通 + Gate 3 真验证。OK 后跑全 6 个。

---

## Task 2 — C2 NB/HMM 真用 core ops（🔴 1-1.5 天 / $1）

**问题**: 论文 claim "core ops compose NB/HMM 100%"，但 raw `compile_core_ops=1.0` 来自 LLM 自写代码（codegen），**没真用 dsl/core_ops**。今天确认了 dsl/core_ops 数学正确，必须真用 core ops 跑这两个 family。

**修法**:

1. 写 `solvers/nb_solver.py`:
   ```python
   from dsl.core_ops import condition, multiply, normalize, expectation, argmax, enumerate_hypotheses
   
   class NBCoreSolver:
       """Naive Bayes 用 7 core ops 组合实现"""
       def __init__(self, classes, feature_likelihoods):
           self.classes = classes
           self.feature_likelihoods = feature_likelihoods  # P(feature_i | class)
       
       def predict(self, observed_features):
           # P(class | features) ∝ P(class) × ∏ P(feature_i | class)
           # 实现：
           # 1. 用 enumerate_hypotheses 枚举类
           # 2. 用 multiply 做 conditional prob 累乘
           # 3. 用 normalize 归一化
           # 4. 用 argmax 取 most likely
           ...
   ```

2. 写 `solvers/hmm_solver.py`:
   ```python
   class HMMCoreSolver:
       """HMM Forward filter 用 core ops 迭代"""
       def __init__(self, transition, emission, initial):
           ...
       def forward(self, observations):
           # alpha_t(s) = P(obs_t | s) × sum_{s'} alpha_{t-1}(s') × P(s | s')
           # 用 multiply + marginalize 迭代
           ...
   ```

3. 改 `taskspec/compiler.py`:
   ```python
   if family == "naive_bayes":
       return _compile_nb(spec)  # 新加
   elif family == "hmm_forward":
       return _compile_hmm(spec)  # 新加
   ```

4. 改 `taskspec/schema.py`:
   - `valid_families` 加 `"naive_bayes"` `"hmm_forward"`
   - 加对应 schema 字段（`nb_classes / nb_feature_dim / hmm_n_states / ...`）

5. 改 `inductor/prompts/induction_prompt.md`:
   - 加 4. `naive_bayes` family 描述
   - 加 5. `hmm_forward` family 描述

6. 写 `tests/test_nb_hmm_core_ops.py`:
   - synthetic NB 100 instances → 用 NBCoreSolver 算 → 对比 sklearn naive_bayes gold
   - synthetic HMM 50 sequences → HMMCoreSolver forward → 对比手算 / 库 gold

**预期结果**: NB/HMM 用 core ops 真组合 100%（VE 数学精确）。

**Smoke 先做**: 1 个 NB sample 用 NBCoreSolver 算正确 + 1 个 HMM sample。

---

## Task 3 — S10 PAL 数字统一（🟡 0.2 天 / $0）

**问题**: main.tex 三处 PAL 数字矛盾:
- L442 "PAL drops to 0--3%"
- L994 "GPT-4o-mini PAL 15%"  
- L1011 Table "GPT-4o-mini PAL 17.5%"

**修法**:
```bash
ls -la baselines/results/bnlearn_*.json  # 看 PAL run 文件 + timestamp
# 选最近的 + 最完整的当 canonical
# 比如 bnlearn_openai_gpt-5.4_20260315_211432.json (pal=0.23) + 
#      bnlearn_openai_gpt-4o-mini_20260315_211540.json (pal=0.175)
# 那 canonical mini=17.5%, 5.4=23.3%
# 全文 grep "PAL" 替换数字
```

3 处都改成 canonical 数字 (mini 17.5% / 5.4 23.3%)，删 L442 "0--3%" 那个 outlier 来源。

---

## Task 4 — S5 成本数字统一（🟡 0.2 天 / $0）

**问题**: $0.008 vs $0.001 / 14× vs 60× 两套并存。

**修法**:
- 看 raw 的 token usage（如有）算真实 cost
- 选一套（推荐 $0.008 / 14× 这套——更接近 NeurIPS 报告的 OpenRouter 价格）
- main.tex grep 全文替换
- Appendix Table cost 同步

---

## Task 5 — Mixed E2E（🟢 1 天 / $1-10）

**Tree 核心愿景**：agent 自主识别 family → 编译 → 求解。

### 5.1 写 `baselines/run_mixed_e2e.py` (0.3 天)

```python
"""Mixed E2E benchmark: agent identify family + compile + solve, all unsupervised"""
import os, sys, json, random, asyncio
sys.path.insert(0, ...)
import _pgmpy_compat
import _artifact_schema as art
from inductor.inductor import induce_taskspec
from taskspec.compiler import compile_solver

# 加载 5 family 数据
def load_mixed_dataset(seed=2026):
    samples = []
    # preference: data/eval/interaction/flight.jsonl[:50]
    # BN: data/external/BLInD/Base_1000_examples.csv[:50]
    # bandit: 看 data/external/TextBandit/ 或合成
    # NB: synthetic 50
    # HMM: synthetic 50
    random.Random(seed).shuffle(samples)
    return samples

async def run_one(sample, model_id):
    # 1. Inductor identify family
    spec = induce_taskspec([sample], model_id=model_id, max_samples=1)
    if spec is None: return {"failed": True}
    
    # 2. Compile
    try:
        solver = compile_solver(spec)
    except Exception as e:
        return {"compile_failed": str(e)}
    
    # 3. Solve
    answer = solver.solve(sample)  # 各 family solver 接口
    
    # 4. 对比 gold
    gold = sample["gold_answer"]
    return {
        "family_predicted": spec.inference_family,
        "family_gold": sample["family"],
        "family_correct": spec.inference_family == sample["family"],
        "answer": answer,
        "answer_correct": answer == gold,
    }

async def main(args):
    samples = load_mixed_dataset(args.seed)
    if args.smoke:
        samples = samples[:5]
    
    results = []
    for s in samples:
        r = await run_one(s, args.model)
        results.append(r)
    
    # 统计
    family_acc = sum(r.get("family_correct", False) for r in results) / len(results)
    answer_acc = sum(r.get("answer_correct", False) for r in results) / len(results)
    per_family = ...
    
    art.save_artifact(
        path=f"results/mixed_e2e_{args.model.replace('/','_')}_{timestamp}.json",
        data={
            "family_recognition_rate": family_acc,
            "overall_e2e_accuracy": answer_acc,
            "per_family": per_family,
            "n": len(results),
            "results": results,
        },
        prompt_tokens=...,
        completion_tokens=...,
        model_id=args.model,
    )
```

### 5.2 跑 smoke 5 sample (5min, $0.05)

```bash
.venv/bin/python3 baselines/run_mixed_e2e.py --model openai/gpt-4o-mini --smoke --seed 2026
```

期望: 至少 family 识别 4/5 + 至少 3/5 答案对（保 pipeline 通畅）

### 5.3 跑全量 250 (mini, $0.5)

### 5.4 (可选) 跑 gpt-5.4 对照 250 ($5-12)

---

## Task 6 — Phase D 论文重写（🟣 2-3 天 / $1-3）

按 Phase C 数字落地后：
- Abstract: 把 bnlearn 100% 改写成真数字 + Mixed E2E 主位
- Section 5.x bnlearn: 真 LLM 端到端 + same-model PAL 对比
- **Section 6 新增 Mixed E2E**（headline）
- Section 5.3 LOO: 6/6 → 真 X/6
- Table 3 NB Parse 3% 明示
- Figure 3a 重 generate (从 raw)
- Conclusion 同步真数字
- paper-claim-audit 复审一次

---

## Task 7 — Phase E 终审（🟣 1-1.5 天 / $5-10）

- `/codex-review` 1 轮（gpt-5.4 xhigh）—— 看修后整体评分
- `pdflatex` 编译验证 (≤9 页 main + ref + appendix)
- `citation-verifier` 复审
- Overleaf push
- README + CHANGELOG（投稿透明度）
- git tag + PR merge

---

## 总预算 + Timeline

| Task | 时间 | $ |
|:-:|:-:|:-:|
| 1. C4 Gate 3 | 0.5-1 天 | $0.5 |
| 2. C2 NB/HMM core ops | 1-1.5 天 | $1 |
| 3. S10 PAL 数字 | 0.2 天 | $0 |
| 4. S5 成本统一 | 0.2 天 | $0 |
| 5. Mixed E2E | 1 天 | $1-10 |
| 6. Phase D paper | 2-3 天 | $1-3 |
| 7. Phase E 终审 | 1-1.5 天 | $5-10 |
| **合计** | **6-9 天** | **$8-25** |

均在 CLAUDE.md "$100 告知阈值" 下，无需额外 approval。

---

## 关键 invariants（接续时不能违反）

1. **不要再硬编码** —— 所有 figure 数字从 raw 读
2. **artifact discipline** —— 所有新 raw JSON 经 `_artifact_schema.save_artifact()` 含 token/cost/model_id
3. **disjoint train/test** —— LOO / Inductor 实验必须 disjoint split
4. **scrub 答案** —— 调 Inductor 前必走 `_scrub_sample()`
5. **pgmpy 用 import** —— 任何 import pgmpy 之前 `import _pgmpy_compat`
6. **commit 细粒度** —— 每个 task 一个 commit，message 说明 what/why/test
7. **不开新 PR**——继续在 PR #1 (`review/2026-04-23-audit-findings`) 上推进

---

## 接续时的第一句

> 「按 next-session-plan.md，从 Task 1 (C4 Gate 3) 开始。先 read verifier/gates.py 看当前 Gate 3 实现，然后设计独立 gold 替换。」

或者直接选某项跳过：
- 想优先验 contribution: 从 Task 2 (C2 NB/HMM) 开始
- 想优先 Mixed E2E: 跳到 Task 5

---

**STATUS**: 等待 next session 接续。
