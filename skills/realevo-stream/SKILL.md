---
name: realevo-stream
description: 用于 RealEvo-Stream 环境初始化与授权：检测或安装命令集、安装 SDK、配置并核验 License。日常开发操作使用原生命令。
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

本 Skill 的脚本只处理四类操作：检测命令集、安装命令集、安装 SDK、配置或查看 License。工作空间、工程、设备、构建和部署直接调用 `/opt/acoinfo/realevo-stream/bin` 中的原生命令。

## Skill 命令

```bash
CLI=<本技能目录>/scripts/cli.py
python3 "$CLI" check
python3 "$CLI" install --dry-run
python3 "$CLI" install
python3 "$CLI" install-sdk --spec='@realevo/realevo-stream-sdk'
python3 "$CLI" license set --type=server --server-ip=<IP> --server-port=4367
python3 "$CLI" license show
```

| 命令 | 用途与关键参数 |
| --- | --- |
| `check` | 检查 `rl-workspace` 和 `rl-tools` 是否可执行，返回 `result.installed`、版本及 License 概览。未安装时查询仍可成功，需检查 `installed` 值。 |
| `install` | 下载并以 `--quiet` 无人值守安装命令集；可用 `--package-file=<文件>` 指定本地包。安装包不支持 `--quiet` 时会失败并保留解包路径。 |
| `install-sdk` | 用 `--spec=@命名空间/包名` 在线安装，或用 `--path=<含 stream_config.json 的目录>` 离线安装。 |
| `license show` | 读取授权状态；查询成功不等于授权有效，需检查 `result.status`。 |
| `license set` | 支持 `usbkey`、`server`（`--server-ip`、可选 `--server-port`）和 `http`（`--http-address`）。配置后最多回读三次，仅在授权为 `VALID` 时返回成功。 |

脚本输出 JSON；退出码 0 表示命令成功，1 表示业务失败，2 表示参数错误。`install`、`install-sdk` 和 `license set` 支持 `--dry-run`。其余参数用 `python3 "$CLI" <命令> --help` 查看。

需要 sudo 时，脚本先尝试免密执行；否则从 `REALEVO_SUDO_PASSWORD` 获取密码并预认证。不要把密码写入命令行。安装可能耗时数分钟，执行前告知用户。

`rl-tools` 的值参数使用 `--参数=值`；SDK 安装时即使底层命令返回 0，也可能有失败项，脚本会检查错误输出。调用方应以脚本 JSON 的 `status` 为准。

## 原生命令

先把命令目录加入 `PATH`。除初始化新工作空间外，在工作空间目录执行动作命令；长任务使用 `timeout` 和 `</dev/null` 防止交互挂起。

```bash
export PATH=/opt/acoinfo/realevo-stream/bin:$PATH

# 在新目录中初始化工作空间；Linux/欧拉工具链传 .cmake 文件，避免选择菜单
rl-workspace init --os=linux --linux_platform=X86_64 \
  --linux_toolchain=<工具链>.cmake --linux_rootfs=<rootfs>

# 在已有工作空间中管理工程、设备、构建和部署
rl-project create --name=<工程名> --type=cmake --template=app \
  --make-tool=make --debug-level=debug
rl-device list
timeout 1800 rl-build all --project=<工程名> --os=sylixos </dev/null
timeout 1800 rl-upload project --device=<设备名> --project=<工程名> </dev/null
```

原生命令输出为文本，部分命令失败时仍可能返回 0；同时检查输出中的错误与成功标志。添加设备前确认 `<工作空间>/.realevo/devicelist.json` 存在，否则设备清单可能写到错误位置。无人值守时避免 `rl-project update --platform`（可能循环等待输入）和 `rl-device upload`（可能交互），部署使用 `rl-upload`。其他原生命令及参数直接查对应命令的 `--help`。
