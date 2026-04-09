"""计算所有实验的 Clopper-Pearson exact binomial 95% CI"""
from scipy import stats

def clopper_pearson(k, n, alpha=0.05):
    """Clopper-Pearson exact binomial CI"""
    if n == 0:
        return (0.0, 1.0)
    if k == 0:
        lo = 0.0
    else:
        lo = stats.beta.ppf(alpha/2, k, n-k+1)
    if k == n:
        hi = 1.0
    else:
        hi = stats.beta.ppf(1 - alpha/2, k+1, n-k)
    return (lo, hi)

def ci_str(k, n):
    p = k/n
    lo, hi = clopper_pearson(k, n)
    return f"{p*100:.1f}% & {n} & [{lo*100:.1f}%, {hi*100:.1f}%]"

def ci_latex(k, n):
    p = k/n
    lo, hi = clopper_pearson(k, n)
    return f"{p*100:.1f}\\% & {n} & [{lo*100:.1f}\\%, {hi*100:.1f}\\%]"

# =============================================
# 1. PCD Preference (n=200 each)
# =============================================
print("=" * 90)
print("1. PCD PREFERENCE (n=200)")
print("=" * 90)
print(f"{'Model':<28} {'Metric':<10} {'p':>7} {'k':>5} {'n':>5}   {'95% CI'}")
print("-" * 90)

pcd_pref = [
    ('GPT-4o-mini', 0.82, 0.275, 1.0, 200),
    ('GPT-4o',      1.0,  0.295, 1.0, 200),
    ('GPT-5.4',     1.0,  0.4,   1.0, 200),
    ('Sonnet 4',    1.0,  0.675, 1.0, 200),
    ('Opus 4.6',    1.0,  0.775, 1.0, 200),
    ('Gemini 3.1 Pro Preview', 1.0, 0.685, 1.0, 200),
]

for model, parse, compute, decide, n in pcd_pref:
    for metric, p in [('Parse', parse), ('Compute', compute), ('Decide', decide)]:
        k = round(p * n)
        lo, hi = clopper_pearson(k, n)
        print(f"{model:<28} {metric:<10} {p*100:>6.1f}% {k:>5} {n:>5}   [{lo*100:.1f}%, {hi*100:.1f}%]")
    print()

# =============================================
# 2. PCD BN (n=900 each)
# =============================================
print("=" * 90)
print("2. PCD BN (n=900)")
print("=" * 90)
print(f"{'Model':<28} {'Metric':<10} {'p':>7} {'k':>5} {'n':>5}   {'95% CI'}")
print("-" * 90)

pcd_bn = [
    ('GPT-4o-mini', 0.3389, 0.2233, 1.0, 900),
    ('GPT-4o',      0.4833, 0.2489, 1.0, 900),
    ('GPT-5.4',     0.3067, 0.3122, 1.0, 900),
    ('Sonnet 4',    0.3056, 0.2911, 1.0, 900),
]

for model, parse, compute, decide, n in pcd_bn:
    for metric, p in [('Parse', parse), ('Compute', compute), ('Decide', decide)]:
        k = round(p * n)
        lo, hi = clopper_pearson(k, n)
        print(f"{model:<28} {metric:<10} {p*100:>6.1f}% {k:>5} {n:>5}   [{lo*100:.1f}%, {hi*100:.1f}%]")
    print()

# =============================================
# 3. PAL (BN n=900, Pref n=624)
# =============================================
print("=" * 90)
print("3. PAL BASELINE")
print("=" * 90)

for desc, k, n in [('PAL-BN (GPT-4o-mini)', 238, 900), ('PAL-Pref (GPT-4o-mini)', 183, 624)]:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{desc:<30} p={p*100:.1f}%, k={k}, n={n}, CI=[{lo*100:.1f}%, {hi*100:.1f}%]")
print()

# =============================================
# 4. Compile-time baseline
# =============================================
print("=" * 90)
print("4. COMPILE-TIME BASELINE")
print("=" * 90)

for model, task, k, n in [
    ('GPT-5.4',     'BN',   900, 900),
    ('GPT-5.4',     'Pref', 624, 624),
    ('GPT-4o',      'BN',   0,   900),
    ('GPT-4o-mini', 'BN',   0,   900),
]:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model:<15} {task:<6} p={p*100:.1f}%, k={k}, n={n}, CI=[{lo*100:.1f}%, {hi*100:.1f}%]")
print()

# =============================================
# 5. Held-out NB (n=20)
# =============================================
print("=" * 90)
print("5. HELD-OUT NAIVE BAYES (n=20)")
print("=" * 90)

held_out = [
    ('GPT-5.4',     'Direct',           12, 20),
    ('GPT-5.4',     'Compile (free)',    20, 20),
    ('GPT-5.4',     'Compile (core)',    20, 20),
    ('GPT-5.4',     'PCD-Parse',         20, 20),
    ('GPT-5.4',     'PCD-Compute',       14, 20),
    ('GPT-5.4',     'PCD-Decide',        20, 20),
    ('GPT-4o-mini', 'Direct',            9,  20),
    ('GPT-4o-mini', 'Compile (free)',    20, 20),
    ('GPT-4o-mini', 'Compile (core)',    20, 20),
    ('GPT-4o-mini', 'PCD-Parse',         2,  20),
    ('GPT-4o-mini', 'PCD-Compute',       9,  20),
    ('GPT-4o-mini', 'PCD-Decide',        20, 20),
]

print(f"{'Model':<15} {'Metric':<20} {'p':>7} {'k':>3} {'n':>3}   {'95% CI'}")
print("-" * 75)
for model, metric, k, n in held_out:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model:<15} {metric:<20} {p*100:>6.1f}% {k:>3} {n:>3}   [{lo*100:.1f}%, {hi*100:.1f}%]")
print()

# =============================================
# 6. DeLLMa (n=17~20)
# =============================================
print("=" * 90)
print("6. DELLMA (n=17~20)")
print("=" * 90)

dellma = [
    ('GPT-5.4',     'Direct',   8,  20),
    ('GPT-5.4',     'Compile',  5,  17),
    ('GPT-4o-mini', 'Direct',   8,  20),
    ('Opus 4.6',    'Direct',   8,  20),
    ('Opus 4.6',    'Compile',  3,  17),
]

for model, metric, k, n in dellma:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model:<15} {metric:<10} p={p*100:.1f}%, k={k}, n={n}, CI=[{lo*100:.1f}%, {hi*100:.1f}%]")
print()

# =============================================
# LATEX FORMAT OUTPUT
# =============================================
print("=" * 90)
print("FULL LATEX TABLE")
print("=" * 90)
print()

# --- Table 1: PCD Preference ---
print("% === Table: PCD Preference (n=200) ===")
print("% Model & Metric & Accuracy & n & 95\\% CI \\\\")
for model, parse, compute, decide, n in pcd_pref:
    for metric, p in [('Parse', parse), ('Compute', compute), ('Decide', decide)]:
        k = round(p * n)
        lo, hi = clopper_pearson(k, n)
        pstr = f"{p*100:.1f}"
        lostr = f"{lo*100:.1f}"
        histr = f"{hi*100:.1f}"
        print(f"{model} & {metric} & {pstr}\\% & {n} & [{lostr}\\%, {histr}\\%] \\\\")
print()

# --- Table 2: PCD BN ---
print("% === Table: PCD BN (n=900) ===")
for model, parse, compute, decide, n in pcd_bn:
    for metric, p in [('Parse', parse), ('Compute', compute), ('Decide', decide)]:
        k = round(p * n)
        lo, hi = clopper_pearson(k, n)
        pstr = f"{p*100:.1f}"
        lostr = f"{lo*100:.1f}"
        histr = f"{hi*100:.1f}"
        print(f"{model} & {metric} & {pstr}\\% & {n} & [{lostr}\\%, {histr}\\%] \\\\")
print()

# --- Table 3: PAL ---
print("% === Table: PAL Baseline ===")
for desc, k, n in [('GPT-4o-mini (BN)', 238, 900), ('GPT-4o-mini (Pref)', 183, 624)]:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{desc} & {p*100:.1f}\\% & {n} & [{lo*100:.1f}\\%, {hi*100:.1f}\\%] \\\\")
print()

# --- Table 4: Compile-time ---
print("% === Table: Compile-time Baseline ===")
for model, task, k, n in [
    ('GPT-5.4','BN',900,900),
    ('GPT-5.4','Pref',624,624),
    ('GPT-4o','BN',0,900),
    ('GPT-4o-mini','BN',0,900),
]:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model} & {task} & {p*100:.1f}\\% & {n} & [{lo*100:.1f}\\%, {hi*100:.1f}\\%] \\\\")
print()

# --- Table 5: Held-out NB ---
print("% === Table: Held-out Naive Bayes (n=20) ===")
for model, metric, k, n in held_out:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model} & {metric} & {p*100:.1f}\\% & {n} & [{lo*100:.1f}\\%, {hi*100:.1f}\\%] \\\\")
print()

# --- Table 6: DeLLMa ---
print("% === Table: DeLLMa (n=17~20) ===")
for model, metric, k, n in dellma:
    p = k/n
    lo, hi = clopper_pearson(k, n)
    print(f"{model} & {metric} & {p*100:.1f}\\% & {n} & [{lo*100:.1f}\\%, {hi*100:.1f}\\%] \\\\")
