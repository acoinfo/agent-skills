# RealEvo-Stream 原生命令参考

本文说明命令路由与已确认的差异，不代替命令帮助；内容以 `/opt/acoinfo/realevo-stream` 原生命令的实际行为为准。

## 命令入口

| 命令 | 实际子命令或入口 | 用途 |
| --- | --- | --- |
| `rl-workspace` | `init` `createbase` `show` `clean` `--version` | 初始化工作空间、准备 SylixOS Base、查看和清理平台产物 |
| `rl-project` | `create` `update` `reconfig` `show` | 创建工程、更新配置、重配、查看配置 |
| `rl-build` | `all` `clean` `config` `build` `install` `uninstall` `symbolcheck` `package` | 构建编排；`all` 执行 clean → config → build → install，`package` 当前为空实现 |
| `rl-device` | `add` `delete` `update` `list` `upload` `install` | 设备清单、整机 FTP 上传、设备端软件安装 |
| `rl-upload` | `workspace` `project` `file` `directory` `soft` | 上传工作空间或工程产物、单文件、目录、设备端软件 |
| `rl-package` | `set` `show` `search` `install` `uninstall` `install2device` `package` | Armory 配置、检索、安装与打包 |
| `rl-tools` | `show` `update` `update_lcsproxy` `getarmory` `install` `modifycmake` `restorecmake` `modifygcc` `restoregcc` `exportcmake` `checksymbolic` `json2struct` `--version` | 命令集、SDK、License、开发工具及系统配置辅助 |
| `rl-colcon` | `clean` `build` `list` | ROS 2 colcon 构建与包列表 |
| `rl-ros` | `create` | 创建 ROS 2 包 |
| `rl-ecs` | `create` `config` `package` `upload` `load` `save` `systemcallgen` | ECS 容器包和设备操作 |
| `rl-ecsm` | `set` `update` `list` `delete` `push` `pull` `show` | ECSM 镜像源配置与镜像传输 |
| `project-run-tools` | 独立参数入口 | 通过 Telnet/SSH 在设备端启动程序 |
| `project-run-test` | `--device` `--project` `--path` | 上传并运行 SylixOS 工程可执行文件 |

`sylixos-linux-tools` 是 `rl-build` 调用的构建配置执行器；`realevo-project-tools`、`realevo-symbol-tools`、`realevo-package-tools`、`rl-utils` 是解析和检查辅助工具；`realevo-complete-tools` 提供 Shell 补全。`armory` 为包管理二进制，`windows_exec` 为 Windows 执行辅助脚本。常规开发先选上表中的入口。

`rl-tools update` 可升级命令集或安装 SDK：在线 SDK 使用 `--plugin=@命名空间/包名`，离线 SDK 使用 `--path=<含 stream_config.json 的目录>`。`rl-tools update_lcsproxy` 配置 `usbkey|server|http` 授权代理；环境初始化与授权优先使用本 Skill 的 CLI，以取得统一 JSON 结果及授权回读。`rl-tools install --soft=` 安装 `cpython-crossenv|go|colcon|ecsc|fastddsgen|uorb` 等开发工具，属于原生命令能力。

## 目标 OS 与 Platform

`--os`、`--platform`、产品系列和 ECS 架构标签是不同概念，不可混用。

| 目标 OS | `rl-workspace init` 所需参数 | Platform 与构建 |
| --- | --- | --- |
| SylixOS | `--os=sylixos`；选择 `--product=<系列>`、`--version=<Base> --platform=<P> --createbase=true`，或已有 `--base=<路径> --platform=<P>` | `--platform` 名称须被所选 Base 的 `platforms.mk`/`config.mk` 接受；`rl-build --os=sylixos` 使用 SylixOS Base 与 `.realevo/arch/<P>/rootfs` |
| Linux | `--os=linux --linux_platform=<P> --linux_toolchain=<.cmake 文件或工具链目录> --linux_rootfs=<目录或 tar.gz>` | `<P>` 为 `ARM64|X86|X86_64|RISCV|LOONGARCH` 中的一个；`rl-build --os=linux` 使用 `.realevo/linux/<P>/rootfs` |
| OpenEuler | `--os=openeuler --openeuler_platform=<P> --openeuler_toolchain=<.cmake 文件或工具链目录> --openeuler_rootfs=<目录或 tar.gz>` | 同一组五个 Platform 值；`rl-build --os=openeuler` 使用 `.realevo/openeuler/<P>/rootfs` |

Linux/OpenEuler 的工具链参数始终必填。rootfs 规范化后恰好为 `/` 时为 native 构建：staging 保持空目录，构建配置不设置 `CMAKE_SYSROOT`；其他有效 rootfs 为 cross 构建。两者的初始化参数按单个平台值校验。`--os=all` 选择三个目标 OS，但仍须提供各自必要参数。`rl-workspace init` 会先清理原有 `.realevo/arch`、`linux`、`openeuler` 和 `package_list`，再次初始化前须确认这些产物可被重建。

当前全局 `config/platforms.mk` 列出以下 **63 个 SylixOS Platform 名称**；实际可用集合取决于所选 Base 和已安装工具链：

- ARM：`ARM_926H` `ARM_926S` `ARM_920T` `ARM_A5` `ARM_A5_SOFT` `ARM_A7` `ARM_A7_SOFT` `ARM_A8` `ARM_A8_SOFT` `ARM_A9` `ARM_A9_SOFT` `ARM_A15` `ARM_A15_SOFT` `ARM_V7A` `ARM_V7A_SOFT`
- ARM64：`ARM64_A53` `ARM64_A55` `ARM64_A57` `ARM64_A72` `ARM64_GENERIC`
- MIPS：`MIPS32` `MIPS32_SOFT` `MIPS32_R2` `MIPS32_R2_SOFT` `MIPS64_R2` `MIPS64_R2_SOFT` `MIPS64_LS3A` `MIPS64_LS3A_SOFT`
- x86：`x86_PENTIUM` `x86_PENTIUM_SOFT` `X86_64`
- PPC：`PPC_750` `PPC_750_SOFT` `PPC_464FP` `PPC_464FP_SOFT` `PPC_E500V1` `PPC_E500V1_SOFT` `PPC_E500V2` `PPC_E500V2_SOFT` `PPC_E500MC` `PPC_E500MC_SOFT` `PPC_E5500` `PPC_E5500_SOFT` `PPC_E6500` `PPC_E6500_SOFT`
- SPARC：`SPARC_LEON3` `SPARC_LEON3_SOFT` `SPARC_V8` `SPARC_V8_SOFT`
- RISCV：`RISCV_GC32` `RISCV_GC32_SOFT` `RISCV_GC64` `RISCV_GC64_SOFT`
- LOONGARCH：`LOONGARCH64` `LOONGARCH64_SOFT`
- CSKY：`CSKY_CK807` `CSKY_CK807_SOFT` `CSKY_CK810` `CSKY_CK810_SOFT` `CSKY_CK860` `CSKY_CK860_SOFT`
- SW6B：`SW6B` `SW6B_SOFT`

`--product` 是另一种选择：当前 `acu-sdk` 的产品系列为 `ARC1000`、`AEC1000`、`ARC2000`、`AEC2000`、`AMC2000`、`ARC3000`、`AEC3000`、`AMC3000`。其 SylixOS `arch` 映射为 `ARM64_GENERIC`；其中 `AMC2000`、`AMC3000` 另有 Linux `ARM64` rootfs 和工具链配置。产品系列名不是 `--platform` 值。

`rl-ecs --platform` 使用包架构标签：`arm|arm64|x86|x86-64|ppc|sparc|mips32|mips64|riscv|loongarch|csky|noarch`，与工作空间的 Platform 名称不同。

## 开发流程

1. **准备环境**：用 Skill `check` 查看 `result.installed`；必要时 `install` 和 `install-sdk`；用 `license show` 查看 `result.status`，需要时 `license set` 并确认 `VALID`。开发命令加入路径：`export PATH=/opt/acoinfo/realevo-stream/bin:$PATH`。
2. **新目录初始化工作空间**：按目标 OS 选择上述一条 `rl-workspace init` 路径；用 `rl-workspace show` 和 `.realevo/config.json` 核对平台与工具链。SylixOS Base 可由 `createbase` 单独准备。初始化会清理旧平台产物。
3. **创建或导入工程**：在工作空间根目录使用 `rl-project create --name=<工程名> --type=cmake --template=app` 创建常规 CMake 工程，或按实际源码类型使用 `--source=<路径>`。编辑工程源码；已有工程使用 `rl-project update|reconfig|show` 管理配置。帮助列出的工程类型不保证都存在同名模板。
4. **构建**：`rl-build all --project=<工程名> --os=<sylixos|linux|openeuler>`，需要定位问题时分别执行 `clean`、`config`、`build`、`install`；`--platforms=<P>` 可限定目标平台。普通工程产物位于 `install-<os>/<P>/`。SylixOS ROS 2 工程使用 `rl-colcon build`，符号检查使用 `rl-build symbolcheck`。
5. **登记设备与部署**：确认工作空间中的 `.realevo/devicelist.json`，用 `rl-device add --name=<设备名> --ip=<地址> --platform=<P> --os=<目标OS>` 登记，再用 `rl-device list` 核对。工程部署用 `rl-upload project --device=<设备名> --project=<工程名>`；工作空间 rootfs 用 `rl-upload workspace --device=<设备名>`。设备 OS、Platform 须与已构建产物一致。
6. **运行与发布**：SylixOS 可用 `project-run-test --device=<设备名> --project=<工程名> --path=<install-sylixos 下的可执行文件>` 上传并运行，或用 `project-run-tools` 在设备端启动。需要 Armory 包时使用 `rl-package package`。ROS 2 包由 `rl-ros create` 创建；ECS 包与镜像操作分别用 `rl-ecs`、`rl-ecsm`。

## 实现限制与命令选择

- `rl-build package` 当前仅输出完成提示，实际打包使用 `rl-package package`。
- `rl-colcon all` 出现在允许命令数组中，但实际分发没有该分支；使用 `clean`、`build`、`list`。
- `rl-package install` 要求 SylixOS `.realevo/arch`，`install2device` 也走 SylixOS 包路径；不要写成 Linux/OpenEuler 通用安装流程。
- `rl-upload workspace/project` 探测 FTP，失败时尝试 SFTP；`file/directory` 当前固定使用 FTP。Linux/OpenEuler 工程或工作空间部署路径映射到 `/root` 或 `/home/<用户>` 下，SylixOS 映射到设备根目录。
- `rl-upload soft` 中的 Python/JavaScript 设备运行时安装明确拒绝 Linux/OpenEuler；`project-run-test` 明确要求 SylixOS 设备及 `install-sylixos` 路径。
- `rl-project run/debug` 无有效分发入口；`rl-project` 帮助列出的 CMake `common` 模板在当前模板目录中不存在。构建命令成功与否应结合退出码、错误输出和产物核验。
