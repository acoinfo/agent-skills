---
name: realevo-stream
description: 指导 RealEvo-Stream（SylixOS / Linux / OpenEuler）嵌入式工程的完整开发流程：命令集检测与安装、SDK 安装、License 配置与核验、工作空间初始化、工程创建、构建、设备登记、部署、运行与打包。需要使用 rl-* 原生命令完成 RealEvo 工程开发，或准备 RealEvo-Stream 开发环境时使用。
metadata:
  type: skill
  domain: embedded-development
  version: 2.1.0
  platform:
    - SylixOS
    - Linux
    - OpenEuler
  tags:
    - realevo-stream
    - embedded
    - build
    - deploy
---

# RealEvo-Stream 工程开发

覆盖两类工作：**环境准备**（命令集 / SDK / License）与**工程开发全流程**（工作空间 → 工程 → 构建 → 设备 → 部署 → 运行）。

默认命令集位于 `/opt/acoinfo/realevo-stream`。本 Skill 于 2026-10-08 核对了本机 **3.0.0（Launch_Date=2026-08-21）** 的源码；已知缺陷只适用于该核验基线，源码指纹见 [constraints.md](references/constraints.md)。其他版本先核对帮助与实际分支行为，不能仅凭版本号沿用缺陷结论。

## 1. 入口选择

| 意图 | 入口 |
| --- | --- |
| 检测/安装命令集、安装 SDK、查看/配置 License | 本 Skill 的 `scripts/cli.py`（统一 JSON 输出） |
| 工作空间、工程、构建、设备、部署、运行、打包、ROS 2、ECS | `/opt/acoinfo/realevo-stream/bin` 的原生命令 |

命令集内**没有** `scripts/cli.py`，它是本 Skill 自带的无人值守封装。

## 2. 运行前置

本封装支持 **Linux 开发宿主、Python 3.10+**；安装包解压还要求 `tarfile.data_filter`（旧维护版本需安全补丁）。目标 SylixOS/Linux/OpenEuler 与宿主系统是两个概念。需具备 Bash、GNU coreutils（含 `timeout`）、sudo，以及当前阶段所用的 `jq`、CMake、make 等依赖。安装器依赖 deb/rpm 包管理器，License 配置依赖 systemd；不要对其他宿主假定兼容。

```bash
export PATH=/opt/acoinfo/realevo-stream/bin:$PATH
sudo -n true || echo "无免密 sudo：需要特权的命令会失败"
CLI="<本 Skill 目录>/scripts/cli.py"
python3 "$CLI" check          # result.installed 且 result.usable；SDK/编译器另行检查
python3 "$CLI" license show   # 检查 result.status == VALID
```

- 安装会向 `/etc/profile` 写入 `REALEVO_COMPILER_PATH` 与 PATH；不会刷新当前进程。新安装后开启登录 shell，或读取该已核验配置并把编译器 bin 目录加入当前 PATH，再用 `command -v <目标编译器>` 验证。仅添加命令集 bin 不等于工具链就绪。
- 工作空间唯一标记是 `.realevo/` 目录，命令会**向上查找**工作空间根。
- `rl-workspace init` 在**目标目录**执行；其余操作在**已有工作空间内**执行。
- `cli.py`：业务结果/参数错误输出 JSON，退出码为 0/1/2；`--help` 为文本且退出 0。`check` 未安装仍可返回 0，必须检查结果字段；`license show` 成功只表示读到状态，授权须为 `VALID`。
- `install`/`install-sdk`/`license set` 支持 `--dry-run`：不执行系统安装/配置；本地包检查会创建并清理临时文件，远程包仅预览地址。超时与验收边界、安装器摘要要求见 [constraints.md](references/constraints.md#8-凭据权限与封装验收)。

## 3. 标准开发流程

链路：**初始化工作空间 → 创建工程 → 编辑代码 → 编译 → 添加设备 → 部署 → 运行**。

| # | 阶段 | 命令 | 必需/关键参数 | 前置 |
| --- | --- | --- | --- | --- |
| 0 | 环境准备 | `cli.py check/install/install-sdk/license` | SDK：`--spec=` 或 `--path=`；License set：`--type=`；install：见脚本帮助 | 仅写入操作需要 sudo 权限 |
| 1 | 初始化工作空间 | `rl-workspace init` | SylixOS：产品模式用 `--product=`；其余用 `--platform=` + （`--base=` 或 `--version=`）；Linux/OpenEuler：`--os=` + `*_platform` + `*_toolchain` + `*_rootfs` | 在目标目录；目录可写 |
| 2 | 创建工程 | `rl-project create` | `--name=` 必填；`--type=`+`--template=`，或 `--source=` | 已在工作空间内 |
| 3 | 编辑源码 | — | — | — |
| 4 | 构建 | `rl-build all`（= clean→config→build→install） | `--project=`（工程目录内可省）、`--os=` | 工作空间 `config.json` 有效 |
| 5 | 登记设备 | `rl-device add` | `--name= --ip= --platform=` | 设备可达、凭据正确 |
| 6 | 部署 | `rl-upload project` \| `workspace` | `--device=`；工程目录外需 `--project=` | 阶段 4 有产物、阶段 5 已登记 |
| 7 | 运行/发布 | `project-run-test`、`rl-package package` | 见参考 | SylixOS 设备 / Armory 凭据 |
| 4' | ROS 2 构建 | `rl-colcon build` | `--merge-install` | ROS 2 工程 + `rl-package install` 依赖 |

## 4. 目标 OS 参数

| OS | `rl-workspace init` | 构建 |
| --- | --- | --- |
| SylixOS（默认） | `--product=<系列>`（平台由 SDK 产品映射决定）；或 `--platform=<P>` 配 `--version=<Base> --createbase=true` / `--base=<路径>` | `rl-build … --os=sylixos`，用 `.realevo/arch/<P>/rootfs` |
| Linux | `--os=linux --linux_platform=<P> --linux_toolchain=<.cmake\|目录> --linux_rootfs=<目录\|tar.gz\|/>` | `rl-build … --os=linux`，用 `.realevo/linux/<P>/rootfs` |
| OpenEuler | `--os=openeuler --openeuler_platform=<P> --openeuler_toolchain=… --openeuler_rootfs=…` | `rl-build … --os=openeuler`，用 `.realevo/openeuler/<P>/rootfs` |

- Linux/OpenEuler 平台只能是 `ARM64|X86|X86_64|RISCV|LOONGARCH`，**工具链必填**；优先传已核验 `.cmake`。目录型会向工具链目录写入生成文件，仅用于自有可写目录；多前缀应明确选择文件，勿用 `--quiet` 盲选。
- **native 判定唯一规则**：rootfs 规范化为 `/` → staging 保持空目录（不复制/软链宿主 `/`）；其他为 cross。
- SylixOS 平台必须是 63 项白名单之一，且被所选 Base 的 `platforms.mk` 接受；产品系列名不是 `--platform` 值。

## 5. 工程 type / template

| 用途 | 命令片段 |
| --- | --- |
| C/C++ 应用 / 动态库 / 内核模块 | `--type=cmake --template=app\|lib\|ko` |
| 兼容 RealEvo-IDE | `--type=realevo --template=app\|ko\|shared_lib` |
| Python / Cython / Go / JavaScript / ROS 2 | `--type=<类型> --template=common` |
| BSP | `--type=realevo_bsp\|cmake_bsp --template=<arch>-none` |
| 中间件移植 | `--source=<目录\|压缩包\|git> --type=cmake` |

`--type=cmake --template=common` 会失败；模板可用集合以 `config/template/` 为准。Go 需先装 Go，ROS 2/Cython 需先装对应环境。

## 6. Agent 硬约束

1. **非交互执行**：原生命令默认关闭 stdin，使用 `timeout --kill-after=5s <截止时间>`。已授权卸载等已知确认协议可以提供受控输入，见参考。命令集没有统一非交互开关。
2. **避开不可靠接口**：多平台下 `rl-project update --platform` 会在 EOF 自旋；`rl-tools exportcmake` 无平台参数，EOF 后可能未选平台就继续执行；`rl-tools update_lcsproxy` 必须带 `--type=`。
3. **不要只信退出码**：`rl-project create --type=ros2` 失败仍返回 0；`rl-package uninstall` 非交互静默取消并返回 0；`rl-tools install/update` 需解析输出中的 `[ERROR]`/`Found N installation failures`。反之 `rl-device add` 平台校验失败返回 255。
4. **不得手工修改厂商文件来绕过错误**：`compiler/**`、`config/cmake/**`、`config/automake/**`、`pkg/**` 与工具链/sysroot/预编译库；用户已授权的安装、更新与工作空间 staging 写入按其正常流程执行。
5. **凭据**：不写入 argv、源码或日志。原生密码接口只有 argv 时使用已受保护的配置；缺少安全配置渠道只停止依赖该凭据的阶段，不能改用默认 `root/root`。
6. **破坏性操作核对授权和目标**：`init` 清理旧 `.realevo/{arch,linux,openeuler,package_list}`；已有授权覆盖该清理时继续，否则在删除已有数据前确认。新空目录初始化无需重复确认。
7. **按阶段报告 BLOCKED**：设备、网络、凭据缺失时仍完成可独立执行的本地工作。远程运行需验证输出与退出状态；本地超时不代表远端程序已停止。

## 7. 参考

- [native-commands.md](references/native-commands.md)：命令总览、执行顺序、各命令参数/前置/产物、平台白名单、配置与目录。
- [workflows.md](references/workflows.md)：各类型工程端到端命令序列与阶段验收点。
- [constraints.md](references/constraints.md)：交互阻塞点、成功判定、错误→处理、已知缺陷、BLOCKED 判定。

`cli.py` 参数以 `python3 "$CLI" <命令> --help` 为准。
