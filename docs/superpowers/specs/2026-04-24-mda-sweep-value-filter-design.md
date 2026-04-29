# MDA 多线/3D 按参数值筛选设计

## 1. 背景
当前多维光谱分析（MDA）在 `multi/3d` 模式下，会默认绘制扫描参数的全部唯一取值对应曲线。用户希望可手动选择扫描参数的部分取值（例如仅 `a=1,3`），并让图例与导出结果严格同步该选择。

## 2. 目标
- 在 MDA 页面为扫描参数提供“取值多选”能力。
- 勾选哪些值，就只绘制/导出哪些值对应的光谱。
- 影响范围统一到 `multi(2D)`、`3d`、指标导出与图片导出（当前页面）。
- 空选择时阻止输出，并给出提示。

## 3. 非目标
- 本次不扩展批量导出对话框（`MdaBatchDialog`）的“参数值多选 UI”。
- 不改变现有单线（`single`）模式行为。

## 4. 方案选择
采用“模型层统一过滤 + 页面层多选控件”的最小改动方案：
- 在 `MultiDimSpectrumDataset.get_sweep(...)` 增加可选参数 `selected_values`。
- 所有 sweep 链路（绘图/3D/导出）统一透传该参数，避免各处重复过滤。
- 页面层维护扫描参数值复选列表，默认全选，空选直接阻止请求。

该方案改动少、复用高、性能开销低，且能保证行为一致。

## 5. 改动范围
- `src/views/pages/mda_page.py`
  - 新增扫描参数值复选列表 UI。
  - 在 `multi/3d` 模式下采集勾选值并传递给 `viewmodel.plot_sweep(...)`。
  - 导出指标时同样传递勾选值。
  - 空选择时提示并停止触发。
- `src/viewmodels/mda_viewmodel.py`
  - `plot_sweep(...)` 增加 `selected_values` 入参并透传至数据层。
  - `_collect_metrics_rows(...)`、`_export_metrics_for_dataset(...)`、`_save_sweep_plot(...)` 等 sweep 路径增加透传。
  - 与当前页面导出一致联动筛选值。
- `src/models/spectrum_model.py`
  - `get_sweep(...)` 增加 `selected_values` 过滤逻辑。
  - 空过滤结果抛出明确异常。
- `src/res/translations/zh_CN.json`、`src/res/translations/en_US.json`
  - 补充“扫描参数值”“至少选择一个参数值”等文案键。

## 6. 数据流
1. 页面根据当前 `varying_param` 展示该参数全部可选值，默认全选。
2. 用户改变勾选后，页面收集 `selected_values`。
3. 页面调用 `plot_sweep(vary, fixed, mode, selected_values)`。
4. `viewmodel` 透传到 `dataset.get_sweep(vary, fixed, selected_values)`。
5. `dataset` 先按 `fixed` 过滤，再按 `selected_values` 过滤，返回波长、光谱矩阵、值列表。
6. `viewmodel` 基于返回值生成：
   - 2D 图 `labels`
   - 3D 图 `param_values`
   - 指标计算与导出行
   保证与当前勾选集一致。

## 7. 交互与错误处理
- 默认行为：首次进入 sweep 模式时自动全选扫描参数所有值。
- 空选择：
  - 页面直接提示“请至少选择一个参数值”。
  - 不更新图，不执行导出。
- 数据层兜底：
  - 若透传值全部无效或过滤后为空，抛出“未找到可绘制的光谱”类错误，供上层提示。

## 8. 性能与复杂度
- 过滤操作仅在当前已匹配数据子集上做集合包含判断，复杂度线性。
- 通过模型层统一过滤，避免多处重复切片与重复转换，减少维护和运行开销。
- 不引入新线程或重型依赖。

## 9. 验证计划
- 功能验证：
  - 扫描参数 `a=1,2,3`，只选 `1,3`，2D 仅 2 条曲线，图例仅 2 项。
  - 切到 3D，仅显示 2 条对应曲线。
  - 导出指标与导出图片仅包含已选值。
- 边界验证：
  - 全部取消勾选时，出现提示且不输出。
  - 勾选全部时行为与旧版一致。
- 回归验证：
  - `single` 模式无行为变化。
  - 批量导出入口保持当前行为（不受本次 UI 影响）。

## 10. 实施顺序
1. 扩展模型层 `get_sweep` 签名与过滤逻辑。
2. 扩展 viewmodel sweep 链路透传参数。
3. 在页面加入复选 UI 与状态同步。
4. 接入导出入口参数透传。
5. 补充文案键并执行手工验证。
