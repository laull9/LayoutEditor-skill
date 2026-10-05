# 待办

- LVS 比较器件尺寸：从版图测 MOS W/L、电阻方块数，按容差与 SPICE 参数对照；脚本定义元件不回写 `extractionDeviceParameter`。
- 用真实开源 PDK（IHP SG13G2 或 SkyWater 130）写技术文件，跑一个小型标准单元的 audit/DRC/LVS 回归。
- 层次化 LVS：子电路逐级比较，而不是先展平。
- 增加 DXF 文本/path/层次回读，以及 CIF/Gerber 格式案例；OASIS 的 datatype 往返单独验收。
- `normalize-dbu` 后文本 magnification 被同比缩放；评估是否恢复原文本高度。
- 在合适商业授权下验证布尔差集、并集、交集、XOR 和 sizing 的实际导出；现有免费版案例不覆盖此项。
- 扩展 DRC：无效/空规则 deck 的失败检查、网格、密度、填充、区域/层次检查及 `.ledrc`；当前 runner 不能作为 foundry 验收。
- 跟进厂商版本：无界面下 `components.addLib()` 崩溃、原生 SPICE 导入不绑定库元件端口；新版本修复后可改用原生 LVS。
- 逐项验证 PIC 工艺模型、光学损耗、耦合比与谱响应；当前只验几何。
- 为大版图保留层次，加入局部/分区预览、flatten 规模上限、内存和时间基准，记录输出与中间文件清理策略。
- 增加混合尺寸紧凑拼版、旋转、wafer flat/notch 和 stepper 字段；不要把当前规则网格当作 packing optimizer。
- 补充圆形 wafer 的原生 GDS 导出验收；当前回归只验证圆形排布计划。
- 分别在 Windows/Linux 验证解释器发现、subprocess 导入和五组 runner。
