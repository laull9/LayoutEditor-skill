# layout-skill

[English](README.md) | **简体中文**

一个 [Agent Skill](https://agentskills.io)：通过 **[juspertor LayoutEditor](https://layouteditor.com)** 的
LayoutScript Python 接口**无界面（headless）生成掩模版图**。你的编程 Agent 会编写参数化的 Python 版图生成脚本，
导出 GDSII，接着做验证（设计规则 DRC、电学连通/绝缘、机械释放、物理量复核），最后给你看渲染好的预览图。

内容都来自真实做过的项目：实测过的 API 签名和坑、免费版的导出限制及合规的规避画法、不依赖布尔运算的几何技巧、
SOI-MEMS 掩模约定，以及一套通用的验证工具。

- 与具体 Agent 无关：遵循开放的 [Agent Skills 规范](https://agentskills.io/specification)，可用于 Claude Code、
  Cursor、Codex、OpenCode、GitHub Copilot、Cline 等兼容的 Agent。
- 可以用 `npx skills` 一条命令安装，也可以直接复制文件夹。

> 本项目与 juspertor GmbH 无关联。LayoutEditor 是商业软件，请到官方下载并遵守其许可；本 skill 只负责自动化操作它。

---

## 1. 安装 skill

### 方式 A：`npx skills`（适用于所有受支持的 Agent）

需要 Node.js。用的是开源的 [skills CLI](https://github.com/vercel-labs/skills)：

```bash
npx skills add laull9/layout-skill
```

默认装到当前项目；加 `-g` 则为全局（用户级）安装：

```bash
npx skills add laull9/layout-skill -g
```

也可以指定 Agent，并以非交互方式安装：

```bash
npx skills add laull9/layout-skill -g -a claude-code -a cursor -y
```

CLI 会识别仓库根目录的 `SKILL.md`，把 skill 链接（或复制）到各个 Agent 的 skills 目录。

### 方式 B：手动复制

整个仓库就是 skill 文件夹。把它克隆到 Agent 的 skills 目录即可，**文件夹名要保持 `layout-skill`**
（必须与 `SKILL.md` 里的 `name` 字段一致）：

| Agent | 用户级位置 | 项目级位置 |
|---|---|---|
| Claude Code | `~/.claude/skills/layout-skill` | `<项目>/.claude/skills/layout-skill` |
| 遵循通用约定的 Agent | `~/.agents/skills/layout-skill` | `<项目>/.agents/skills/layout-skill` |
| 其他 | 见各 Agent 文档中的 skills 目录说明 | |

```bash
git clone https://github.com/laull9/layout-skill ~/.claude/skills/layout-skill
```

不支持 skill 的 Agent 也能用：让它先读 `SKILL.md` 再按其中步骤执行（例如"阅读 layout-skill/SKILL.md 并照做"），
脚本在任意 shell 里都能运行。

## 2. 安装 LayoutEditor

LayoutEditor 由 juspertor GmbH 开发，官网：<https://layouteditor.com>。

1. 打开官方下载页 **<https://layouteditor.com/download.html>**（完整安装包列表在
   <http://www.layouteditor.net/download.html>，历史版本也从这里进入）。下载前需要勾选出口管制声明。
2. 按平台选择安装包（下表以 20260920 版为例，新版本命名规则相同）：

   | 系统 | 安装包 |
   |---|---|
   | macOS（Apple Silicon 与 Intel 通用） | `layout-<版本>-macOS-universal.dmg`，把 `layout.app` 拖进 `/Applications` |
   | Windows 64 位 | `layout-<版本>-win-64bit-installer.msi`（或免安装的 `.zip`） |
   | Linux | `layout-<版本>-Linux.x86_64.AppImage`，或 `.deb`（Ubuntu 22.04/24.04/26.04）/ `.rpm`（RHEL 8/9/10） |

3. 仅 macOS：如果第一次打开被 Gatekeeper 拦截，右键 `layout.app` →"打开"一次即可；
   也可以执行 `xattr -d com.apple.quarantine /Applications/layout.app`。
4. 版本选择：**免费版（0 €）就够用**，脚本、免费限额内的 GDS 导出和 DRC 都可以用。付费的 reduced / full 版会解除导出限制。
   最新条款以官网为准，实测的限制见 `references/free-version-limits.md`。
5. 确认能找到 LayoutEditor 自带的 Python：

   ```bash
   scripts/find_layouteditor.sh
   ```

   正常会输出类似 `/Applications/layout.app/Contents/MacOS/Frameworks/Python.framework/Versions/3.14/bin/python3.14` 的路径。
   如果找不到，可以设置 `LE_PY=<该 python 的路径>` 或 `LAYOUTEDITOR_HOME=<安装目录>`
   （用 `find / -name LayoutScript.py` 可以找到模块所在位置）。

## 3. 其他依赖

分析和预览脚本需要 Python 3.8+，并装好 numpy、Pillow、matplotlib（LayoutEditor 自带的 Python 里没有这些包）：

```bash
python3 -m pip install numpy pillow matplotlib
```

## 4. 快速体验

在 skill 文件夹内运行：

```bash
examples/run_demo.sh /tmp/le_demo
```

它会对一个 2×2 mm 的 SOI 梳齿驱动测试芯片依次执行：生成 → DRC → 连通性检查 → 预览图。
预期结果：生成 `demo_chip.gds`，DRC 报告 0 处违规，连通性报告最后一行为 `RESULT: ALL PASS`，
`/tmp/le_demo/preview/` 下生成 PNG 预览图。

之后直接对 Agent 提需求即可，例如："用 LayoutEditor 按这些尺寸画一个 4 掩模 SOI 梳齿谐振器版图，跑 DRC 并给我看预览图。"

也可以直接调用各个工具：

```bash
LE_PY="$(scripts/find_layouteditor.sh)"
"$LE_PY" my_generator.py                                         # 你的生成脚本（参考 examples/demo_chip.py）
"$LE_PY" scripts/drc_check.py out.gds MY_TOP rules.json drc.txt  # LayoutEditor 自带 DRC
python3 scripts/check_connectivity.py out_polys.json probes.json nets.txt
python3 scripts/render_preview.py out_polys.json preview/ views.json
```

## 5. 目录结构

```
layout-skill/
├── SKILL.md                     # Agent 入口（工作流 + 规则）
├── scripts/
│   ├── le_helpers.py            # 几何工具 + LayoutEditor 会话封装 + JSON 导出
│   ├── drc_check.py             # 按 JSON 规则表调用 LayoutEditor drcTool 做 DRC
│   ├── check_connectivity.py    # 栅格法网表/绝缘/释放检查（numpy + Pillow）
│   ├── render_preview.py        # PNG 预览（matplotlib）；headless 截图是空白的
│   └── find_layouteditor.sh     # 定位 LayoutEditor 自带的 Python
├── examples/
│   ├── demo_chip.py             # 用到全部技巧的 SOI 梳齿驱动测试芯片
│   ├── demo_drc_rules.json      # SOI-MEMS 起步规则集
│   ├── demo_probes.json         # demo 的焊盘与探针点
│   ├── demo_views.json          # demo 预览的放大视窗
│   └── run_demo.sh              # 端到端流程
└── references/                  # Agent 按需读取
    ├── layoutscript-api.md      # 实测 API 签名与坑
    ├── free-version-limits.md   # 免费版导出限制实测 + 合规的规避画法
    ├── geometry-techniques.md   # 不用布尔运算画圆角、沟槽环、孔、梳齿、文字
    ├── mems-soi-process.md      # 4 掩模 SOI-MEMS 约定与默认规则
    ├── verification.md          # DRC、连通性、解析复核、目检清单
    └── troubleshooting.md       # 现象 → 原因 → 解决
```

## 6. 关键要点（详见 `references/`）

- 1 个数据库单位 = 1 nm；辅助函数统一用 µm。
- `strans.rotate()` 是**顺时针**旋转；`addCellrefArray` 只有一维阵列可靠。
- headless 截图是空白的，所以预览图由导出的多边形数据渲染。
- **免费版**：元素数超过约 8,000–10,000，**或会话中用过布尔运算引擎**之后，GDS 导出会被拒绝（改为写出只能在云端打开的 `.lec`）。
  本 skill 全程不用布尔运算来画最终掩模（结构层采用"所画即保留"极性、keyhole 场区多边形、偏置加裁剪生成沟槽环）。
  请尊重软件许可：不要把布尔运算的结果搬到新会话里去绕过限制。

## 7. 兼容性

| 项目 | 状态 |
|---|---|
| LayoutEditor 20260920，macOS universal（Apple Silicon），自带 Python 3.14 | 完整验证 |
| Linux / Windows | LayoutScript API 相同，预计可用；安装路径未验证（可用 `LE_PY` 指定） |
| Agent | 任何兼容 [Agent Skills](https://agentskills.io) 的 Agent；其他 Agent 可通过 `SKILL.md` 手动使用 |

## 参与贡献

特别欢迎在其他 LayoutEditor 版本或平台上的实测反馈（API 行为、安装路径、许可限制），请附上版本号和操作系统。
脚本请保持依赖精简、与具体项目无关，并确保 `examples/run_demo.sh` 仍能通过。

## 许可证

[MIT](LICENSE) © 2026 laull9
