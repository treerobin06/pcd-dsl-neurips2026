# 论文目录规则

## Overleaf 同步

论文与 Overleaf 项目保持双向同步。

**同步配置**：
- Overleaf 项目 ID: `69b6b3ef97c780fd88673a80`
- Git URL: `https://git:TOKEN@git.overleaf.com/69b6b3ef97c780fd88673a80`
- 本地同步目录: `paper/overleaf-sync/`（已在 .gitignore 中）
- 同步脚本: `paper/sync_overleaf.sh`
- 同步文件: `main.tex`, `references.bib`, `neurips_2026.sty`

**强制规则**：
1. **修改论文前**：先执行 `bash paper/sync_overleaf.sh pull`，拉取 Overleaf 上的最新改动
2. **修改论文后**：执行 `bash paper/sync_overleaf.sh push`，推送到 Overleaf
3. 每次 push 后，在下方同步日志中追加一行记录

## 同步日志

格式: `- [YYYY-MM-DD HH:MM] push/pull | 变更摘要`

- [2026-03-15 21:30] push | 初始同步：完整论文上传到 Overleaf
- [2026-03-15 21:35] sync | 测试双向同步，无变更
- [2026-03-15 21:53] push | 修复 Figure 3: legend 移至底部，加 Direct Answer 柱子，增加高度
- [2026-03-15 22:16] push | 页面压缩 10.3→9.0: Table2+Fig2并排, Fig3+Fig4并排, Table1移appendix, 文字精简
- [2026-03-18 18:00] push | 去AI味: 缩写首次出现全拼(LLM/DSL/BN/CPT/CoT/PAL/PGM/PPL/MAP/LOO/NB/HMM/VE), 减少括号和破折号过度使用
- [2026-03-18 18:06] push | 格式规范化: CI全拼, Tab→Table统一, OOD→全拼, 添加todocounter定义, BN去重复定义
- [2026-03-18 18:32] push | 新增 Appendix I: Prompt Templates (PCD BN/Preference parse/compute/decide + Inductor 说明)
- [2026-03-18 18:35] push | 新增5个附录section: Inductor Reliability+LOO详表, Cost Accounting, Compile-time失败分析, 多模型PCD详细结果, DeLLMa边界条件; 删除空头承诺语句
- [2026-03-18 18:44] push | 扩充App C: 23策略完整表格(14行精选) + Content×Channel 2D消融矩阵 + 关键发现段落
- [2026-03-18 19:16] push | 语言/格式审查修改(Codex+3 Claude): 删反问修辞, 削弱overclaim, 去slogan化caption, 修Limitations矛盾, CI格式统一, reweighed→reweighted
- [2026-03-18 19:20] push | 格式修复: BN/DSL body重新定义, PPL顺序修正, 删qxy双盲风险, 删死label; 新增Related Work段(ToT+Autoformalization)
- [2026-03-18 19:50] push | 故事重构(Codex讨论后): Abstract加入bnlearn scaling, Intro突出weakest=strongest+bnlearn, Contributions从3条压成2条(系统+诊断证据)
- [2026-03-18 19:56] push | 恢复depth曲线为原始版本(去掉Parse带)
- [2026-03-18 20:00] push | 重写Appendix I Prompt Templates: verbatim墙→总结表+2个framed box, 省1页
- [2026-03-18 20:09] push | 加入理论公式: PCD形式化(Eq1-3), family-level induction objective(Eq4), DSL program space(Eq5), compiler equivalence(Eq6), cost break-even(Eq7)
- [2026-03-25 10:30] push | 新增 Section 6 "End-to-End Pipeline Validation": E2E 74.3%≈Gold 74.4%, Intro加一句引用
- [2026-03-28 16:00] push | NeurIPS结构审查: Abstract首句改为evidence-led, Contribution#2删DeLLMa细节, E2E从Analysis移入Experiments, Limitations从4段压到3段(合并Statistical Reporting), Related Work合并最后两段为一段, S5.2加claim声明
- [2026-03-28 16:30] push | 第二轮修复: 删line1中文乱码, \bigtimes fallback定义, Abstract 3%→3-11%统一, 27-70%→27-65%数据修正, Contribution#1从5行压到2行
- [2026-03-28 03:37] push | Prose polish L243-658 (PCD/Method/Experiments): 30处修改, 去冗余/紧凑语言/修复vague referent/强化transitions

## 论文概况

- **标题**: Compile Once, Reason Exactly: Verified Solver Induction for LLM Probabilistic Reasoning
- **目标会议**: NeurIPS 2026
- **主文件**: `main.tex`（主文 9 页 + references + appendix）
- **引用**: `references.bib`
- **审查报告**: `CODEX_REVIEW.md`

## 写作规范

- NeurIPS 2026 格式，使用 `neurips_2026.sty`
- 主文不超过 9 页（不含 references 和 appendix）
- 修改后必须 `pdflatex` 编译验证无错误
- 修改论文内容后，同时更新 `CODEX_REVIEW.md` 中的修改记录
