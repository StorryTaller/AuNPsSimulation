# AuNPs Simulation ver2.2

用于金纳米颗粒（AuNPs）光谱数据处理的桌面应用，覆盖 `mat -> csv` 转换、1D 光谱分析、多维参数分析、指标计算与批量导出。

## 1. 功能总览

- `格式转换`（mat -> csv）
- `光谱分析`（1D / 2D / 3D）
- `多维分析`（按参数组合查看单线或扫参曲线）
- `指标计算`：`λ`、`FWHM`、`Q`、`RIS`、`FOM`
- `导出能力`：
  - 归一化 CSV
  - 指标 Excel（含柱状图模板）
  - 图像导出（所见即所得，默认 400 DPI）
- `批处理能力`：批量导图、批量导指标
- `中英双语`：`zh_CN` / `en_US`

## 2. 技术栈与架构

- UI：`PySide6`
- 图表显示：`matplotlib`（`SpectrumChartWidget`），可选 `pyqtgraph`
- 数据处理：`numpy`、`pandas`、`scipy`、`h5py`
- Excel：`openpyxl`
- 绘图风格：`scienceplots`
- 架构：`MVVM`

目录结构（精简）：

```text
src/
├── main.py
├── models/
│   ├── file_converter.py
│   ├── spectrum_model.py
│   └── metrics_calc.py
├── viewmodels/
│   ├── mat_viewmodel.py
│   ├── viz_viewmodel.py
│   └── mda_viewmodel.py
├── views/
│   ├── main_window.py
│   ├── pages/
│   ├── dialogs/
│   ├── components/
│   └── styles/
├── utils/
└── res/translations/
```

## 3. 环境准备

### 3.1 推荐环境

- Windows 10/11
- Python 3.10+

### 3.2 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

依赖文件说明：

- `requirements.txt`：兼容入口，默认安装运行依赖。
- `requirements-runtime.txt`：运行软件所需依赖。
- `requirements-dev.txt`：开发/测试依赖，包含运行依赖与 `pytest`。
- `requirements-optional.txt`：可选依赖，例如后续启用 `pyqtgraph` 交互绘图时使用。

## 4. 启动方式

在项目根目录执行：

```bash
python src/main.py
```

应用入口会在 Windows 下优先加载系统 ICU DLL，减少 Anaconda 场景的 ICU 符号冲突问题。

### 4.1 Windows 一键打包（生成可双击启动的 EXE）

在项目根目录执行：

```bash
python packaging/build_windows.py
```

打包完成后，入口文件位于：

- `packaging/dist/AuNPsSimulation.exe`

说明：

- 这是单文件打包（`onefile`），只有一个 `AuNPsSimulation.exe`，双击即可启动。
- 首次打包会自动安装 `PyInstaller`。
- 资源文件（`src/res`）会内嵌到 exe，运行时自动解压到临时目录。
- 会额外生成分发压缩包：`packaging/dist/AuNPsSimulation.zip`（内含单个 exe）。

## 5. 快速上手（建议）

仓库内提供了可直接试用的数据：

- `data/FDTD_test/1D/mat/1D_P50.mat`
- `data/FDTD_test/nD/mat/CoreShell.mat`

### 5.1 一维/批量 mat 转换

1. 进入 `格式转换` 页面。
2. 在 `一维转换` 区域选择一个或多个 `.mat` 文件。
3. 选择输出目录。
4. 点 `扫描变量`（可选，默认可 `自动` 匹配）。
5. 点 `开始转换`。

输出：

- 主 CSV：`输出目录/<源文件名>[_光谱变量名].csv`
- 归一化 CSV：`输出目录/Ncsv/<主CSV文件名>N.csv`

### 5.2 多维 mat 转换

1. 在 `多维转换` 区域选择 `.mat` 文件。
2. 选择输出目录。
3. 点 `扫描变量`。
4. 勾选至少一个 `参数变量`。
5. 点 `开始转换`。

输出同样包含主 CSV + `Ncsv` 归一化 CSV。

### 5.3 1D 光谱分析

1. 进入 `光谱分析` 页面（analysis 选择 `1D`）。
2. 点击 `打开 csv`。
3. 切换模式：`单线 / 多线 / 三维`。
4. 可编辑图题、Y 轴标题、波长范围。
5. 使用 `导出图像` 或 `导出指标`。

### 5.4 多维分析

1. 进入 `多维分析` 页面（analysis 选择 `nD`）。
2. 点击 `打开 csv`。
3. 选择参数组合（单线），或在 `多线/3D` 下选择 `扫描参数` 与需要显示的参数取值。
4. 导出图像或指标。

## 6. 输入输出数据规范

### 6.1 转换后 CSV 结构

无论 1D 还是多维 CSV，首行是“表头行”：

- 前 N 列：波长（数值）
- 最后 1 列（1D）或最后 M 列（多维）：参数名

示意：

```text
500,501,502,...,param
0.10,0.11,0.09,...,1.33
0.15,0.14,0.12,...,1.34
```

多维示意：

```text
500,501,502,...,Radius,Thick
..., ..., ..., ...,50,10
..., ..., ..., ...,55,10
```

### 6.2 自动识别规则（mat 变量）

转换器会按关键词优先匹配变量：

- 光谱变量：`spec/spectrum/abs/ext`
- 波长变量：`lam/lambda/wave/wavelength/wl`
- 参数变量：`index/param/ri/radius/diam/height/width/period/gap/thick`

若手动指定变量名，支持完整路径、尾名、大小写不敏感匹配。

### 6.3 单位缩放规则

对波长和非 `index` 参数，内部会自动按量级转换到更易读尺度：

- `max < 1e-6` -> 乘 `1e9`
- `max < 1` -> 乘 `1e3`
- 其余保持原值

### 6.4 多维展平规则

多维光谱会把波长轴移动到最后一维后展平（Fortran 顺序），并与参数列对齐；长度不一致时会记录警告并截断到共同长度。

## 7. 指标定义

核心指标位于 `src/models/metrics_calc.py`：

- `λ`（共振波长）：峰值点波长（`argmax`）
- `FWHM`：半高宽（按半峰值并做线性插值）
- `Q`：`λ / FWHM`
- `RIS`：仅当参数名为 `index` 且至少两组数据时，`Δλ / Δn`
- `FOM`：`|RIS| / FWHM`

## 8. 导出行为说明

### 8.1 图像导出

- 页面上的 `导出图像`：导出当前可见图像（WYSIWYG），默认 `400 DPI`
- 若目标扩展名不是 `.png`，会自动改为 `.png`
- `dpi` 最小限制为 `72`

### 8.2 批量导图命名

1D 光谱分析批量导图：

- `single`：`<csv文件名>_<参数名=参数值>.png`（每条曲线一张）
- `multi`：`<csv文件名>_<参数名-2d>.png`
- `3d`：`<csv文件名>_<参数名-3d>.png`

多维分析批量导图：

- `single`：`<csv文件名>_<扫描参数=参数值>.png`
- `multi/3d`：`<csv文件名>_<扫描参数>-2d|3d.png`

### 8.3 指标导出

- 单文件导出：`.xlsx`
- 批量导出：输出目录下 `Excel/` 子目录
- 1D 指标导出会尽量复用模板：`src/res/icons/example_single_i.xlsx`

## 9. 批量功能

两类页面都支持“批量分析”弹窗：

- `导出图像`
- `导出指标`

默认模式：

- 1D 批量默认 `multi`
- 多维批量默认 `single`

日志区会显示每个文件处理结果与总成功/失败统计。

## 10. 测试

开发/验证环境先安装：

```bash
python -m pip install -r requirements-dev.txt
```

若仓库中包含 `tests/`，运行：

```bash
pytest -q
```

建议测试覆盖关键流程：

- 单文件 mat 转换 + 指标 Excel 结构检查
- 打开 csv 不产生额外文件
- 多维 mat 转换与扫参读取
- 批量导图/导指标
- 图像导出 DPI 差异
- 批量对话框默认模式

## 11. 常见问题

### 11.1 3D 模式没有图

3D 需要“数值型参数”；若参数列是文本或无法转数值，会回退/报提示。

### 11.2 选择波长范围后无图

当范围内没有任何波长点会提示“当前波段范围内无可显示数据”，点击 `全谱` 可恢复。

### 11.3 批量转换失败

优先检查：

- 多个 mat 文件的变量结构是否一致
- 手动指定变量名是否存在于每个文件
- 输出目录是否可写

## 12. 开发与维护建议

- 代码遵循 MVVM：`models` 纯计算、`viewmodels` 编排、`views` 渲染
- 新增界面文案请同步到 `src/res/translations/*.json`
- 新增核心逻辑建议补充 `tests/`

---

如需继续扩展 ver2.2（例如“最优传感”页面），建议先在 `viewmodels + models` 层定义稳定数据契约，再接入页面层，便于复用现有批量导出链路。
