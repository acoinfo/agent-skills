# 翼辉 AI 技能集

本仓库提供 RealEvo-Stream 的 Agent Skill：[realevo-stream](skills/realevo-stream/SKILL.md)。它指导 RealEvo-Stream（SylixOS / Linux / OpenEuler）嵌入式工程的完整开发流程：

- **环境准备**由 Skill 自带的 `scripts/cli.py` 完成（命令集检测与安装、SDK 安装、License 配置与核验，统一 JSON 输出）。
- **工程开发**直接使用 `/opt/acoinfo/realevo-stream/bin` 的原生命令（工作空间、工程、构建、设备、部署、运行、打包、ROS 2、ECS）。

Skill 内容以 `/opt/acoinfo/realevo-stream` 环境的**实际命令行为**为准，不绑定具体版本；`docs/realevo-stream` 仅作为编写时的参考资料，不是运行依赖。

| 文件 | 内容 |
| --- | --- |
| [SKILL.md](skills/realevo-stream/SKILL.md) | 入口：适用场景、运行前置、标准开发流程、硬约束 |
| [references/native-commands.md](skills/realevo-stream/references/native-commands.md) | 每个命令的作用、场景、前置条件、参数、产物与依赖 |
| [references/workflows.md](skills/realevo-stream/references/workflows.md) | 各类型工程的端到端命令序列与阶段验收点 |
| [references/constraints.md](skills/realevo-stream/references/constraints.md) | 非交互约束、阻塞点、常见错误、已知缺陷、BLOCKED 判定 |

## 安装到 Codex

在仓库根目录执行：

```bash
mkdir -p ~/.codex/skills
cp -a skills/realevo-stream ~/.codex/skills/
```

项目的 `skills/` 不是 Codex 的自动发现目录。其他支持通用 Agent Skill 目录的工具可安装到 `~/.agents/skills/`。
