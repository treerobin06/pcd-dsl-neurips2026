"""
dsl/macros/ — 本目录是 self-evolving library 的 manifest 目录（vision sketch）。

每个 .py 文件是一个 macro manifest，含 METADATA dict + fn callable。
dsl.macros_library._scan_registry() 启动时自动扫描 dsl/macros/*.py 加载所有 manifest。

⚠️ vision sketch — 未连接主流程。详见 ../macros_library.py。
"""
