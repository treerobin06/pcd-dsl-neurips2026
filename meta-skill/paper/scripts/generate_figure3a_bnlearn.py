"""
Figure 3a: bnlearn real-world network scaling.
NeurIPS 2025 style following PaperBanana conventions.

✅ 2026-04-24 ARTIFACT DISCIPLINE FIX (C9 + Codex CRITICAL 1 已修):
原代码 L33-36 含 `our_dsl=[100,100,100,100]` 等硬编码——属于学术造假。
现已删除并改为从 baselines/results/bnlearn_*.json 的 'per_network' 字段读，
缺失则 fail-fast (raise + exit 1) 阻止 figure 生成，绝不再用硬编码兜底。

历史数据来源（已废弃）:
- 原 `our_dsl=[100,100,100,100]` 来自 verify_bnlearn_dsl_100.py 的旧版本
  fallback bug（`dsl_p = gold_p` 自动 100%，已修于 commit 9963f2f）
- 原 `pal_54 / pal_mini / direct` 来自 raw 但是 overall 不是 per-network

Phase C 待补:
1. run_bnlearn_held_out.py 改 save_artifact 含 'per_network' 字段
2. 重跑 4 nets × {mini, gpt-5.4} 取真实 per-network 数字
3. 本 figure 自动 regenerate（从 raw 读）—— 不需要再改本文件硬编码

注意: figure3a.pdf 当前仍是 fake 100% 版本（commit 历史里）；
重跑前 paper 引用 \\includegraphics{figure3a_bnlearn} 仍指向 fake PDF。
prose 和 figure 必须 Phase C 完成后**同 commit 更新**。
"""
import glob
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


# ── C9 修复 (2026-04-24): 从 raw artifact 读，禁止硬编码 ──
# 原代码 L33-36 硬编码 our_dsl=[100,100,100,100] 等被 Codex CRITICAL 1 标
# 为"NEW EVIDENCE OF EVASION"。本节强制从 baselines/results/bnlearn_*.json
# 读 per-network 数字；缺失则 raise，阻止生成。
_RAW_GLOB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "baselines", "results", "bnlearn_*.json"
)
_REQUIRED_NETWORKS = ["asia", "child", "insurance", "alarm"]
_REQUIRED_METHODS = ["our_dsl", "pal_54", "pal_mini", "direct"]


def _load_per_network_from_raw():
    """从 baselines/results/bnlearn_*.json 读 per-network 数字。

    要求 JSON 含 'per_network' 字段:
        {"per_network": {"asia": {"our_dsl": 95.0, "pal_54": 90.0, ...}, ...}}

    Returns:
        dict: {method: [asia_acc, child_acc, insurance_acc, alarm_acc]} (% scale 0-100)

    Raises:
        FileNotFoundError: 没有 raw bnlearn JSON
        KeyError: raw 缺 per_network/required network/required method
    """
    files = sorted(glob.glob(_RAW_GLOB))
    if not files:
        raise FileNotFoundError(
            f"C9 violation: no bnlearn raw artifact under {_RAW_GLOB}. "
            f"Run baselines/run_bnlearn_held_out.py first; figure cannot be regenerated "
            f"from hardcoded values (Codex CRITICAL 1)."
        )

    # 取最新的
    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)

    if "per_network" not in data:
        raise KeyError(
            f"C9 violation: {latest} missing 'per_network' field. Current bnlearn "
            f"runs only save 'overall' aggregates; per-network breakdown required for "
            f"Figure 3a but not yet captured in raw. Re-run run_bnlearn_held_out.py "
            f"with per-network output enabled before regenerating Figure 3a."
        )

    per_net = data["per_network"]
    result = {}
    for method in _REQUIRED_METHODS:
        try:
            result[method] = [per_net[n][method] for n in _REQUIRED_NETWORKS]
        except KeyError as e:
            raise KeyError(
                f"C9 violation: {latest} per_network missing {e} (network or method). "
                f"Required: networks={_REQUIRED_NETWORKS}, methods={_REQUIRED_METHODS}"
            )
    return result

# ── NeurIPS style setup ──
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 10,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 7.5,
    'axes.linewidth': 0.8,
    'axes.edgecolor': '#333333',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'figure.dpi': 300,
})

# ── Data (loaded from raw, not hardcoded — C9 fix) ──
networks = ['Asia\n(8)', 'Child\n(20)', 'Insurance\n(27)', 'Alarm\n(37)']
x = np.arange(len(networks))
bar_width = 0.2

# 从 raw 读（旧 [100,100,100,100] 硬编码已删除，C9/Codex CRITICAL 1）
try:
    _data = _load_per_network_from_raw()
except (FileNotFoundError, KeyError) as e:
    print(f"\n❌ Cannot generate figure3a — {e}\n", file=sys.stderr)
    print(
        "Per-network bnlearn raw is required (Phase C task). To regenerate this "
        "figure, run:\n"
        "  cd baselines && python3 run_bnlearn_held_out.py --model openai/gpt-4o-mini --queries-per-net 30\n"
        "  cd baselines && python3 run_bnlearn_held_out.py --model openai/gpt-5.4 --queries-per-net 30\n"
        "and ensure each result JSON saves 'per_network' breakdown.",
        file=sys.stderr,
    )
    sys.exit(1)

our_dsl  = _data["our_dsl"]
pal_54   = _data["pal_54"]
pal_mini = _data["pal_mini"]
direct   = _data["direct"]

# Okabe-Ito palette
colors = {
    'Our DSL':          '#228833',
    'PAL (GPT-5.4)':    '#4477AA',
    'PAL (4o-mini)':    '#EE6677',
    'Direct Answer':    '#BBBBBB',
}

# ── Plot ──
fig, ax = plt.subplots(figsize=(4.5, 3.0))

bars1 = ax.bar(x - 1.5*bar_width, our_dsl,  bar_width, label='Our DSL',
               color=colors['Our DSL'], edgecolor='#1a6625', linewidth=0.5)
bars2 = ax.bar(x - 0.5*bar_width, pal_54,   bar_width, label='PAL (GPT-5.4)',
               color=colors['PAL (GPT-5.4)'], edgecolor='#2d5a8a', linewidth=0.5)
bars3 = ax.bar(x + 0.5*bar_width, pal_mini,  bar_width, label='PAL (4o-mini)',
               color=colors['PAL (4o-mini)'], edgecolor='#c4505f', linewidth=0.5)
bars4 = ax.bar(x + 1.5*bar_width, direct,    bar_width, label='Direct Answer',
               color=colors['Direct Answer'], edgecolor='#999999', linewidth=0.5)

# Value labels on bars
for bars in [bars1, bars2, bars3]:
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height + 1.5,
                    f'{int(height)}', ha='center', va='bottom', fontsize=6)

# Horizontal grid
ax.grid(True, axis='y', linestyle='--', linewidth=0.5, color='#E0E0E0', zorder=0)

# ≥20 node failure zone
ax.axvspan(0.6, 3.5, alpha=0.05, color='red', zorder=0)
ax.annotate('PAL fails on $\\geq$20 nodes', xy=(2.05, 105),
            fontsize=6.5, fontstyle='italic', color='#AA3377', ha='center')

# Axes
ax.set_xlabel('Network (nodes)')
ax.set_ylabel('Accuracy (%)')
ax.set_xticks(x)
ax.set_xticklabels(networks)
ax.set_ylim(-3, 115)
ax.set_yticks([0, 20, 40, 60, 80, 100])

# Legend — outside plot to avoid overlap
ax.legend(loc='upper center', frameon=False, ncol=4, bbox_to_anchor=(0.5, 1.18),
          columnspacing=0.8, handletextpad=0.3)

plt.tight_layout()
plt.savefig('../figures/figure3a_bnlearn.pdf', bbox_inches='tight', dpi=300)
plt.savefig('../figures/figure3a_bnlearn.png', bbox_inches='tight', dpi=300)
print("Saved figure3a_bnlearn.pdf and .png")
