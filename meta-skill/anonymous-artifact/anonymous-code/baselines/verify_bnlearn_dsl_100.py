"""
验证 DSL ve_query 在 bnlearn 网络上的准确率（100 queries/网络）
不需要 LLM API 调用——纯确定性计算
"""
import sys, os, random, json, argparse, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# pgmpy 0.1.26 + xgboost-without-libomp 修复 (2026-04-27)
# 必须在 import pgmpy 之前 monkey-patch xgboost stub。详见 _pgmpy_compat.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pgmpy_compat  # noqa: F401

from pgmpy.utils import get_example_model
from pgmpy.inference import VariableElimination
from dsl.types import Factor
from dsl.core_ops import condition, multiply
from dsl.family_macros import _eliminate_one
from _artifact_schema import save_artifact
from scipy import stats

NETWORKS = ["asia", "child", "insurance", "alarm"]
QUERIES_PER_NET = 100
SEED = 2026


def wilson_ci(k, n, alpha=0.05):
    """Wilson score interval"""
    if n == 0:
        return (0.0, 1.0)
    z = stats.norm.ppf(1 - alpha / 2)
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    margin = z * ((p * (1 - p) / n + z ** 2 / (4 * n ** 2)) ** 0.5) / denom
    return (max(0, center - margin), min(1, center + margin))


def _domain_sizes(factors):
    sizes = {}
    for factor in factors:
        for idx, var in enumerate(factor.variables):
            vals = {key[idx] for key in factor.table}
            sizes[var] = max(sizes.get(var, 0), len(vals))
    return sizes


def _estimated_join_size(factors, var, domain_sizes):
    scope = []
    for factor in factors:
        if var not in factor.variables:
            continue
        for v in factor.variables:
            if v not in scope:
                scope.append(v)
    size = 1
    for v in scope:
        size *= max(1, domain_sizes.get(v, 1))
    return size


def dsl_posterior_distribution(factors, query_var, query_states, evidence):
    """Vectorized equivalent of ve_query for all states of one query variable.

    The original checker called ve_query once per query state, which repeats the
    same elimination work and is very slow on Insurance/Alarm. This helper uses
    the same core ops and _eliminate_one, but normalizes the final factor once.
    It also exposes P(evidence), so zero-probability evidence can be skipped.
    """
    conditioned = [condition(f, evidence) for f in factors]
    if any(len(f.table) == 0 for f in conditioned):
        return {}, 0.0

    all_vars = set()
    for factor in conditioned:
        all_vars.update(factor.variables)

    eliminate = set(all_vars) - {query_var} - set(evidence.keys())
    current = conditioned
    while eliminate:
        domain_sizes = _domain_sizes(current)
        var = min(
            eliminate,
            key=lambda v: (
                _estimated_join_size([f for f in current if v in f.variables], v, domain_sizes),
                v,
            ),
        )
        current = _eliminate_one(current, var)
        eliminate.remove(var)

    product_factor = multiply(current)
    evidence_prob = sum(product_factor.table.values())
    if evidence_prob <= 1e-12 or not math.isfinite(evidence_prob):
        return {}, evidence_prob

    posterior = {state: 0.0 for state in query_states}
    if query_var not in product_factor.variables:
        return posterior, evidence_prob

    q_idx = product_factor.variables.index(query_var)
    for vals, prob in product_factor.table.items():
        state = vals[q_idx]
        if state in posterior:
            posterior[state] += prob

    posterior = {state: prob / evidence_prob for state, prob in posterior.items()}
    return posterior, evidence_prob


def generate_and_verify(net_name, n_queries, seed):
    """生成 query 并用 DSL ve_query 验证"""
    model = get_example_model(net_name)
    pgmpy_ve = VariableElimination(model)
    nodes = list(model.nodes())
    rng = random.Random(seed)

    # 构建 DSL Factor 列表
    # 注 (2026-04-27 bug 修): 必须用 cpd.variables[1:] 而非 cpd.get_evidence()，
    # 因为 get_evidence() 返回 set/dict_keys，顺序不保证；cpd.values 的 axis
    # 顺序由 cpd.variables 决定。之前用 list(get_evidence()) 导致 multi-state /
    # multi-parent factor 构造时 axis 错位 → joint 分布错 → asia 60% / child 33%
    # 假阳性。修后所有 query 数学完全正确。dsl/core_ops 本身并无 bug。
    import numpy as np
    from itertools import product as iterproduct
    dsl_factors = []
    for node in nodes:
        cpd = model.get_cpds(node)
        parents = list(cpd.variables[1:])  # was: list(cpd.get_evidence())
        state_names = cpd.state_names

        # Factor variables 顺序: [node] + parents
        factor_vars = [node] + parents
        node_dom = state_names[node]
        parent_doms = [state_names[p] for p in parents]

        table = {}
        flat_vals = np.array(cpd.values).reshape(len(node_dom), -1)
        if parents:
            combos = list(iterproduct(*parent_doms))
            for col_idx, combo in enumerate(combos):
                for row_idx, node_val in enumerate(node_dom):
                    # key 是 tuple of values，顺序与 factor_vars 对应
                    key = (node_val,) + combo
                    prob = float(flat_vals[row_idx, col_idx].item())
                    if prob != 0.0:
                        table[key] = prob
        else:
            for row_idx, node_val in enumerate(node_dom):
                key = (node_val,)
                prob = float(flat_vals[row_idx, 0].item())
                if prob != 0.0:
                    table[key] = prob

        dsl_factors.append(Factor(variables=factor_vars, table=table))

    correct = 0
    total = 0
    errors = []

    max_attempts = n_queries * 20
    skipped_invalid_gold = 0
    skipped_zero_evidence = 0
    for i in range(max_attempts):  # 多生成一些以防 skip
        if total >= n_queries:
            break

        query_var = rng.choice(nodes)
        other_nodes = [n for n in nodes if n != query_var]
        n_ev = rng.randint(1, min(3, len(other_nodes)))
        ev_vars = rng.sample(other_nodes, n_ev)

        node_states = {n: model.get_cpds(n).state_names[n] for n in nodes}
        evidence = {v: rng.choice(node_states[v]) for v in ev_vars}

        # pgmpy gold
        try:
            pgmpy_result = pgmpy_ve.query([query_var], evidence=evidence)
            gold_posterior = {}
            for idx, state in enumerate(node_states[query_var]):
                gold_posterior[state] = float(pgmpy_result.values[idx])
        except Exception:
            continue

        # 跳过零概率 evidence 导致的未定义条件概率。pgmpy 在这类 query 上会
        # 返回 NaN；这不是推断器错误，而是 query 本身没有定义。
        if any(not math.isfinite(v) for v in gold_posterior.values()):
            skipped_invalid_gold += 1
            continue

        # DSL posterior：一次变量消元得到完整 posterior。若 P(evidence)=0，
        # 条件概率本身未定义；pgmpy 有时不会返回 NaN，而是给一个有限但
        # 没有数学语义的 posterior，必须显式跳过。
        try:
            dsl_posterior, evidence_prob = dsl_posterior_distribution(
                dsl_factors, query_var, node_states[query_var], evidence
            )
            if evidence_prob <= 1e-12 or not math.isfinite(evidence_prob):
                skipped_zero_evidence += 1
                continue

            # sanity check: posterior 应归一化到 1
            prob_sum = sum(dsl_posterior.values())
            if abs(prob_sum - 1.0) > 0.01:
                errors.append({
                    "query_id": total,
                    "network": net_name,
                    "query_var": query_var,
                    "evidence": evidence,
                    "error": f"DSL posterior does not sum to 1: sum={prob_sum:.4f}",
                    "gold": gold_posterior,
                    "dsl": dsl_posterior,
                })
                total += 1
                continue

            # 每个 state 的绝对误差
            max_err = 0
            for state in node_states[query_var]:
                gold_p = gold_posterior.get(state, 0)
                dsl_p = dsl_posterior[state]
                err = abs(gold_p - dsl_p)
                max_err = max(max_err, err)

            if max_err < 0.001:
                correct += 1
            else:
                errors.append({
                    "query_id": total,
                    "network": net_name,
                    "query_var": query_var,
                    "evidence": evidence,
                    "max_error": max_err,
                    "gold": gold_posterior,
                    "dsl": dsl_posterior,
                })
            total += 1

        except Exception as e:
            errors.append({
                "query_id": total,
                "network": net_name,
                "error": str(e)[:200],
            })
            total += 1

    return correct, total, errors, skipped_invalid_gold, skipped_zero_evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify DSL ve_query on bnlearn networks")
    parser.add_argument("--queries-per-net", type=int, default=QUERIES_PER_NET)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", default=None)
    parser.add_argument("--networks", nargs="+", default=NETWORKS, choices=NETWORKS)
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"bnlearn DSL Verification ({args.queries_per_net} queries/network)")
    print(f"{'='*60}\n")

    all_results = {}
    total_correct = 0
    total_queries = 0
    total_skipped_invalid_gold = 0
    total_skipped_zero_evidence = 0

    for net_name in args.networks:
        print(f"Processing {net_name}...", end=" ", flush=True)
        correct, total, errors, skipped_invalid_gold, skipped_zero_evidence = generate_and_verify(
            net_name, args.queries_per_net, args.seed
        )
        acc = correct / total if total > 0 else 0
        lo, hi = wilson_ci(correct, total)

        all_results[net_name] = {
            "correct": correct,
            "total": total,
            "accuracy": acc,
            "ci_lo": lo,
            "ci_hi": hi,
            "skipped_invalid_gold": skipped_invalid_gold,
            "skipped_zero_evidence": skipped_zero_evidence,
            "errors": errors,
        }

        total_correct += correct
        total_queries += total
        total_skipped_invalid_gold += skipped_invalid_gold
        total_skipped_zero_evidence += skipped_zero_evidence

        n_nodes = len(get_example_model(net_name).nodes())
        print(f"{correct}/{total} = {acc*100:.1f}% "
              f"[{lo*100:.1f}%, {hi*100:.1f}%] "
              f"({n_nodes} nodes; skipped invalid gold={skipped_invalid_gold}, "
              f"zero evidence={skipped_zero_evidence})")

        if errors:
            for e in errors[:3]:
                print(f"  ERROR: {e}")

    # 总结
    overall_acc = total_correct / total_queries
    lo, hi = wilson_ci(total_correct, total_queries)
    print(f"\n{'='*60}")
    print(f"Overall: {total_correct}/{total_queries} = {overall_acc*100:.1f}% "
          f"[{lo*100:.1f}%, {hi*100:.1f}%]")
    print(f"Skipped invalid gold queries: {total_skipped_invalid_gold}")
    print(f"Skipped zero-probability evidence queries: {total_skipped_zero_evidence}")
    print(f"{'='*60}")

    all_results["_overall"] = {
        "correct": total_correct,
        "total": total_queries,
        "accuracy": overall_acc,
        "ci_lo": lo,
        "ci_hi": hi,
        "skipped_invalid_gold": total_skipped_invalid_gold,
        "skipped_zero_evidence": total_skipped_zero_evidence,
        "queries_per_net": args.queries_per_net,
        "seed": args.seed,
        "networks": args.networks,
    }

    # 保存结果
    out_path = args.out or os.path.join(
        os.path.dirname(__file__),
        "results",
        f"bnlearn_dsl_{args.queries_per_net}q_seed{args.seed}.json",
    )
    save_artifact(
        out_path,
        all_results,
        prompt_tokens=0,
        completion_tokens=0,
        total_cost_usd=0.0,
        model_id="deterministic-dsl",
        extra_meta={
            "benchmark": "bnlearn",
            "reference": "pgmpy.VariableElimination",
            "zero_probability_evidence_policy": "skip",
            "command": "baselines/verify_bnlearn_dsl_100.py",
        },
    )
    print(f"\n结果已保存到 {out_path}")
