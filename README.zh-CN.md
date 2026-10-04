# LayoutEditor-skill

[English](README.md) | **简体中文**

一个 [Agent Skill](https://agentskills.io)：通过 **[juspertor LayoutEditor](https://layouteditor.com)** 的 LayoutScript Python 接口无界面生成、准备、拼版与验证掩模版图。你的编程 Agent 可以编写参数化生成脚本、导出 GDSII/OASIS/DXF、跑设计规则与物理验证、做晶圆级多芯片拼版，以及执行图层布尔运算。

v0.2 覆盖四个主要场景（按日常使用频次排列）：
1. **版图数据准备与图层运算**：版图结构与图层统计检查、GDS/DXF/OASIS 格式互转、图层编号重映射、多 GDS 命名空间安全合并，以及批量图层布尔与尺寸外扩。
2. **硅基光电子回路（PIC）**：直波导、余弦 S 弯、欧拉弯头、定向耦合器、微环谐振器、MZI 滤波器与光纤光栅耦合器。
3. **晶圆与标线版拼版（Wafer Assembly）**：多芯片排布、划片槽生成、划片道十字对准标记与硅片面积使用率核算。
4. **MEMS 与微机械掩模**：参数化悬臂梁、梳齿执行器、隔离环，以及离线 DRC、电学连通与机械释放验证。

- 与具体 Agent 无关：遵循开放的 [Agent Skills 规范](https://agentskills.io/specification)，适用于 Claude Code、Cursor、Codex、OpenCode、GitHub Copilot、Cline 等兼容 Agent。
- 可以用 `npx skills` 一条命令安装，也可以直接复制文件夹。

> 本项目与 juspertor GmbH 无关联。LayoutEditor 是商业软件，请到官方下载并遵守其许可；本 skill 只负责自动化操作它。

<p align="center">
  <img src="assets/v0.2_showcase_grid.png" alt="LayoutEditor-skill 四大场景版图概览缩略图" width="100%" />
</p>

---

## 1. 安装 skill

### 方式 A：`npx skills`

需要 Node.js。使用开源的 [skills CLI](https://github.com/vercel-labs/skills)：

```bash
npx skills add laull9/LayoutEditor-skill
```

默认装到当前项目；加 `-g` 为全局安装：

```bash
npx skills add laull9/LayoutEditor-skill -g
```

指定具体 Agent 非交互安装：

```bash
npx skills add laull9/LayoutEditor-skill -g -a claude-code -a cursor -y
```

### 方式 B：手动克隆

把整个仓库克隆到 Agent 的 skills 目录，文件夹名保持 `LayoutEditor-skill`（与 `SKILL.md` 的 `name` 字段一致）：

| Agent | 用户级位置 | 项目级位置 |
|---|---|---|
| Claude Code | `~/.claude/skills/LayoutEditor-skill` | `<项目>/.claude/skills/LayoutEditor-skill` |
| 通用约定 Agent | `~/.agents/skills/LayoutEditor-skill` | `<项目>/.agents/skills/LayoutEditor-skill` |
| 其他 | 参考对应 Agent 的 skills 目录说明 | |

```bash
git clone https://github.com/laull9/LayoutEditor-skill ~/.claude/skills/LayoutEditor-skill
```

## 2. 安装 LayoutEditor

LayoutEditor 官网：<https://layouteditor.com>。

1. 打开官方下载页 **<https://layouteditor.com/download.html>**。下载前需要勾选出口管制声明。
2. 按操作系统选择安装包：
   - macOS：`layout-<版本>-macOS-universal.dmg`，将 `layout.app` 拖入 `/Applications`。如果 Gatekeeper 拦截，执行 `xattr -d com.apple.quarantine /Applications/layout.app`。
   - Windows 64 位：`layout-<版本>-win-64bit-installer.msi`（或免安装 zip）。
   - Linux：`layout-<版本>-Linux.x86_64.AppImage`，或 `.deb` / `.rpm`。
3. 版本说明：免费版可以运行脚本、进行 DRC 与小规模设计导出。付费版解除元素量与布尔引擎的导出限制。
4. 检查自带 Python 路径：

   ```bash
   scripts/find_layouteditor.sh
   ```

   正常输出类似 `/Applications/layout.app/Contents/MacOS/Frameworks/Python.framework/Versions/3.14/bin/python3.14`。

## 3. 分析与渲染依赖

分析与离线渲染脚本需要标准 Python 3.8+ 环境，并安装 numpy、Pillow、matplotlib：

```bash
python3 -m pip install numpy pillow matplotlib
```

## 4. 实例与快速体验

仓库提供了覆盖四大场景的独立实例：

### 实例 1：版图数据准备与图层布尔运算（Data Prep）

执行版图检查、GDS 转 DXF、图层编号重映射、双芯片左右合并（无命名冲突）与图层布尔差集及外扩：

```bash
examples/mask_prep/run_prep_demo.sh /tmp/le_prep
```

输出 `converted.dxf`、`remapped.gds`、双芯片合并版图 `dual_merged.gds` 以及图层布尔结果 `boolean_result.gds`。

<p align="center">
  <img src="assets/prep_dual_chip.png" width="100%" alt="多 GDS 芯片合并拼合切片图" />
</p>

左右两颗芯片独立命名空间重命名（`LEFT_` / `RIGHT_`），平移并入顶层单元，排除单元命名冲突。

### 实例 2：硅基光电子集成回路（PIC）

生成包含非对称 MZI 滤波器、微环谐振器、欧拉弯头与光纤光栅耦合器的光子测试芯片：

```bash
examples/photonic_circuit/run_pic_demo.sh /tmp/le_pic
```

输出 `pic_chip.gds` 以及 MZI 耦合区、环形腔 200 nm 缝隙和欧拉弯头切片预览。

<p align="center">
  <img src="assets/pic_mzi_filter.png" width="49%" alt="MZI 滤波器与 S 弯波导切片" />
  <img src="assets/pic_ring_coupler.png" width="49%" alt="微环谐振器 200 nm 耦合间隙切片" />
</p>

左图显示 MZI 滤波器的余弦 S 弯波导与定向耦合器，右图显示微环谐振器的 200 nm 亚微米耦合间隙。

### 实例 3：晶圆与标线版多芯片拼版（Wafer Assembly）

将芯片阵列排布进 26 mm 标线版视场，自动生成 100 µm 划片槽与十字对准标记，核算硅片使用率：

```bash
examples/wafer_assembly/run_assembly.sh /tmp/le_wafer
```

输出 `reticle_assembly.gds` 与拼版报告（放置 89 颗芯片，面积使用率 67.1%）。

<p align="center">
  <img src="assets/wafer_assembly.png" width="100%" alt="26 mm 标线版 89 芯片阵列与划片槽道拼版图" />
</p>

标线版内排布 89 颗测试芯片，包含四周 100 µm 划片道、交叉处十字对准标记与芯片标签。

### 实例 4：4 掩模 SOI-MEMS 测试芯片（MEMS 实例）

运行微机械芯片生成、DRC 规则检查、栅格连通性与机械释放分析：

```bash
examples/mems_comb_drive/run_mems.sh /tmp/le_demo
```

也可以调用根目录兼容脚本：`examples/run_demo.sh /tmp/le_demo`。

<p align="center">
  <img src="assets/demo_core_overview.png" width="100%" alt="demo_chip 驱动中心区版图排布" />
</p>

梭体、悬臂梁、梳齿执行器与电极岛排布。避开布尔运算，直接用解析几何生成 R15 圆角与微米级等间隙梳齿。

<p align="center">
  <img src="assets/demo_verification.png" width="100%" alt="DRC 与连通性验证报告截图" />
</p>

drcTool 检查规则 0 处违规，离线连通性与绝缘测试全部 PASS。

## 5. 命令行工具用法

除了调用完整实例，也可以直接使用各个脚本：

```bash
LE_PY="$(scripts/find_layouteditor.sh)"

# 1. 版图结构检查
"$LE_PY" scripts/layout_prep.py inspect my_chip.gds

# 2. 格式转换（GDS -> DXF / OASIS / CIF）
"$LE_PY" scripts/layout_prep.py convert my_chip.gds my_chip.dxf

# 3. 图层重映射
"$LE_PY" scripts/layout_prep.py remap my_chip.gds remapped.gds mapping.json

# 4. 多 GDS 合并
"$LE_PY" scripts/layout_prep.py merge merge_spec.json merged.gds TOP_CELL

# 5. 晶圆/标线版拼版
"$LE_PY" scripts/wafer_assembly.py wafer_cfg.json wafer.gds report.txt

# 6. 图层布尔与尺寸外扩
"$LE_PY" scripts/layer_boolean.py in.gds out.gds bool_ops.json TOP_CELL

# 7. DRC 规则检查
"$LE_PY" scripts/drc_check.py out.gds MY_TOP rules.json drc.txt

# 8. 栅格连通性与释放检查
python3 scripts/check_connectivity.py out_polys.json probes.json nets.txt

# 9. 离线多层与局部切片渲染
python3 scripts/render_preview.py out_polys.json preview/ views.json
```

## 6. 目录结构

```
LayoutEditor-skill/
├── SKILL.md                          # Agent 入口（v0.2 规范与规则）
├── scripts/
│   ├── le_helpers.py                 # 基础几何工具、LE 会话封装与布尔接口
│   ├── photonic_helpers.py           # 硅光原语（直波导、S弯、欧拉弯头、MZI、环形腔、光栅）
│   ├── layout_prep.py                # 版图检查、格式转换、图层重映射、多 GDS 合并
│   ├── wafer_assembly.py             # 晶圆/标线版拼版、划片槽、对准标记与使用率统计
│   ├── layer_boolean.py              # 图层布尔运算（并/交/差/异或）与尺寸外扩
│   ├── drc_check.py                  # 按 JSON 规则表调用 LayoutEditor drcTool
│   ├── check_connectivity.py         # 栅格法网表、电学绝缘与释放分析
│   ├── render_preview.py             # PNG 离线预览与切片渲染
│   └── find_layouteditor.sh          # 定位 LayoutEditor 自带的 Python
├── examples/
│   ├── mask_prep/                    # 实例 1：数据准备、格式转换、GDS合并与图层布尔
│   │   └── run_prep_demo.sh
│   ├── photonic_circuit/             # 实例 2：硅基光电子测试芯片（MZI、微环、欧拉弯头）
│   │   ├── pic_chip.py
│   │   ├── pic_views.json
│   │   └── run_pic_demo.sh
│   ├── wafer_assembly/               # 实例 3：多芯片拼版与划片槽
│   │   ├── wafer_config.json
│   │   └── run_assembly.sh
│   ├── mems_comb_drive/              # 实例 4：4 掩模 SOI-MEMS 梳齿驱动器测试芯片
│   │   ├── demo_chip.py
│   │   ├── demo_drc_rules.json
│   │   ├── demo_probes.json
│   │   ├── demo_views.json
│   │   └── run_mems.sh
│   ├── demo_chip.py                  # 根级向后兼容入口
│   └── run_demo.sh                   # 根级向后兼容一键运行脚本
└── references/                       # 详细技术参考
    ├── data-prep-and-assembly.md     # 版图清洗、合并与晶圆拼版规范
    ├── boolean-workflow.md           # 图层布尔与外扩操作指引
    ├── photonic-layout.md            # 硅光波导数学原理与器件设计
    ├── geometry-techniques.md        # 无布尔运算画圆角、沟槽环与 keyhole 多边形
    ├── mems-soi-process.md           # SOI-MEMS 工艺与规则约定
    ├── verification.md               # 验证流程与检查清单
    ├── layoutscript-api.md           # 实测 API 签名与行为细节
    ├── free-version-limits.md        # 免费版导出门槛实测与应对策略
    └── troubleshooting.md            # 常见故障排除
```

## 7. 实测要点

- 数据库单位：1 dbu = 1 nm，辅助函数统一以 µm 传参。
- 旋转方向：LayoutScript 的 `strans.rotate()` 顺时针旋转，`LE.ref(..., ang)` 统一使用逆时针角度并自动换算。
- 免费版导出限制：单会话元素数超过 8000 至 10000，或执行布尔与外扩后，GDS 导出会被阻止（写出云端格式 `.lec`）。无商业许可时，生成脚本建议使用解析几何画法；图层布尔脚本建议在中间分析或有商业许可的环境下执行。
- 阵列：`addCellrefArray` 仅一维阵列（`ny = 1`）位置稳定，二维阵列建议按行放置。
- 预览渲染：无界面环境下自带截图为空白，离线渲染统一读取导出的 JSON 几何点集。

## 许可证

[MIT](LICENSE) © 2026 laull9
