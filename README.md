# 翼辉 AI 技能集

本仓库提供 RealEvo-Stream 的 Agent Skill：[realevo-stream](skills/realevo-stream/SKILL.md)。它只封装命令集检测与安装、SDK 安装和 License 配置；工作空间、工程、设备、构建与部署使用 RealEvo-Stream 原生命令。

## 安装到 Codex

在仓库根目录执行：

```bash
mkdir -p ~/.codex/skills
cp -a skills/realevo-stream ~/.codex/skills/
```

项目的 `skills/` 不是 Codex 的自动发现目录。其他支持通用 Agent Skill 目录的工具可安装到 `~/.agents/skills/`。
