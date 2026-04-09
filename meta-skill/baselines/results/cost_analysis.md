# Cost Curve 分析

## OpenRouter 定价 (2026-03)

| 模型 | Input ($/M tokens) | Output ($/M tokens) |
|------|:---:|:---:|
| GPT-4o-mini | $0.15 | $0.60 |
| GPT-4o | $2.50 | $10.00 |
| GPT-5.4 | $2.50 | $10.00 |
| Claude Sonnet 4 | $3.00 | $15.00 |
| Claude Opus 4.6 | $15.00 | $75.00 |

## 方法对比: BN 推断 (BLInD, 900 问题)

### Our DSL+Compiler (GPT-4o-mini)
- **Compile-time**: Inductor 1次调用
  - Input: ~3000 tokens (DSL docs + 5 samples)
  - Output: ~500 tokens (TaskSpec JSON)
  - Cost: 3000 × $0.15/M + 500 × $0.60/M = $0.00075
- **Test-time**: 确定性 solver, 0 API calls
- **总成本**: ~$0.001
- **准确率**: 100%

### Compile-time Free Code (GPT-5.4)
- **Compile-time**: 1次生成 + 0-1次 self-repair
  - 生成: ~4000 input + ~3000 output = $0.01 + $0.03 = $0.04
  - 最多 1 轮修复: $0.04 × 2 = $0.08
- **Test-time**: 确定性 solver, 0 API calls
- **总成本**: ~$0.04-0.08
- **准确率**: 100%

### Compile-time Free Code (GPT-4o/GPT-4o-mini)
- **Compile-time**: 生成 + 5 轮 self-repair 全部失败
  - GPT-4o: ~6 calls × (4000 × $2.5/M + 3000 × $10/M) = ~$0.24
  - GPT-4o-mini: ~6 calls × (4000 × $0.15/M + 3000 × $0.60/M) = ~$0.014
- **准确率**: 0% (solver 无法正确实现 variable elimination)

### Per-instance Direct Answer (GPT-5.4)
- **每个问题**: ~800 input + ~200 output
  - Cost per problem: 800 × $2.5/M + 200 × $10/M = $0.004
- **900 问题总成本**: 900 × $0.004 = $3.60
- **准确率**: 31.2%

### Per-instance PAL (GPT-4o-mini)
- **每个问题**: ~1200 input + ~1500 output
  - Cost per problem: 1200 × $0.15/M + 1500 × $0.60/M = $0.00108
- **900 问题总成本**: 900 × $0.00108 = $0.97
- **准确率**: 26.4% (代码成功率 75.4%)

## 汇总表

| 方法 | 模型 | BN 准确率 | 总成本 | Cost/问题 | 相对成本 |
|------|------|:---------:|:------:|:---------:|:--------:|
| **Our DSL+Compiler** | mini | **100%** | **$0.001** | $0.000001 | **1×** |
| Compile-time (成功) | GPT-5.4 | 100% | $0.06 | $0.00007 | 60× |
| Compile-time (失败) | GPT-4o | 0% | $0.24 | — | — |
| Per-instance PAL | mini | 26.4% | $0.97 | $0.0011 | 970× |
| Per-instance Direct | GPT-5.4 | 31.2% | $3.60 | $0.004 | 3600× |
| Per-instance Direct | Opus 4.6 | ~22%* | $54 | $0.06 | 54000× |

*Opus BN Compute|GoldParse 从 PCD 估算

## 核心发现

1. **Our DSL 比 per-instance 直接算便宜 3600×**，且准确率从 31% 提到 100%
2. **GPT-5.4 compile-time 也能达到 100%，但需要 frontier 模型** — 便宜模型 (4o/mini) 写不出正确的 VE 代码
3. **Our DSL 让 $0.001 的 mini 达到 $0.06 的 5.4 compile-time 相同效果** — 60× 的成本降低
4. **Per-instance 方法无论用什么模型都无法超过 ~31%** — 问题在"逐题计算"而非模型能力

## 偏好学习 (Flight, 624 问题)

| 方法 | 模型 | 准确率 | 总成本 | 相对成本 |
|------|------|:---------:|:------:|:--------:|
| **Our DSL+Compiler** | mini | **74.8%** | **$0.001** | **1×** |
| Compile-time | GPT-5.4 | 74.8% | $0.06 | 60× |
| Per-instance Direct | Opus | 56.6% | ~$80 | 80000× |
| Per-instance Direct | mini | 36.6% | ~$0.5 | 500× |
| Per-instance PAL | mini | 29.3% | ~$0.7 | 700× |
