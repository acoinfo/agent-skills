---
name: realevo-stream
description: 当需要检测或安装 RealEvo-Stream 命令集、安装 SDK、配置或核验 License 时使用。工作空间、工程、构建、设备和部署等开发操作直接使用原生命令。
metadata:
  type: skill
  domain: embedded-development
  version: 2.0.0
  platform:
    - SylixOS
    - Linux
    - OpenEuler
  tags:
    - realevo-stream
    - embedded-ide
    - bootstrap
    - install
    - license
---

# RealEvo-Stream 环境初始化与授权

本 Skill 的脚本只负责命令集检测与安装、SDK 安装、License 配置与核验。按用户意图选择入口：

| 意图 | 入口 |
| --- | --- |
| 检测或安装命令集、安装 SDK、查看或配置 License | 本 Skill 的 `scripts/cli.py` |
| 初始化工作空间、创建工程、构建、设备管理、部署、打包、ROS 或 ECS 操作 | `/opt/acoinfo/realevo-stream/bin` 中的原生命令 |

## Skill 命令

```bash
CLI="<Skill 目录>/scripts/cli.py"
python3 "$CLI" check
python3 "$CLI" install --dry-run
python3 "$CLI" install
python3 "$CLI" install-sdk --spec='@realevo/realevo-stream-sdk'
python3 "$CLI" license show
python3 "$CLI" license set --type=server --server-ip="$SERVER_IP" --server-port="$SERVER_PORT"
```

将 `<Skill 目录>` 替换为当前 Skill 的实际路径，配置 server 模式前设置 `SERVER_IP` 和 `SERVER_PORT`。`install` 可用 `--package-file=<文件>` 指定本地包；`install-sdk` 可用 `--path=<含 stream_config.json 的目录>` 离线安装。`license set` 支持 `usbkey`、`server` 和 `http`。其他参数以 `python3 "$CLI" <命令> --help` 为准。

脚本输出 JSON：退出码 0 为操作成功，1 为业务失败，2 为参数错误。`check` 成功仍须查看 `result.installed`；`license show` 成功仍须查看 `result.status`；`license set` 只有回读为 `VALID` 才成功。安装 SDK 时底层 `rl-tools` 可能在部分组件失败后仍返回 0，应以脚本的 `status` 为准。`install`、`install-sdk`、`license set` 支持 `--dry-run`。

需要系统权限的操作由脚本先尝试免密 sudo；否则使用环境变量 `REALEVO_SUDO_PASSWORD` 预认证。不要把密码写入命令行。

## 原生命令

开发操作直接调用原生命令；命令选择、目标 OS 与 Platform 差异、端到端流程见 [原生命令参考](references/native-commands.md)。运行前将 `/opt/acoinfo/realevo-stream/bin` 加入 `PATH`，并检查对应命令的 `--help` 与当前工作空间配置。`rl-workspace init` 应在目标目录执行；其余工作空间操作在已有工作空间内执行。
