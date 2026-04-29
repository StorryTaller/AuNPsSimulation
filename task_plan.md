# Task Plan: 多线光谱按参数值选择显示

## Goal
在多线光谱模式下新增参数值选择能力，使用户可只显示被选中的参数对应光谱，并让图例与显示曲线严格一致。

## Current Phase
Phase 5

## Phases
### Phase 1: 项目探索与需求确认
- [x] 了解用户目标与限制（仅中文回复）
- [x] 定位相关模块（model/viewmodel/view）
- [x] 记录当前发现到 findings.md
- **Status:** complete

### Phase 2: 澄清问题（一次一个）与方案比较
- [x] 提出单个关键澄清问题
- [x] 给出 2-3 种可行方案与取舍
- [x] 确认推荐方案
- **Status:** complete

### Phase 3: 设计确认（先设计后实现）
- [x] 输出设计（数据流、UI、错误处理、测试点）
- [x] 获得用户确认
- **Status:** complete

### Phase 4: 代码实现
- [x] 增加参数值多选控件
- [x] 接入 viewmodel 过滤逻辑
- [x] 保证图例/导出与过滤结果一致
- **Status:** complete

### Phase 5: 验证与交付
- [x] 运行最小验证（手动或自动）
- [x] 记录测试结果与风险
- [x] 交付变更说明
- **Status:** complete

## Key Questions
1. （已确认）筛选影响范围：2D/3D/导出是否都联动？
2. （已确认）当扫描参数值一个都不选时如何处理？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| 仅扫描 `src` 目录并排除 `packaging/.venv_build` | 避免第三方库噪声，快速定位真实业务代码 |
| 相关改动聚焦 `spectrum_model.py` / `mda_viewmodel.py` / `mda_page.py` | 这三层覆盖数据选择、绘图载荷生成与界面交互 |
| 筛选作用域按“2D+3D+导出”统一联动 | 用户已明确选择 3，要求所见即所得 |
| 空选择时不输出并提示错误/警告，且采用最低开销实现 | 用户要求“消耗最低、速度最快”，避免复杂回退逻辑与额外计算 |
| 本轮先不改批量导出对话框的多选值 UI | 用户同意“先做当前页面链路”，以更快交付 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg.exe` 无法执行（拒绝访问） | 1 | 改用 PowerShell `Get-ChildItem` + `Select-String` |
| 当前目录非 git 仓库 | 1 | 跳过 recent commits 检查，继续基于文件结构分析 |
| 设计文档无法执行 git 提交 | 1 | 先保存文档并继续流程，待用户确认后直接进入实现 |

## Notes
- 当前严格遵循 `$brainstorming`：先设计并获得确认，再进入实现。
