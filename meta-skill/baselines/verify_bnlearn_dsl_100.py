"""
验证 DSL ve_query 在 bnlearn 网络上的准确率（100 queries/网络）
不需要 LLM API 调用——纯确定性计算
"""
import sys, os, random, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pgmpy.utils import get_example_model
from pgmpy.inference import VariableElimination
from dsl.types import Factor
from dsl.family_macros import ve_query
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


def generate_and_verify(net_name, n_queries, seed):
    """生成 query 并用 DSL ve_query 验证"""
    model = get_example_model(net_name)
    pgmpy_ve = VariableElimination(model)
    nodes = list(model.nodes())
    rng = random.Random(seed)

    # 构建 DSL Factor 列表
    import numpy as np
    from itertools import product as iterproduct
    dsl_factors = []
    for node in nodes:
        cpd = model.get_cpds(node)
        parents = list(cpd.get_evidence())
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
                    table[key] = float(flat_vals[row_idx, col_idx].item())
        else:
            for row_idx, node_val in enumerate(node_dom):
                key = (node_val,)
                table[key] = float(flat_vals[row_idx, 0].item())

        dsl_factors.append(Factor(variables=factor_vars, table=table))

    correct = 0
    total = 0
    errors = []

    for i in range(n_queries + 10):  # 多生成一些以防 skip
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

        # DSL ve_query：对每个 state 单独查询得到完整 posterior
        # 注：ve_query 签名是 -> float（返回单个 P(query_var=state | evidence)）
        # 原代码传 {query_var: [all_states]}（list 作为 value）→ ve_query 永远返回 0.0
        # 然后 `dsl_p = gold_p` fallback 把这个永远为 0 的 bug 吞掉自动通过（fraud blocker C1, 2026-04-23 修复）
        try:
            dsl_posterior = {}
            for state in node_states[query_var]:
                query_vars_dict = {query_var: state}  # 单个 value，不是 list
                dsl_p = ve_query(dsl_factors, query_vars_dict, evidence)
                dsl_posterior[state] = dsl_p

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

    return correct, total, errors


if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"bnlearn DSL Verification (100 queries/network)")
    print(f"{'='*60}\n")

    all_results = {}
    total_correct = 0
    total_queries = 0

    for net_name in NETWORKS:
        print(f"Processing {net_name}...", end=" ", flush=True)
        correct, total, errors = generate_and_verify(net_name, QUERIES_PER_NET, SEED)
        acc = correct / total if total > 0 else 0
        lo, hi = wilson_ci(correct, total)

        all_results[net_name] = {
            "correct": correct,
            "total": total,
            "accuracy": acc,
            "ci_lo": lo,
            "ci_hi": hi,
            "errors": errors,
        }

        total_correct += correct
        total_queries += total

        n_nodes = len(get_example_model(net_name).nodes())
        print(f"{correct}/{total} = {acc*100:.1f}% "
              f"[{lo*100:.1f}%, {hi*100:.1f}%] "
              f"({n_nodes} nodes)")

        if errors:
            for e in errors[:3]:
                print(f"  ERROR: {e}")

    # 总结
    overall_acc = total_correct / total_queries
    lo, hi = wilson_ci(total_correct, total_queries)
    print(f"\n{'='*60}")
    print(f"Overall: {total_correct}/{total_queries} = {overall_acc*100:.1f}% "
          f"[{lo*100:.1f}%, {hi*100:.1f}%]")
    print(f"{'='*60}")

    # 保存结果
    out_path = os.path.join(os.path.dirname(__file__), "results", "bnlearn_dsl_100q.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n结果已保存到 {out_path}")
