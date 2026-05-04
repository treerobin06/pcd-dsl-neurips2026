"""pgmpy 0.1.26 在 mac 上 xgboost 缺 libomp.dylib 时 hang 修复 (2026-04-27)

诊断:
- pgmpy 0.1.26 的 CausalInference.py → estimators/__init__.py → MmhcEstimator
  → CITests.py 强制 `from xgboost import XGBClassifier, XGBRegressor`
- xgboost 加载 libxgboost.dylib 时需要 libomp.dylib（macOS OpenMP runtime）
- 未装 libomp（brew install libomp）时 xgboost.core._load_lib() 抛 XGBoostError
- 我们只需要 pgmpy.inference.VariableElimination + pgmpy.utils.get_example_model，
  不需要 CausalInference 也不需要 estimators 整套。但 pgmpy.inference.__init__.py
  顶层就 import CausalInference → 整个 pgmpy.inference import 失败
- 不修：bnlearn 真实网络实验跑不了（论文 Section 5.4 + Figure 3a 核心证据）

修复策略: monkey-patch sys.modules 注入 xgboost stub，让 import 链满足。
不影响 VE / get_example_model / BIFReader 的正确性（它们不调 xgboost）。

使用: run_bnlearn_held_out.py / verify_bnlearn_dsl_100.py 等需要 pgmpy 的
脚本顶部 `import _pgmpy_compat  # noqa` 即可（必须在 import pgmpy 之前）。
"""

import sys
import types

if "xgboost" not in sys.modules:
    _fake_xgboost = types.ModuleType("xgboost")

    class _Stub:
        def __init__(self, *a, **kw):
            pass

        def fit(self, *a, **kw):
            return self

        def predict(self, *a, **kw):
            return None

    _fake_xgboost.XGBClassifier = _Stub
    _fake_xgboost.XGBRegressor = _Stub
    _fake_xgboost.DMatrix = _Stub
    _fake_xgboost.train = lambda *a, **kw: None

    sys.modules["xgboost"] = _fake_xgboost


# 自检
if __name__ == "__main__":
    import time

    t = time.time()
    from pgmpy.utils import get_example_model
    from pgmpy.inference import VariableElimination

    print(f"[_pgmpy_compat smoke] pgmpy import: {time.time()-t:.2f}s")

    t = time.time()
    m = get_example_model("asia")
    ve = VariableElimination(m)
    r = ve.query(["lung"], evidence={"asia": "yes"})
    print(f"[_pgmpy_compat smoke] asia VE query: {time.time()-t:.2f}s")
    print(f"  P(lung|asia=yes) yes={r.values[0]:.4f} no={r.values[1]:.4f}")
    print("PASS")
