"""
Figure 3a: bnlearn real-world network scaling.
NeurIPS 2025 style following PaperBanana conventions.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

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

# ── Data ──
networks = ['Asia\n(8)', 'Child\n(20)', 'Insurance\n(27)', 'Alarm\n(37)']
x = np.arange(len(networks))
bar_width = 0.2

our_dsl  = [100, 100, 100, 100]
pal_54   = [90,  0,   3,   0]
pal_mini = [27,  20,  23,  0]
direct   = [0,   0,   0,   0]

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
