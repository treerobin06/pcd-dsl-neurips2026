#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PAL (Program-Aided Language) Baseline 实验

让 LLM 直接生成 Python 代码来解决概率推理任务，对比我们的 DSL+Compiler 方案。

两种任务:
1. 偏好学习 (Flight/Hotel): R1-R4 历史 → 生成代码推断偏好 → 推荐 R5
2. BN 推断 (BLInD): 给 BN 描述 → 生成代码计算条件概率

用法:
  # 快速验证（10 样本）
  python run_pal_experiment.py --task preference --n 10 --model openai/gpt-4o-mini

  # 偏好学习全量
  python run_pal_experiment.py --task preference --model openai/gpt-4o-mini

  # BN 推断
  python run_pal_experiment.py --task bn --n 50 --model openai/gpt-4o-mini

  # 同时测两个任务
  python run_pal_experiment.py --task both --n 20 --model openai/gpt-4o-mini
"""

import os
import sys
import json
import re
import time
import asyncio
import subprocess
import tempfile
import argparse
import csv
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from openai import AsyncOpenAI

# ==========================================
# 路径常量
# ==========================================
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROMPT_DIR = SCRIPT_DIR / "prompts"

FLIGHT_DATA = PROJECT_ROOT / "bayes" / "data" / "eval" / "interaction" / "flight.jsonl"
HOTEL_DATA = PROJECT_ROOT / "bayes" / "data" / "eval" / "interaction" / "hotel.jsonl"
BLIND_DATA = PROJECT_ROOT / "BLInD" / "datasets" / "Base_1000_examples.csv"
RESULTS_DIR = SCRIPT_DIR / "results"

# ==========================================
# OpenRouter 客户端
# ==========================================
def get_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 环境变量未设置")
    proxy = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", "http://127.0.0.1:7897"))
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        http_client=httpx.AsyncClient(proxy=proxy, timeout=120),
    )


# ==========================================
# 代码执行（安全沙箱）
# ==========================================
def execute_python_code(code: str, timeout: int = 30) -> Tuple[bool, str, str]:
    """安全执行 LLM 生成的 Python 代码

    Returns:
        (success, stdout, stderr)
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": "",
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "TEMP": os.environ.get("TEMP", ""),
                "TMP": os.environ.get("TMP", ""),
            },
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as e:
        return False, "", str(e)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def extract_code_block(response: str) -> str:
    """从 LLM 响应中提取 Python 代码块"""
    # 匹配 ```python ... ``` 或 ```...```
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)
    if matches:
        return matches[0].strip()
    # 如果没有代码块，尝试把整个响应当作代码
    if "import " in response or "print(" in response:
        return response.strip()
    return ""


# ==========================================
# 偏好学习任务
# ==========================================
def build_preference_prompt(sample: Dict, prompt_template: str) -> str:
    """构建偏好学习的 PAL prompt"""
    features = sample["features"]
    rounds = sample["rounds"]
    rounds_numpy = sample["rounds_numpy"]
    n_features = len(features)

    # 检测偏好值域
    pref_vals = set()
    # 从数据集全局获取（这里用 reward_fn 的值）
    for v in sample["reward_fn"]:
        pref_vals.add(float(v))
    # 补充常见值
    pref_vals = sorted(pref_vals | {-1.0, -0.5, 0.0, 0.5, 1.0})

    # 构建历史 block（R1-R4）
    history_lines = []
    for r_idx in range(min(len(rounds) - 1, 4)):
        r = rounds[r_idx]
        opts = rounds_numpy[r_idx]
        chosen = r["user_idx"]
        history_lines.append(f"Round {r_idx + 1}:")
        for o_idx, opt in enumerate(opts):
            opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
            marker = " <-- USER CHOSE THIS" if o_idx == chosen else ""
            history_lines.append(f"  Option {o_idx}: [{opt_str}]{marker}")
        history_lines.append("")

    # 当前轮（R5）的选项
    last_round = rounds_numpy[len(rounds) - 1]
    current_lines = []
    for o_idx, opt in enumerate(last_round):
        opt_str = ", ".join(f"{features[j]}={opt[j]:.2f}" for j in range(n_features))
        current_lines.append(f"Option {o_idx}: [{opt_str}]")

    prompt = prompt_template.format(
        n_features=n_features,
        feature_names=", ".join(features),
        preference_values=str(pref_vals),
        n_history=min(len(rounds) - 1, 4),
        history_block="\n".join(history_lines),
        current_options="\n".join(current_lines),
    )
    return prompt


async def eval_preference_sample(
    client: AsyncOpenAI,
    model: str,
    sample: Dict,
    prompt_template: str,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """评估单个偏好学习样本"""
    prompt = build_preference_prompt(sample, prompt_template)
    gold_idx = sample["rounds"][-1]["user_idx"]

    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.0,
            )
            response_text = resp.choices[0].message.content or ""
        except Exception as e:
            return {
                "idx": sample["idx"],
                "gold": gold_idx,
                "predicted": -1,
                "correct": False,
                "error": f"API error: {e}",
                "code_ok": False,
            }

    # 提取并执行代码
    code = extract_code_block(response_text)
    if not code:
        return {
            "idx": sample["idx"],
            "gold": gold_idx,
            "predicted": -1,
            "correct": False,
            "error": "No code block found",
            "code_ok": False,
            "response": response_text[:500],
        }

    success, stdout, stderr = execute_python_code(code)
    if not success:
        return {
            "idx": sample["idx"],
            "gold": gold_idx,
            "predicted": -1,
            "correct": False,
            "error": f"Code execution failed: {stderr[:300]}",
            "code_ok": False,
            "code": code[:500],
        }

    # 解析输出
    try:
        predicted = int(stdout.strip().split("\n")[-1].strip())
    except (ValueError, IndexError):
        return {
            "idx": sample["idx"],
            "gold": gold_idx,
            "predicted": -1,
            "correct": False,
            "error": f"Cannot parse output: {stdout[:200]}",
            "code_ok": True,
        }

    return {
        "idx": sample["idx"],
        "gold": gold_idx,
        "predicted": predicted,
        "correct": predicted == gold_idx,
        "error": None,
        "code_ok": True,
    }


# ==========================================
# BN 推断任务
# ==========================================
def build_bn_prompt(sample: Dict, prompt_template: str) -> str:
    """构建 BN 推断的 PAL prompt"""
    return prompt_template.format(
        context=sample["contexts"],
        graph=sample["graph"],
        query=sample["query"],
    )


async def eval_bn_sample(
    client: AsyncOpenAI,
    model: str,
    sample: Dict,
    prompt_template: str,
    semaphore: asyncio.Semaphore,
) -> Dict:
    """评估单个 BN 推断样本"""
    prompt = build_bn_prompt(sample, prompt_template)
    gold = float(sample["answers"])

    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.0,
            )
            response_text = resp.choices[0].message.content or ""
        except Exception as e:
            return {
                "gold": gold,
                "predicted": None,
                "error_abs": None,
                "correct": False,
                "error": f"API error: {e}",
                "code_ok": False,
            }

    code = extract_code_block(response_text)
    if not code:
        return {
            "gold": gold,
            "predicted": None,
            "error_abs": None,
            "correct": False,
            "error": "No code block found",
            "code_ok": False,
            "response": response_text[:500],
        }

    success, stdout, stderr = execute_python_code(code)
    if not success:
        return {
            "gold": gold,
            "predicted": None,
            "error_abs": None,
            "correct": False,
            "error": f"Code execution failed: {stderr[:300]}",
            "code_ok": False,
            "code": code[:500],
        }

    # 解析输出
    try:
        # 取最后一行有效浮点数
        lines = stdout.strip().split("\n")
        predicted = None
        for line in reversed(lines):
            line = line.strip()
            try:
                predicted = float(line)
                break
            except ValueError:
                continue
        if predicted is None:
            raise ValueError("No float found")
    except (ValueError, IndexError):
        return {
            "gold": gold,
            "predicted": None,
            "error_abs": None,
            "correct": False,
            "error": f"Cannot parse output: {stdout[:200]}",
            "code_ok": True,
        }

    error_abs = abs(predicted - gold)
    return {
        "gold": gold,
        "predicted": predicted,
        "error_abs": error_abs,
        "correct": error_abs < 0.01,
        "error": None,
        "code_ok": True,
    }


# ==========================================
# 主实验循环
# ==========================================
async def run_preference_experiment(
    model: str,
    n_samples: int,
    concurrency: int,
    data_path: Path = None,
) -> Dict:
    """运行偏好学习 PAL 实验"""
    data_path = data_path or FLIGHT_DATA
    if not data_path.exists():
        print(f"  [跳过] 数据文件不存在: {data_path}")
        return {}

    # 加载 prompt 模板
    template = (PROMPT_DIR / "pal_preference.md").read_text(encoding="utf-8")

    # 加载数据
    with open(data_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]
    if n_samples > 0:
        samples = samples[:n_samples]

    print(f"\n{'='*60}")
    print(f"PAL Baseline: 偏好学习 ({data_path.stem})")
    print(f"模型: {model}, 样本数: {len(samples)}, 并发: {concurrency}")
    print(f"{'='*60}")

    client = get_client()
    sem = asyncio.Semaphore(concurrency)

    start = time.time()
    tasks = [eval_preference_sample(client, model, s, template, sem) for s in samples]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    # 统计
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    code_ok = sum(1 for r in results if r["code_ok"])
    errors = [r for r in results if r.get("error")]

    acc = correct / total if total > 0 else 0
    code_rate = code_ok / total if total > 0 else 0

    print(f"\n结果:")
    print(f"  准确率: {acc*100:.1f}% ({correct}/{total})")
    print(f"  代码执行成功率: {code_rate*100:.1f}% ({code_ok}/{total})")
    print(f"  耗时: {elapsed:.1f}s")

    # 错误分类
    error_types = {}
    for r in errors:
        err = r.get("error", "unknown")
        if "TIMEOUT" in err:
            key = "timeout"
        elif "API error" in err:
            key = "api_error"
        elif "No code block" in err:
            key = "no_code"
        elif "Code execution failed" in err:
            key = "exec_failed"
        elif "Cannot parse" in err:
            key = "parse_failed"
        else:
            key = "other"
        error_types[key] = error_types.get(key, 0) + 1

    if error_types:
        print(f"  错误分布: {error_types}")

    return {
        "task": "preference",
        "dataset": data_path.stem,
        "model": model,
        "n_samples": total,
        "accuracy": acc,
        "code_execution_rate": code_rate,
        "correct": correct,
        "error_types": error_types,
        "elapsed": elapsed,
        "details": results,
    }


async def run_bn_experiment(
    model: str,
    n_samples: int,
    concurrency: int,
) -> Dict:
    """运行 BN 推断 PAL 实验"""
    if not BLIND_DATA.exists():
        print(f"  [跳过] BLInD 数据不存在: {BLIND_DATA}")
        return {}

    template = (PROMPT_DIR / "pal_bn.md").read_text(encoding="utf-8")

    with open(BLIND_DATA, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if n_samples > 0:
        rows = rows[:n_samples]

    print(f"\n{'='*60}")
    print(f"PAL Baseline: BN 推断 (BLInD)")
    print(f"模型: {model}, 样本数: {len(rows)}, 并发: {concurrency}")
    print(f"{'='*60}")

    client = get_client()
    sem = asyncio.Semaphore(concurrency)

    start = time.time()
    tasks = [eval_bn_sample(client, model, r, template, sem) for r in rows]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    code_ok = sum(1 for r in results if r["code_ok"])

    # 计算 MAE（仅代码成功执行且可解析的样本）
    valid_errors = [r["error_abs"] for r in results if r["error_abs"] is not None]
    mae = sum(valid_errors) / len(valid_errors) if valid_errors else float("inf")

    acc = correct / total if total > 0 else 0
    code_rate = code_ok / total if total > 0 else 0

    print(f"\n结果:")
    print(f"  精确率 (|err|<0.01): {acc*100:.1f}% ({correct}/{total})")
    print(f"  MAE: {mae:.6f} (over {len(valid_errors)} valid)")
    print(f"  代码执行成功率: {code_rate*100:.1f}% ({code_ok}/{total})")
    print(f"  耗时: {elapsed:.1f}s")

    # 按 depth 分组统计
    depth_stats = {}
    for row, result in zip(rows, results):
        d = int(row.get("depth", 0))
        if d not in depth_stats:
            depth_stats[d] = {"total": 0, "correct": 0, "code_ok": 0}
        depth_stats[d]["total"] += 1
        if result["correct"]:
            depth_stats[d]["correct"] += 1
        if result["code_ok"]:
            depth_stats[d]["code_ok"] += 1

    if depth_stats:
        print(f"\n  按 depth 分组:")
        for d in sorted(depth_stats.keys()):
            s = depth_stats[d]
            dacc = s["correct"] / s["total"] if s["total"] > 0 else 0
            print(f"    depth={d}: {dacc*100:.1f}% ({s['correct']}/{s['total']})")

    error_types = {}
    for r in results:
        if r.get("error"):
            err = r["error"]
            if "TIMEOUT" in err:
                key = "timeout"
            elif "API error" in err:
                key = "api_error"
            elif "No code block" in err:
                key = "no_code"
            elif "Code execution failed" in err:
                key = "exec_failed"
            elif "Cannot parse" in err:
                key = "parse_failed"
            else:
                key = "other"
            error_types[key] = error_types.get(key, 0) + 1

    if error_types:
        print(f"  错误分布: {error_types}")

    return {
        "task": "bn",
        "dataset": "BLInD",
        "model": model,
        "n_samples": total,
        "accuracy": acc,
        "mae": mae,
        "code_execution_rate": code_rate,
        "correct": correct,
        "depth_stats": depth_stats,
        "error_types": error_types,
        "elapsed": elapsed,
        "details": results,
    }


async def main():
    parser = argparse.ArgumentParser(description="PAL Baseline 实验")
    parser.add_argument("--task", choices=["preference", "bn", "both"], default="both",
                        help="任务类型")
    parser.add_argument("--model", "-m", default="openai/gpt-4o-mini",
                        help="模型 ID (OpenRouter 格式)")
    parser.add_argument("--n", type=int, default=0,
                        help="样本数 (0=全部)")
    parser.add_argument("--concurrency", "-c", type=int, default=20,
                        help="并发数")
    parser.add_argument("--data", type=str, default=None,
                        help="自定义数据路径 (偏好学习任务)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}

    if args.task in ("preference", "both"):
        data_path = Path(args.data) if args.data else FLIGHT_DATA
        result = await run_preference_experiment(
            args.model, args.n, args.concurrency, data_path
        )
        if result:
            all_results["preference"] = result

    if args.task in ("bn", "both"):
        result = await run_bn_experiment(args.model, args.n, args.concurrency)
        if result:
            all_results["bn"] = result

    # 保存结果
    if all_results:
        model_tag = args.model.replace("/", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = RESULTS_DIR / f"pal_{model_tag}_{ts}.json"

        # 准备保存（details 可能很大，单独存）
        summary = {}
        for task_name, result in all_results.items():
            details = result.pop("details", [])
            summary[task_name] = result

            # 详细结果单独存
            detail_file = RESULTS_DIR / f"pal_{model_tag}_{task_name}_{ts}_details.jsonl"
            with open(detail_file, "w", encoding="utf-8") as f:
                for d in details:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
            print(f"\n详细结果: {detail_file}")

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n汇总结果: {out_file}")

    # 最终汇总
    print(f"\n{'='*60}")
    print("PAL Baseline 实验汇总")
    print(f"{'='*60}")
    print(f"模型: {args.model}")
    for task_name, result in all_results.items():
        acc = result.get("accuracy", 0)
        code_rate = result.get("code_execution_rate", 0)
        n = result.get("n_samples", 0)
        print(f"  {task_name}: 准确率={acc*100:.1f}%, 代码成功率={code_rate*100:.1f}%, N={n}")

    # 与 Our Method 对比
    print(f"\n对比:")
    print(f"  {'方法':<25} {'偏好学习':>10} {'BN推断':>10}")
    print(f"  {'-'*45}")
    if "preference" in all_results:
        pal_pref = all_results["preference"]["accuracy"] * 100
        print(f"  {'PAL (LLM→Python)':<25} {pal_pref:>9.1f}%")
    if "bn" in all_results:
        pal_bn = all_results["bn"]["accuracy"] * 100
        print(f"  {'PAL (LLM→Python)':<25} {'':>10} {pal_bn:>9.1f}%")
    print(f"  {'Our DSL+Compiler':<25} {'74.8%':>10} {'100.0%':>10}")
    print(f"  {'LLM baseline (no tool)':<25} {'36.6%':>10} {'~30%':>10}")


if __name__ == "__main__":
    asyncio.run(main())
