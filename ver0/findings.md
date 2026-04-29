# Findings & Decisions

## Requirements
- 用户希望在“多线光谱”里支持按参数值筛选显示。
- 示例：参数 `a=1,2,3` 时，若选择 `1` 和 `3`，图中只显示两条曲线。
- 图例需同步，仅显示被选择参数值的条目。
- 回复语言限制：中文。
- 用户确认筛选影响范围为：多线 2D、3D、导出结果都联动。
- 用户确认空选择时可“不输出或报错”，并要求优先最低消耗、最快实现路径。

## Research Findings
- 核心目录在 `src/`，其中与多线光谱最相关：
  - `src/models/spectrum_model.py`
  - `src/viewmodels/mda_viewmodel.py`
  - `src/views/pages/mda_page.py`
  - `src/views/components/charts.py`
- `spectrum_model.py` 已有按 sweep 取多条曲线的数据接口（含 `picked_values`）。
- `charts.py` 的 2D 绘图按 `labels` 生成图例，具备图例同步基础条件。
- 当前 `MultiDimSpectrumDataset.get_sweep()`（`spectrum_model.py`）会在固定参数条件下返回“该扫描参数的全部唯一值”对应曲线，不支持“只取部分值”。
- 当前 `MdaViewModel.plot_sweep()`（`mda_viewmodel.py`）直接把 `get_sweep()` 的全部结果组装为 `labels`，因此图例天然是“全量值”。
- 当前 `MdaPage._sweep_selection()`（`mda_page.py`）仅确定 `vary=params[0]` 与 `fixed`，没有“扫描参数值多选”的 UI 或请求参数。
- 当前导出链路（`_collect_metrics_rows`、`_save_sweep_plot`、`_export_plots_for_dataset`）都基于 `dataset.get_sweep(vary, fixed)` 全量结果，尚未接收“已选参数值”。
- 批量导出入口当前无法传递页面勾选值；用户同意本轮不扩展该 UI。
- 已完成实现：
  - `mda_page.py` 增加扫描参数取值复选列表（默认全选），空选择时阻止绘图/导出。
  - `mda_viewmodel.py` 在实时绘图、指标导出、图片导出链路透传 `selected_values`。
  - `spectrum_model.py:get_sweep` 支持 `selected_values` 过滤并处理空过滤结果。
  - 中英文翻译新增 `mda.sweep_values`、`mda.sweep_values_hint`、`mda.message.select_sweep_values`。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 先做“参数值过滤后再下发绘图 payload” | 能同时保证曲线和图例一致，改动点清晰 |
| 过滤逻辑优先放在 ViewModel 或 Model 层 | 避免视图层手工切片，保持职责清晰 |
| 优先复用现有复选列表交互模式 | `mat_page.py` 已有 `QListWidget + QCheckBox` 实现，可降低 UI 风险与维护成本 |
| 导出结果遵循当前筛选状态 | 用户选定“2D/3D/导出统一联动” |
| 空选择采用“阻止绘图/导出 + 提示信息” | 实现最轻量，避免回退全选带来的隐式行为与额外处理成本 |
| 先完成设计文档并等待确认，再实施代码 | 遵循 `$brainstorming` 流程门禁 |
| 空选择时先清空图表 payload，再提示 | 避免用户误导出旧图，满足“不输出”约束 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| 文件扫描被虚拟环境噪声淹没 | 排除 `packaging/.venv_build` 后重新扫描 |
| `rg` 不可用 | 切换 PowerShell 原生命令 |
| 当前目录不是 git 仓库，无法执行“提交设计文档” | 记录问题后继续推进本地文档与实现流程 |
| PowerShell 不支持 `python - <<'PY'` heredoc 语法 | 改用 `@'... '@ | python -` 执行内联脚本 |

## Resources
- `E:\Code\VSCode\Python\Software\AuNPsSimulation\ver0\src\models\spectrum_model.py`
- `E:\Code\VSCode\Python\Software\AuNPsSimulation\ver0\src\viewmodels\mda_viewmodel.py`
- `E:\Code\VSCode\Python\Software\AuNPsSimulation\ver0\src\views\pages\mda_page.py`
- `E:\Code\VSCode\Python\Software\AuNPsSimulation\ver0\src\views\components\charts.py`
- `E:\Code\VSCode\Python\Software\AuNPsSimulation\ver0\docs\superpowers\specs\2026-04-24-mda-sweep-value-filter-design.md`

## Visual/Browser Findings
- 本轮未使用浏览器或图像工具。
