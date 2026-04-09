"""
Figure 3b: Cost-accuracy Pareto plot on BLInD.
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
    'legend.fontsize': 7,
    'axes.linewidth': 0.8,
    'axes.edgecolor': '#333333',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'figure.dpi': 300,
})

# ── Data ──
methods = {
    'Our DSL\n(GPT-4o-mini)':    {'cost': 0.008, 'acc': 100,  'color': '#228833', 'marker': '*',  'size': 200, 'zorder': 10},
    'Compile\n(GPT-5.4)':        {'cost': 0.11,  'acc': 100,  'color': '#4477AA', 'marker': '^',  'size': 80,  'zorder': 8},
    'Compile\n(GPT-4o-mini)':    {'cost': 0.05,  'acc': 0,    'color': '#CCBB44', 'marker': 'X',  'size': 80,  'zorder': 6},
    'PAL\n(GPT-5.4)':            {'cost': 2.50,  'acc': 98.1, 'color': '#AA3377', 'marker': 'D',  'size': 80,  'zorder': 7},
    'PAL\n(GPT-4o-mini)':        {'cost': 0.84,  'acc': 26.4, 'color': '#EE6677', 'marker': 'D',  'size': 60,  'zorder': 6},
    'Direct\n(GPT-5.4)':         {'cost': 3.60,  'acc': 31.2, 'color': '#BBBBBB', 'marker': 's',  'size': 60,  'zorder': 5},
}

# ── Plot ──
fig, ax = plt.subplots(figsize=(4.5, 3.0))

for name, d in methods.items():
    ax.scatter(d['cost'], d['acc'], c=d['color'], marker=d['marker'],
               s=d['size'], zorder=d['zorder'], edgecolors='#333333', linewidths=0.5,
               label=name)

# Annotations with offset
annotations = {
    'Our DSL\n(GPT-4o-mini)':    (0.008, 100,  (-25, -12), '#228833'),
    'Compile\n(GPT-5.4)':        (0.11,  100,  (-20, -12), '#4477AA'),
    'PAL\n(GPT-5.4)':            (2.50,  98.1, (-15, -12), '#AA3377'),
    'Compile\n(GPT-4o-mini)':    (0.05,  0,    (5, 8),     '#CCBB44'),
    'PAL\n(GPT-4o-mini)':        (0.84,  26.4, (5, 8),     '#EE6677'),
    'Direct\n(GPT-5.4)':         (3.60,  31.2, (5, 8),     '#BBBBBB'),
}

for name, (x, y, offset, color) in annotations.items():
    label = f'${x}, {y:.0f}%' if y == int(y) else f'${x}, {y}%'
    ax.annotate(label, xy=(x, y), xytext=offset,
                textcoords='offset points', fontsize=6, color=color,
                ha='center' if offset[0] < 0 else 'left')

# Cost ratio annotations
ax.annotate('', xy=(0.008, 92), xytext=(0.11, 92),
            arrowprops=dict(arrowstyle='<->', color='#666666', lw=0.8))
ax.text(0.03, 94, '$14\\times$', fontsize=7, color='#666666', ha='center')

ax.annotate('', xy=(0.008, 85), xytext=(2.50, 85),
            arrowprops=dict(arrowstyle='<->', color='#666666', lw=0.8))
ax.text(0.14, 87, '$310\\times$', fontsize=7, color='#666666', ha='center')

# Grid
ax.grid(True, linestyle='--', linewidth=0.5, color='#E0E0E0', zorder=0)

# Axes
ax.set_xscale('log')
ax.set_xlabel('Cost (\\$, log scale)')
ax.set_ylabel('Accuracy (%)')
ax.set_xlim(0.003, 10)
ax.set_ylim(-8, 115)
ax.set_yticks([0, 20, 40, 60, 80, 100])

# Legend
ax.legend(loc='center left', frameon=False, ncol=1, markerscale=0.8,
          bbox_to_anchor=(1.02, 0.5))

plt.tight_layout()
plt.savefig('../figures/figure3b_cost.pdf', bbox_inches='tight', dpi=300)
plt.savefig('../figures/figure3b_cost.png', bbox_inches='tight', dpi=300)
print("Saved figure3b_cost.pdf and .png")
