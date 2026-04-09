"""
Figure 2: Compute|GoldParse accuracy vs BN depth.
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
    'axes.titlesize': 12,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'legend.fontsize': 8,
    'axes.linewidth': 0.8,
    'axes.edgecolor': '#333333',
    'axes.spines.top': False,     # open frame
    'axes.spines.right': False,   # open frame
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.major.size': 4,
    'ytick.major.size': 4,
    'figure.dpi': 300,
})

# ── Data ──
depths = np.arange(2, 11)

data = {
    'Our DSL':     [100, 100, 100, 100, 100, 100, 100, 100, 100],
    'GPT-5.4':     [81, 56, 41, 24, 20, 23, 13, 12, 11],
    'Sonnet 4':    [82, 55, 37, 24, 15, 19, 9, 12, 9],
    'GPT-4o-mini': [82, 49, 30, 11, 12, 8, 4, 2, 3],
}

# Okabe-Ito derived palette
colors = {
    'Our DSL':     '#228833',  # forest green
    'GPT-5.4':     '#4477AA',  # steel blue
    'Sonnet 4':    '#EE6677',  # salmon
    'GPT-4o-mini': '#BBBBBB',  # gray
}

markers = {
    'Our DSL':     's',  # square
    'GPT-5.4':     '^',  # triangle
    'Sonnet 4':    'D',  # diamond
    'GPT-4o-mini': '*',  # star
}

linestyles = {
    'Our DSL':     '-',
    'GPT-5.4':     '-',
    'Sonnet 4':    ':',
    'GPT-4o-mini': '--',
}

# ── Plot ──
fig, ax = plt.subplots(figsize=(4.5, 3.0))

for name in ['Our DSL', 'GPT-5.4', 'Sonnet 4', 'GPT-4o-mini']:
    lw = 2.5 if name == 'Our DSL' else 1.5
    ms = 8 if name == 'Our DSL' else 6
    ax.plot(depths, data[name],
            color=colors[name], marker=markers[name], markersize=ms,
            linewidth=lw, linestyle=linestyles[name],
            label=name, zorder=10 if name == 'Our DSL' else 5)

# Grid
ax.grid(True, axis='both', linestyle='--', linewidth=0.5, color='#E0E0E0', zorder=0)

# Axes
ax.set_xlabel('BN Depth')
ax.set_ylabel('Compute|Gold (%)')
ax.set_xlim(1.5, 10.5)
ax.set_ylim(-2, 108)
ax.set_xtick = depths
ax.set_xticks(depths)
ax.set_yticks([0, 20, 40, 60, 80, 100])

# Legend
ax.legend(loc='upper right', frameon=False, handlelength=2.0)

# Annotation: highlight the gap at depth 10
ax.annotate('89% error rate',
            xy=(10, 11), xytext=(8.0, 30),
            fontsize=7, fontstyle='italic', color='#4477AA',
            arrowprops=dict(arrowstyle='->', color='#4477AA', lw=0.8))

plt.tight_layout()
plt.savefig('../figures/figure2_depth.pdf', bbox_inches='tight', dpi=300)
plt.savefig('../figures/figure2_depth.png', bbox_inches='tight', dpi=300)
print("Saved figure2_depth.pdf and .png")
