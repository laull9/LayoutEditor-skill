# LayoutEditor 需求覆盖评估

评估日期：2026-10-05。依据当前代码、五组本机运行示例、原生契约测试和厂商文档。

这个 skill 现在覆盖了脚本化版图工作里最常见的几类需求：读懂和清理已有文件
（layer/datatype、单位、多 top）、按工艺描述画图、DRC、原生网表提取与 LVS、拼版和格式转换。
它仍然不是完整的 IC 设计环境：原理图编辑、PCell、OpenAccess 库和 foundry 签核 deck 不在
脚本流程里。没有用户任务分布数据，因此不给覆盖百分比。

| 用户要做什么 | 当前交付能力 | 仍缺什么 |
|---|---|---|
| 看 GDS 层次、图层、范围 | `inspect`：按 `layer/datatype` 统计，引用单独计数，列出候选 top，`--top` 选择 | 属性（PROPATTR）审计 |
| 对照工艺检查文件 | `audit`：DBU、未声明的层对、未使用层、离网格顶点/引用 | 按区域或按 cell 的报告 |
| 单位不一致 | `normalize-dbu`：逐 cell resize 后改 DBU，校验范围；非整数倍默认拒绝 | 文本 magnification 会随之缩放；非 GDS 格式未单独测 |
| 图层映射、筛选 | `remap`：成对 `L/D` 与仅层号两种键，引用不删，原子写，可原地改写 | — |
| 转 GDS/OASIS/DXF | OASIS 几何独立复核；DXF 只验证写出 | DXF 文本/路径/层次回读；CIF、Gerber 案例 |
| 多文件合并 | 先加前缀再导入；冲突和缺 top 会失败 | 非 1 nm 源需先 normalize |
| PDK / 工艺描述 | JSON 技术文件：层表、单位、导体/via 堆叠、器件识别、DRC 规则；`pdk_tool.py` 校验、导入文本 layer map、生成 DRC 规则、跨工艺映射；`LE(tech=...)` 按层名绘图 | 厂商加密 `.ltgz` 包和 PCell 只能在 GUI 使用；OpenAccess 未接入 |
| 器件提取、网表与 LVS | 原生 `extractComponent`/`buildConnect`/`extractNetList`；MOS 与薄膜电阻实测；对照 SPICE 的拓扑 LVS，NAND2 good/short/open 三例 | 器件尺寸（W/L、R）不比较；寄生参数；原生 `layoutVersusNetlist` 在无界面 SPICE 导入下不可用 |
| 布尔运算、尺寸偏置 | 有 CLI 和厂商 API 对照 | 商业授权下的端到端导出回归 |
| 小型 reticle / wafer 拼版 | 矩形 reticle 混排 25 个 die；间距独立检查 | 紧凑排布、旋转、flat/notch、stepper 字段 |
| MEMS 掩模 | 参数化生成、9 条 DRC、栅格连通性与释放检查 | 用户工艺、材料与 FEM 验收 |
| PIC 版图 | MZI/ring、两层光栅、Euler 弯曲、3 条尺寸规则 | PDK 单元/端口库、光学仿真 |
| 完整 foundry DRC | JSON runner 支持 6 种规则；技术文件可按层名写规则 | 密度、填充、天线、`.ledrc`、区域/层次检查 |
| PCB、RF、制造格式 | 几何工具可辅助 | Gerber/ODB++、阻抗约束、布线 |
| 大版图生产准备 | 小字段已验证，保留层次 | 内存/时间基准、分区预览、fracture、job deck |
| GUI 与跨平台 | 无界面脚本；macOS 实测 | Windows/Linux 原生验收 |

## 本次实测得到的原生行为

- GDS 导入默认 `layerNum` = GDS layer，datatype 挂在元素上；单改 `databaseunits` 会让几何物理尺寸改变。
- LayoutEditor 的技术层、DRC 和提取都按层号工作，同层号的所有 datatype 一起参与；
  `setup.addNetlistNotUseDatatype()` 可以把填充等 datatype 排除出连接。
- 技术层级：导体 N、via N+1、导体 N+2（与厂商宏 `autoLoadMacro.layout` 一致）；MOS-default
  的 S/D 端口落在 contact 层，因此 diffusion 不能作为导体。
- 无界面下 `components.newComponent()` 可用，`addLib()`/`getLibs()` 崩溃；自带 IHP 包不可达。
- 原生 LVS 能运行，但 SPICE 导入的器件端口无名或按子电路名绑定，正确版图也报差异；
  因此 LVS 比较由 `lvs_compare.py` 完成。

厂商资料：[提取与 LVS](https://www.layouteditor.org/layout/netlist-extraction/extract-netlist)、
[器件提取方法](https://www.layouteditor.org/layout/netlist-extraction/device-extraction)、
[技术层 API](https://layouteditor.org/layoutscript/api/layers)、
[netListModule API](https://layouteditor.org/layoutscript/api/netlistmodule)。

## 建议的后续顺序

1. 器件尺寸：从栅区几何测 W/L、从电阻体测方块数，加入 LVS 比较（可设容差）。
2. 一个真实开源 PDK（如 IHP SG13G2）的技术文件与小型标准单元 LVS 回归。
3. DRC 扩展：无效 deck 的失败、密度、网格和 `.ledrc`。
4. DXF/CIF 回读与跨平台运行验收。

未纳入本次修改的事项记录在 [TODO.md](../TODO.md)。
