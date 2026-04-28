# Root-Cause Retrospective — 为什么之前论文错了

**日期**: 2026-04-24
**作者**: Claude Opus 4.7（应 Tree 要求"自己分析为什么之前错了 是不是代码有问题"）
**审查 verdict**: Codex 3 轮独立审查 5/10 → 4.5/10 → 4/10；4 agent 交叉印证
**对应 todo**: meta-skill/CLAUDE.md 第六章 C1-C9 + S1-S12
**关联**: [2026-04-23-master-plan.md](2026-04-23-master-plan.md), [2026-04-23-codex-review.md](2026-04-23-codex-review.md), [2026-04-23-experiment-audit.md](2026-04-23-experiment-audit.md)

---

## TL;DR

之前论文有 **8 类问题**：
- **3 类是真代码 bug**（C1 multiply_factors / dsl_p=gold_p fallback / C5 prompt 喂答案 / C6 LOO 同样本两用 / S2 Gate 2 总 pass）
- **1 类是设计问题**（C3 BN compile 实为路由，不是 compile）
- **2 类是叙事/选择性展示**（C2 NB Parse=3% 被 Abstract 说成 ≥95% / S10 bnlearn 数字多套混用）
- **1 类是工程基础设施缺失**（C9 figure 硬编码 + 无 token trace）
- **1 类是数字不精确**（C8 1,200 vs 实际 1,150）

**核心元根因**（Codex 金句）："**claim-first, artifact-later 工作模式**——先决定要 claim 什么再写 figure，不去 raw 验证"。这个模式让所有 8 类问题都没在内部审查中浮现。

---

## 1. 每个问题的精确 root cause

### C1 bnlearn 100% — 双重 bug + 叙事冒用

**直接代码 bug**:
- `baselines/verify_bnlearn_dsl_100.py:95-117` 含 `dsl_p = gold_p` fallback——多值节点分支自动 100%
- 同文件传 `query_vars = {var: [list]}` 给 `ve_query`，但 `ve_query` 期望 `{var: single_value}` → always returns `0.0` → fallback 每次都吞错
- `paper/scripts/generate_figure3a_bnlearn.py:33` 硬编码 `our_dsl=[100,100,100,100]`

**叙事冒用**:
- LLM 端到端实验 `baselines/results/bnlearn_*.json` 真实结果 `compile_core_ops=0% failed=true`
- 论文 figure 把 `verify_bnlearn_dsl_100.py` 的假 100% 当 LLM agent 端到端表现展示

**why not caught**:
1. ❌ 测试只 print "100%" 没人 grep `dsl_p = gold_p` 看是不是 fallback
2. ❌ figure 数字没和 raw JSON 对账（`raw compile_core_ops=0` 但 figure 写 100% 应该警报）
3. ❌ 两个脚本同名前缀但语义完全不同（一个走 LLM 一个绕过），没文档区分

### C1' multiply_factors 空壳 — prompt 里的代码 bug

**直接代码 bug**:
- `baselines/run_bnlearn_held_out.py:281-293` 的 core_ops_section prompt 给 LLM 看的 `multiply_factors`：
  - `mul2` 循环体只有 `pass`
  - `multiply_factors` 没调用 `mul2` 也没 `reduce`
  - 整个函数返回 `{}`

**why not caught**:
1. ❌ prompt 是 string literal，没静态分析
2. ❌ raw JSON 里 `compile_core_ops=0%, failed=true` 已经在了，但论文用的不是这个数字（论文用假 100%）
3. ❌ 没人对比 prompt 给 LLM 的 helper code 的数学正确性

### C2 NB Parse=3% 被 Abstract 说成 ≥95%

**性质**: 不是代码 bug，是叙事/选择性展示

**Raw 实锤**:
- `held_out_nb_openai_gpt-4o-mini_205problems.json`: `parse_accuracy=0.03`
- `held_out_nb_openai_gpt-5.4_205problems.json`: 同低
- 但 Abstract 写 "Parse ≥95%"

**why not caught**:
1. ❌ Parse 用了**滑动定义**——preference 任务的"all-fields-match"是宽松的(82-100%)，NB 的 exact-match 是严格的(3%)
2. ❌ 论文同时引用两种 Parse metric 但没明确区分口径
3. ❌ Table 3 里就有 NB Parse=3% cell，但 Abstract 反复说 ≥95%——内部矛盾自己没人查
4. ❌ paper-claim-audit 跑前没人对账 raw 里 Parse 真实数字

### C3 BN compile 实为路由 — 设计问题

**直接设计问题**:
- `taskspec/compiler.py:68-70`: BN 分支直接 `return BNReferenceSolver()`
- "compiler" 这个名字暗示编译，但 BN 没真 compile，spec 内容没参与

**性质**: 论文叙事是 "compile-once → verified solver"——给定 TaskSpec 编译出 solver。但 BN 分支实际是 family routing（识别是 BN 就用手写 solver），不是 spec→code 编译

**why not caught**:
1. ❌ "compiler" 名字误导
2. ❌ 没 unit test 验证 compiler output 真的依赖于 spec 内容（如果 spec 变了 compiler output 应该变）
3. ❌ BN family 用得最多，"100% compute" 数字最好——挡住了"实际没编译"的真相

### C5 Inductor prompt 喂答案

**直接代码 bug**:
- `inductor/inductor.py:35` 用 `json.dumps(sample)` 把整个 sample dict 喂给 LLM
- sample 含 `reward_fn`（答案空间）/ `answers`（对应答案）/ `correct_diagnosis`（BN 正确预测）
- `inductor/prompts/induction_prompt.md:17` 还**显式要求 LLM 看 `reward_fn`**

**after**: LLM 看到答案直接 copy → produce "正确" TaskSpec → LOO/E2E/Inductor reliability 数字虚高

**why not caught**:
1. ❌ prompt 是动态构造的，没人 print 出来检查
2. ❌ LOO/E2E "成功"被**空 Gate 2** 接住（C5 + S2 互相掩护）
3. ❌ 没 sanity test "scrub 答案后 LLM 能否 produce reasonable TaskSpec"

### C6 LOO `samples[:k]` 两用 — 测试设计错误

**直接代码 bug**:
- `tests/test_loo_induction.py:79-80`: `induction_samples = samples[:max_induction_samples]`
- 然后 verify 时**也用同样的 samples** 而不是 `samples[max_induction_samples:]`
- 违反论文 L371-395 声称的 "held-out validation"

**why not caught**:
1. ❌ "held-out" 这词在论文里被强调，但代码实现不匹配
2. ❌ 没独立测试覆盖 train/test split disjointness
3. ❌ `samples[:k]` 是 Python 直觉写法，但忘了写 `samples[k:]` 那一半

### S2 Gate 2 `passed = True` — verifier 失效

**直接代码 bug**:
- `verifier/gates.py:195-200`: preference 类 Gate 2 直接 `passed = True`，没真验证

**after**: "Gate 2 通过率 100%" 看起来很好，实际是空 gate。LOO 6/6 / Reliability 40/40 等数字都是"代码没崩就过"

**why not caught**:
1. ❌ "Gate 2 通过率 100%" 被当 method 太强，没人怀疑是 vacuous gate
2. ❌ 没单元测试 "Gate 2 应该 fail 哪些 case"
3. ❌ verifier 设计上"宽容失败"——倾向通过，反向激励

### S10 bnlearn 数字多套混用

**性质**: 论文 prose 跨段引用不同 run 的数字
- L442 说 "PAL drops to 0-3%"
- L994 说 "GPT-4o-mini PAL 15%"
- L1011 Table 说 "GPT-4o-mini PAL 17.5%"
- raw 实际 17.5% / 23.3%

**why not caught**:
1. ❌ 多次重跑产生不同 raw JSON 都留在 `baselines/results/`
2. ❌ 论文没维护"哪个 raw 是 canonical"
3. ❌ 跨段引用没对账（写 Section 5.2 时引一个，写 Appendix 时引另一个）

### C8 TextBandit 50 不存在

**性质**: 数字不精确（不是 fraud）
- `tests/test_equivalence_full.py` 实际只有 BLInD 900 + Flight (50 samples × ~5 rounds = 250 比对)
- TextBandit 50 这个 split 在 test 里不存在
- 论文 L339 + L765 + L117 都写 "1,200" 实际 1,150

**why not caught**:
1. ❌ "1,200" 是 round number，没人逐项 add up
2. ❌ TextBandit 在论文中被多处提及（"third inference family"），但 equivalence test 里没实现
3. ❌ paper-claim-audit 类全文核账没在投稿前跑

### C9 artifact discipline 缺失

**性质**: 工程基础设施缺失
- 全仓 `rg prompt_tokens / completion_tokens / total_cost / model_id` 命中数 ≈ 0
- figure 脚本可以硬编码
- 没 raw schema 强制

**after**: 所有"成本 $0.008/14× vs $0.001/60×"类 claim 都没 token trace 支撑——只能改 prose 不能验证

---

## 2. 元层面的根因（meta-level）

### 根因 A: Claim-first, artifact-later

**Codex 元反思**: "claim-first, artifact-later 工作方式是核心病根"

实际工作流（不健康）:
```
1. 想要 claim "DSL bnlearn 100%"
2. 写 verify_bnlearn_dsl_100.py 跑出 100%
3. figure 写 100%
4. paper Section 5.4 写 "100%"
5. ... 投稿前才用 paper-claim-audit 发现 raw 实际 0%
```

健康工作流:
```
1. 写 raw JSON (含 token/cost/model_id 强制 schema)
2. 跑 raw → 看真实数字
3. figure 从 raw 读
4. paper claim 引用 figure → 自然只能写真数字
```

### 根因 B: 测试只看 returncode 不看数据流

Tree 在 feedback memory 里有这条："测试必须端到端验证完整数据流，不能只看返回码"

具体例子：
- `test_loo_induction.py` 跑通就过——但没人验证"输入 inductor 的样本 vs verify 的样本是否独立"
- `verify_bnlearn_dsl_100.py` 输出 "100%" 就过——但没人验证"100% 是 fallback 出来的还是真算的"

### 根因 C: Confirmation bias

"100% 太好了"在多个位置都出现，但内部审查没人触发警报。
- 4 family compile_core_ops 100%
- LOO 6/6
- Reliability 40/40
- Equivalence 1,200/1,200 max_err=0
- bnlearn 100% × 4 networks

健康版本应该是："100% 太干净了 → 必须是 fallback / 测试设计问题"。

### 根因 D: 外审晚于论文写作

paper-claim-audit / Codex review 类外部审查应该在**写 Abstract 前**做，不是投稿前。这次 4 agent + Codex 是投稿前 1 天才跑——发现的所有问题，如果在 6 个月前（写 Abstract 阶段）跑就能被截住。

### 根因 E: prompt 是字符串没 lint

`run_bnlearn_held_out.py:281-293` 的 multiply_factors 是 string literal——Python AST 不会检查它的语义正确性。

LLM 拿到这个 prompt → 写出基于空壳 multiply 的 solver → solver 全部失败 → "我们 method 在 bnlearn 上 0%"。

应该有一个 prompt 静态分析器（或者人工 review）把 string literal 里的代码片段当真代码 lint。

---

## 3. 怎么防止再发生（机制层）

| # | 机制 | 实现 |
|:-:|---|---|
| **1** | **artifact discipline 硬门槛**（C9）| 所有 raw JSON 必须含 `prompt_tokens / completion_tokens / total_cost / model_id`；figure 脚本禁止硬编码值，只能从 raw 读 |
| **2** | **prompt scrub 强制**（防 C5）| Inductor 调用前必走 `scrub_sample()` 函数，移除 `reward_fn / answers / correct_diagnosis / correct_*`；写单元测试覆盖 scrub 完整性 |
| **3** | **train/test split disjointness**（防 C6）| `split()` 函数显式返回 `(train, test)` 两个**不重叠** index 集合；test 用 `assert set(train) & set(test) == set()` |
| **4** | **real Gate 2 implementation**（防 S2）| Gate 2 必须有真阈值（preference 类 ≥ 70% accuracy on train queries 才 pass）；写测试覆盖"明显错的 solver Gate 2 应该 fail" |
| **5** | **paper-claim-audit on every commit**（防 S10/C8）| Pre-commit hook：扫 main.tex 所有数字，对比 raw JSON；不一致警告 |
| **6** | **prompt static analysis**（防 multiply_factors 类）| 把 prompt 里的 code block 提取出来跑 `python3 -c` 验证语义正确性；core ops 写成可导入的 module 而不是 prompt 内联 |
| **7** | **"100% 太干净了" trigger**（confirmation bias 防御）| Pre-commit hook：发现 ≥3 个连续 100% 自动 flag 让人审查 |
| **8** | **CI pipeline raw-vs-paper 对账**（防 claim-first）| GitHub Action：每次 commit 检查 main.tex 引用的所有数字是否在 baselines/results/*.json 里有对应 raw |

---

## 4. 当前 Phase B 必修项（按本诊断）

按 Tree 决定 C3 = B（真重构），后续工作:

| 优先级 | 任务 | 涉及代码 | 工作量 |
|:-:|---|---|:-:|
| **P0** | C5 Inductor scrub | `inductor/inductor.py:35` + `inductor/prompts/induction_prompt.md:17` + 加 `scrub_sample()` 函数 + 单元测试 | 0.5 天 |
| **P0** | C6 LOO independent split | `tests/test_loo_induction.py:79-80` 改 `samples[induct_n:]` for verify | 0.5 天 |
| **P0** | S2 Gate 2 real threshold | `verifier/gates.py:195-200` | 0.5 天 |
| **P0** | C9 artifact schema | 新建 `baselines/_artifact_schema.py` 强制 token/cost/model_id；改所有 `run_*.py` 用它 | 1 天 |
| **P0** | figure 改从 raw 读 | `paper/scripts/generate_figure3a_bnlearn.py` 删硬编码，从 raw JSON 读 | 0.5 天 |
| **P1** | **C3 真重构 compiler**（Tree 选 B）| `taskspec/compiler.py:68-70` BN 分支让 spec 真参与编译 | 2-4 天 |
| **P1** | 重跑 BN equivalence 测试（验证 C3 重构无回归）| `tests/test_equivalence_full.py` | 0.5 天 |
| **P2** | bnlearn 全量重跑（含 multiply_factors 修后）| `run_bnlearn_held_out.py` ×4 nets ×30q ×{mini, gpt-5.4} | 1 天 + $10-15 |

**Phase B 总: 6-9 天 + ~$15 实验成本**

---

## 5. 自审 checkpoint 清单（Phase B 完成后跑）

按 Codex 10 条 Suspicions（[2026-04-23-codex-review.md](2026-04-23-codex-review.md) 末尾）:

```bash
# Suspicion-3: prompt scrub 完整性
rg -n "reward_fn|answers|correct_diagnosis|correct_state|correct_posterior" \
    inductor/inductor.py inductor/prompts/induction_prompt.md \
    baselines/run_held_out_family.py baselines/run_hmm_held_out.py
# 期望: 0 hits（除了 scrub 函数自己）

# Suspicion-4: LOO disjoint
rg -n "samples\[:max_induction_samples\]|samples\[max_induction_samples:" \
    tests/test_loo_induction.py tests/test_gate3_ablation.py
# 期望: 看到 [k:] 而不是只有 [:k]

# Suspicion-5: Gate 2 真阈值
rg -n "passed = True|acc >=|threshold" verifier/gates.py
# 期望: 看到真阈值不是 passed=True

# Suspicion-7: C3 BN 真编译
rg -n "return BNReferenceSolver|variable_elimination" \
    taskspec/compiler.py taskspec/schema.py
# 期望: BN 分支不再直接 return BNReferenceSolver()

# Suspicion-9: token trace
rg -n "prompt_tokens|completion_tokens|total_cost|usage" \
    baselines/results/*.json baselines/run_*
# 期望: ≥1 hit 在每个新 run 的 JSON 和 run_*.py 里

# Suspicion-2: figure 不再硬编码
rg -n "our_dsl|pal_54|pal_mini|direct" \
    paper/scripts/generate_figure3a_bnlearn.py
# 期望: 看到从 json.load 读，不是 list literal
```

每条都通过 → 进 Phase C 实验；任何条 fail → 修后重审。

---

## 6. 一句话总结

**为什么之前错了**: 不是单一原因，是 **8 个独立问题** 在 **4 个元根因**（claim-first / 测试只看 returncode / confirmation bias / 外审晚） 下没被任何一道防线挡住。**修复必须是机制级别的**（artifact discipline + scrub 强制 + disjoint split + real Gate 2 + raw-vs-paper CI），不是单点 patch——否则 Phase C 跑出来的新 raw 还会被同样的问题污染。
