# RealEvo-Stream 原生命令参考

命令入口：`/opt/acoinfo/realevo-stream/bin`。行为与缺陷以 [SKILL.md](../SKILL.md) 的本机 3.0.0 核验基线为准；其他版本核对帮助与源码/行为。原生帮助可能不完整，不可仅凭帮助推断非交互能力。错误信息与排错见 [constraints.md](constraints.md)。

## 1. 命令总览

| 命令 | 用途 |
| --- | --- |
| `rl-workspace` | 工作空间初始化、Base 创建、查看、清理 |
| `rl-project` | 工程创建、配置更新、重配置、查看 |
| `rl-build` | 构建编排：clean / config / build / install / uninstall / symbolcheck |
| `rl-colcon` | ROS 2 工程的 colcon 构建与包列表 |
| `rl-upload` | 工程 / 工作空间 / 目录 / 文件 / 运行时软件部署 |
| `rl-device` | 设备增删改查、整机上传、设备端软件安装 |
| `rl-package` | Armory 包管理：配置 / 搜索 / 安装 / 卸载 / 打包 / 发到设备 |
| `rl-tools` | 命令集自身管理：升级、SDK、License、CMake/GCC 修补、开发工具安装 |
| `rl-ecs` / `rl-ecsm` | ECS 容器打包与 ECSM 镜像源管理 |
| `rl-ros` | 创建 ROS 2 包 |
| `rl-utils` | 内部查询：平台 / 工具链 / Base 信息 |

**内部辅助，通常由上层命令调用**：`sylixos-linux-tools`（仅被 `rl-build config` 调用）、`realevo-project-tools`、`realevo-symbol-tools`、`realevo-package-tools`、`realevo-complete-tools`（补全脚本，非安装器）、`armory`（二进制）。

各命令通用子命令说明见下文；完整参数以 `<命令> --help` 为准。

## 2. 执行顺序与依赖

不可颠倒：

1. 工作空间初始化 → 工程创建（工程需要工作空间的 `platforms`）。
2. 工程创建 → 构建（`rl-build` 读 `.rlproject/.rlconfig`）。
3. `rl-build install` → `rl-upload project`（部署读 `install-<os>/<P>`）。
4. `rl-device add` → `rl-upload` / `rl-package install2device` / `project-run-*`（都查 `devicelist.json`）。
5. `.realevo/arch/<P>/rootfs` 存在 → `rl-package install`（SylixOS 专用）。
6. `rl-tools install --soft=cpython-crossenv` → 构建 cython 工程。
7. ROS 2 三套环境装好 → `rl-project create --type=ros2` / `rl-ros create` / `rl-colcon build`。
8. 换 Base 必须重新初始化工作空间。

调用链：`rl-build` → `sylixos-linux-tools`（config 阶段唯一编译链入口）、`realevo-symbol-tools`（symbolcheck）、`rl-package install`（工程依赖）、`rl-tools install`（依赖命令）；`rl-device install` → `rl-upload soft`；`project-run-test` → `rl-upload project`；`rl-package`/`rl-tools` → `armory`。

## 3. `rl-workspace`

子命令 `init` `createbase` `show` `clean`。**`init` 在目标目录执行。**

```
rl-workspace init --base=<路径> --platform=<P> --createbase=<true|false> --build=<true|false>
                  --debug_level=<debug|release> --version=<base版本> --product=<产品系列>
                  --os=<sylixos|linux|openeuler|all>
                  --linux_platform=<P> --linux_toolchain=<.cmake|目录> --linux_rootfs=<目录|tar.gz|/>
                  --openeuler_platform=<P> --openeuler_toolchain=<...> --openeuler_rootfs=<...>
                  --upload-ignore=<正则> [--quiet]
```

三条 SylixOS 路径（选一）：

| 方式 | 命令 |
| --- | --- |
| 产品系列（平台由产品决定） | `rl-workspace init --product=<系列>` |
| Base 版本（从 `pkg/base/` 解压，可编译） | `rl-workspace init --version=<base> --platform=<P> --createbase=true [--build=true]` |
| 已有 Base | `rl-workspace init --base=<路径> --platform=<P>` |

- SylixOS 非产品模式需要 `--platform`，多平台用 `:` 分隔；产品模式从 SDK 映射取得平台。Linux/OpenEuler 的工具链参数必填，优先传已有 `.cmake`。
- `init` 完成参数/产品解析后、平台初始化前执行 clean，会删除 `.realevo/{arch,linux,openeuler,package_list}` 后重建。
- `--quiet` 消除"目录型工具链多前缀"选择；不能用环境变量注入。
- 成功产物：`.realevo/config.json`、`.realevo/devicelist.json`、`.realevo/arch/<P>/rootfs`（或 `linux`/`openeuler`）。

```
rl-workspace createbase --base=<路径> --platform=<P> [--build=<true|false>] [--debug_level=<debug|release>]
rl-workspace show
rl-workspace clean
```

- `createbase` 的 `--base` 省略时默认 `./.realevo/base`；目录非空报错。会改写 Base 的 `config.mk`，并写 `<base>/.rlproject/.rlconfig`。
- `show` 打印 `.realevo/config.json`。`clean` 删除 `.realevo/{arch,linux,openeuler,package_list}`，保留 `base`、`config.json`、`devicelist.json`、`depend_armory.json`。
- `--version=<base>` 对应 `pkg/base/<base>.tar.gz`；现有 `default`、`default_compiled`、`lts_3.6.5`、`lts_3.6.5_compiled`、`ecs_3.6.5`、`ecs_3.6.5_compiled`、`lts_com_3.9.0` 及各产品 `*_base-devel`。

## 4. `rl-project`

子命令 `create` `update` `reconfig` `show`。**必须在已初始化的工作空间内执行。**

```
rl-project create --name=<工程名> [--type=<类型>] [--template=<模板>|--source=<路径>]
                  [--branch=<git分支>] [--debug-level=<debug|release>]
                  [--make-tool=<make|ninja>] [--version=<版本>] [--upload-ignore=<正则>] [--platform=<P>] [--quiet]
```

| 参数 | 说明 |
| --- | --- |
| `--name=` | 必填；≤60 字符；字符集 `a-zA-Z0-9_!@#$%^&~=+-` |
| `--type=` | `cmake\|automake\|realevo\|meson\|ros2\|python\|cython\|go\|javascript\|realevo_bsp\|cmake_bsp` |
| `--template=` | 见下表；与 `--source` 二选一 |
| `--source=` | 本地目录、`zip/tar.gz/tgz/tar.bz2/tar.xz/tar.zst/tar`、git 仓库；**提供后被强制为 `app` 模板** |
| `--debug-level=` | 默认 `release` |
| `--make-tool=` | 默认 `make` |
| `--version=` | 默认 `0.0.1` |
| `--upload-ignore=` | 默认 `/include/:/cmake/` |
| `--platform=` | ros2/BSP 等单平台工程显式选择，必须匹配工作空间 |
| `--quiet` | 仅消除"多个主 CMakeLists/configure"的选择交互；**不影响平台菜单** |

`--type` / `--template` 可用矩阵（以 `config/template/` 实际目录为准）：

| `--type` | 可用 `--template` |
| --- | --- |
| `cmake` | `app` `lib` `ko` `so` `python_native_lib` `uorb_pubsub` `vsoa_pubsub` `fast_dds_pubsub`（**无 `common`**） |
| `meson` | `app` |
| `realevo` | `app` `ko` `shared_lib`（动态库是 `shared_lib`，不是 `lib`） |
| `python` | `common` `native-lib` |
| `cython` `go` `javascript` `ros2` | `common` |
| `realevo_bsp` `cmake_bsp` | `<arch>-none`（如 `arm64-none`） |

产物：`<project>/` 与 `.rlproject/{.rlconfig,params.cfg,README.md}`。Go 工程落在 `<ws>/go/src/<project>`。

```
rl-project update [--debug-level=] [--make-tool=] [--version=] [--upload-ignore=]
                  [--cmakelists] [--configure] [--project=<工程名>] [--platform]
rl-project reconfig
rl-project show [--project=<工程名>]
```

- `update` 原地改写 `.rlproject/.rlconfig`，不移动源码。
- `update`/`reconfig`/`show` **不接受 `--quiet`**。
- `update --platform` 是无值参数，进入平台选择菜单：**仅 1 个平台时自动选中；≥2 个平台且非交互时无限自旋**。安全替代流程见 [constraints.md §2](constraints.md#2-避开不可靠的非交互接口)。

## 5. `rl-build`

```
rl-build (all|clean|config|build|install|uninstall|symbolcheck|package) [options]
  --project=<工程名>        # 工程目录内可省
  --platforms=<P>          # 限定目标平台
  --parallel=<N>           # 默认 1
  --installdir=<路径>       # 默认 /
  --strip=<true|false>     # 默认 true
  --skiperror=<true|false> # 默认 false
  --os=<sylixos|linux|openeuler>  # 默认 sylixos
  --clean_config=<true|false>     # 默认 true
  --incremental=<true|false>      # 默认 false
```

| 子命令 | 行为 / 产物 |
| --- | --- |
| `clean` | 删 `build-<os>`、`install-<os>`（realevo 类型额外删 `build/`）；`--incremental=true` 跳过 |
| `config` | 逐平台调 `sylixos-linux-tools` 完成配置；python/cython/go/js **跳过** → 生成 `build-<os>/<P>/` 与 `install-<os>/<P>/` |
| `build` | 逐平台 `make`/`ninja`；realevo 用 `make`；cython 产出 whl；go 用 `go build` |
| `install` | 先 `make install`（cmake + strip 走 `install/strip`），再合并进 `.realevo/.../<P>/rootfs` |
| `uninstall` | 按清单从 rootfs 删文件并删 `install-<os>/<P>` |
| `all` | 依次 **clean → config → build → install** |
| `symbolcheck` | 转 `realevo-symbol-tools`；**仅打印，不改变退出码** |
| `package` | **空实现**，仅打印提示；打包用 `rl-package package` |

目录命名：

```
<project>/build-<os>/<PLATFORM>/              # cmake / automake / meson
<project>/build/<PLATFORM>/<Release|Debug>/   # realevo / realevo_bsp
<project>/install-<os>/<PLATFORM>/{apps,lib,usr,...}
<workspace>/.realevo/arch/<PLATFORM>/rootfs/                    # SylixOS 合并目标
<workspace>/.realevo/{linux,openeuler}/<PLATFORM>/rootfs/       # Linux / OpenEuler
```

- `install` 只合并固定目录：`apps boot etc lib qt root sbin usr bin home tmp var`。
- Linux/OpenEuler **native 时跳过 rootfs 合并**。
- 工具链文件：默认 `config/cmake/sylixos.toolchain.cmake`；内核模块用 `sylixos.ko.cmake`；`cmake_bsp` 用 `sylixos.bsp.cmake`。`.rlproject/params.cfg` 每行经 `envsubst` 追加到 CMake 命令后。

## 6. ROS 2：`rl-colcon` / `rl-ros`

```
rl-colcon (clean|build|list) [--merge-install] [--packages-select <P>] [--packages-skip <P>]
          [--parallel-workers <N>] [--test-result-base <PATH>] [--event-handlers <H>]
```

- `build` 会先清理 `build-sylixos`/`install-sylixos`/`log`，产物为 `build-sylixos/<P>`、`install-sylixos/<P>`。
- **`all` 不可用**（校验数组含它但未实现，报 `Unrecognized subcommand` 并退出 1）；`list` 可用。
- 需在工程根目录执行；依赖 `@sylixos-middleware/ros2_jazzy-devel`（由 `rl-build` 按 `config/project_depend.json` 自动安装）。

```
rl-ros create <package_name> --build-type <cmake|ament_cmake|ament_python>
              [--destination-directory <目录>] [--maintainer-name <名>] [--maintainer-email <邮箱>]
              [--license <许可>] [--description <描述>] [--dependencies <依赖...>]
              [--node-name <节点名>] [--library-name <库名>]
```

- 参数用**空格分隔**，不用 `=`；`--build-type` 必填；包名只允许小写字母/数字/下划线。
- 必须在 ROS 2 工程的 `src/` 目录下执行；默认节点名 `test_node`。

凭据接口的参数表仅用于理解原生语法，不授权把真实密码放入 argv；执行使用安全预置配置，见 [constraints.md §8](constraints.md#8-凭据权限与封装验收)。

## 7. `rl-device`

```
rl-device add    --name=<名> --ip=<地址> --platform=<P> [--os=<sylixos|linux|openeuler>]
                 [--telnet=23] [--ssh=22] [--ftp=21] [--gdb=1234]
                 [--user=root] [--password=root] [--hostname=<宿主设备名>]
rl-device delete --name=<名>
rl-device update --name=<名> [--ip=] [--platform=] [--telnet=] [--ssh=] [--ftp=] [--gdb=]
                 [--user=] [--password=] [--os=] [--hostname=]
rl-device list
rl-device upload --name=<名>
rl-device install --name=<名> --soft=<python|javascript>
```

- `add` 的 `--name`、`--ip`、`--platform` 必填；设备名唯一。登记不等于验证网络或凭据。
- 平台按 `--os` 校验：`linux`/`openeuler` 必须是 `ARM64|X86|X86_64|RISCV|LOONGARCH`；`sylixos` 必须是 63 项白名单。
- **`rl-device upload` 用系统 `ftp mput`，有交互确认风险且无忽略规则 → 优先用 `rl-upload`**。
- `rl-device install` 转调 `rl-upload soft`；`--soft` 仅 `python`、`javascript`。
- 已知缺陷：`add` 写入键为 `host_name`，而 `list`/`upload` 读取 `hostName` → ECS 容器别名读不到。
- `--hostname` 用于 ECS 容器（容器视作设备，`ip` 形如 `<宿主机IP>:<容器ID>`，凭据留空）。

## 8. `rl-upload`

```
rl-upload workspace --device=<设备名> [--paths-select=] [--task-id=]
rl-upload project   --device=<设备名> [--project=<工程名>] [--packages-select=]
                    [--executable-file=] [--paths-select=] [--task-id=]
rl-upload file      --device=<设备名> [--localPath=] [--remotePath=]
rl-upload directory --device=<设备名> [--localDir=] [--remoteDir=]
rl-upload soft      --device=<设备名> [--name=<python|javascript>] [--version=]
```

- `--device` 各子命令必填；`project` 在工程目录外需 `--project=`。
- `project` 部署 `install-<os>/<P>`；`workspace` 部署 `.realevo/.../<P>/rootfs`；目录固定 `apps boot etc lib qt root sbin usr bin home tmp var`。
- 路径映射：SylixOS → `/<dir>`；Linux/OpenEuler → root 用户 `/root/<dir>`，非 root `/home/<user>/<dir>`。
- 协议：优先 FTP；设备为 linux/openeuler 或 FTP 失败时走 SFTP；建软链用 Telnet。`file`/`directory` 固定走 FTP。
- 忽略规则：`project` 读 `.rlconfig` 的 `upload.ignore`；`workspace` 读 `.realevo/config.json` 的 `upload.ignore`。
- `soft` 的 `--name=python|javascript` **拒绝 Linux/OpenEuler**。
- ROS 2 工程文件部署到设备 `/apps/ros2`（特例）。

## 9. 运行：`project-run-test` / `project-run-tools`

命令集只提供**远程启动**语义（Telnet/SSH），不是本地调试器；本地调试由 VSCode 插件 + 设备 GDB 端口（默认 1234）完成。

| 命令 | 参数 | 行为 |
| --- | --- | --- |
| `project-run-test` | `--device= --project= --path=`（均必填） | 上传 + **前台**运行；`--path` 形如 `<...>/<project>/install-sylixos/<arch>/<remote path>`，`arch` 必须与设备 `platform` 一致；**仅 SylixOS** |
| `project-run-tools` | `--device_name=<名>`，或位置参数 `<host> <port> <program_wd> <username> <password> <json_path> <args...>` | **后台**启动；PID 写入 `json_path` 的 `configurations[0].customConfigurationVariables.DebugPID`（**不会自动清理**） |

高风险：`project-run-tools` 的 SSH 路径发送 `"<cmd> &"` 不带 `exit`，可能不返回；Telnet 会话轮询至远程程序结束。二者都必须 `timeout` 兜底。

`rl-project run` / `debug` 的包装在源码中被整段注释，命令集内无有效 run/debug 链路。

## 10. `rl-package`

```
rl-package set --username= --password= --repository=<url|default> --organization=
rl-package show
rl-package search --package=<@命名空间/包名> [--page-num=<n>]
rl-package install --package=<spec|本地路径> [--version=] [--dependent=<yes|no>]
rl-package uninstall --package=<spec>
rl-package install2device --package=<spec> --device=<设备名> [--version=] [--dependent=<yes|no>]
rl-package package --project=<工程名> [--type=<develop|source|target>] [--upload=<yes|no>]
                   [--path=<目录>] [--access=<private|public>]
```

- **`install` 要求 `.realevo/arch` 存在**，只适用于 SylixOS 工作空间；安装目标 `.realevo/arch/<P>/rootfs`，并记录到 `.realevo/package_list/`。
- `install2device` 先合并到 `.realevo/package_tmp/target_merge_dir`，再调 `rl-upload directory`。
- `package` 白名单取 `.rlconfig.package.allowlist`（默认 `/bin /lib /usr /apps`），README 取 `.rlproject/README.md`，默认输出 `rlpackage/`；`--upload=yes` 时调 `armory publish`。
- **`uninstall` 无条件交互确认且无 `-y`**：非交互下静默取消并返回 0 → 用 `printf 'y\n' | ...` 并解析 stdout。
- `--dependent` 默认 `yes`；不指定 `--upload=yes` 时不推送到 Armory。

## 11. `rl-tools`

```
rl-tools show [--license] [--product=<名>]
rl-tools --version
rl-tools update [--plugin=<插件>] [--version=<版本>] [--path=<路径>] [--revert=<true|false>]
rl-tools update_lcsproxy --type=<usbkey|server|http> [--server_ip=] [--server_port=] [--http_address=]
rl-tools install --soft=<cpython-crossenv|go|colcon|ecsc|fastddsgen|uorb>
rl-tools getarmory --package=<spec> [--path=<目录>] [--version=]
rl-tools modifycmake | restorecmake | modifygcc | restoregcc
rl-tools exportcmake --workspace=<路径> [--project=<名>]
rl-tools checksymbolic [--path=<目录>] [--project=<名>]
rl-tools json2struct --input=<文件> --output=<文件> [--type=] [--name=]
```

- `--plugin`：缺省=升级命令集、`armory`、`@acu-xxx/acu-sdk`、`@realevo/realevo-stream-sdk`（预编译 Base）。`--path` 指向本地包或**含 `stream_config.json` 的离线 SDK 目录**。
- `show --license` 输出 `Status`（须为 `VALID`）与 `RemainingDays`。
- **`install`/`update` 可能部分失败仍返回 0** → 解析输出的 `[ERROR]` 与 `Found N installation failures`。
- **`update_lcsproxy` 必须显式传 `--type=`**，否则进入交互菜单。
- **`exportcmake` 没有 `--platform` 参数，EOF 退出 select 后可能在未选平台状态继续执行，避免使用**；查询配置用工作空间配置与构建日志，修改工程平台见 [constraints.md §2](constraints.md#2-避开不可靠的非交互接口)。
- `update` 的 `--revert` 默认 `true`，回退到不高于当前版本时会询问确认。
- `modifycmake`/`modifygcc` **会替换系统 CMake 模块与 `gcc/g++/ld`**，用对应 `restore*` 还原。
- 内部大量使用 `sudo`；环境准备优先用本 Skill 的 `cli.py`。

## 12. `rl-ecs` / `rl-ecsm`

```
rl-ecs create --platform=<标签...> [--bundlepath=<目录>]
rl-ecs config [--platform=] [--components=<a:b>] [--parameter=<参数>] [--bundlepath=]
rl-ecs package --name=<名> [--tag=] [--bundlepath=] [--targetpath=] [--targetname=] [--platform=]
rl-ecs upload --device= [--tarpath=] --targetpath=<远端目录>
rl-ecs load --device= --tarpath= --targetpath= --containerid=
rl-ecs save --device= --bundlepath= --tarpath= --name= --tag= [--use_scp=] [--task-id=]
rl-ecs systemcallgen --path=<符号文件> --name=<名> [--startnumber=<起始号>]

rl-ecsm set|update --id=<id> [--url=] [--username=] [--password=] [--active=<true|false>]
rl-ecsm list | delete --id=<id> | show [--id=] [--pagenum=]
rl-ecsm pull [--id=] --imageid=<镜像ID> --path=<本地目录> [--tarname=]
rl-ecsm push [--id=] --path=<镜像文件>
```

- `rl-ecs --platform` 用**包架构标签**：`arm|arm64|x86|x86-64|ppc|sparc|mips32|mips64|riscv|loongarch|csky|noarch`，与工作空间 Platform 名不同。
- 依赖 `rl-tools install --soft=ecsc`；该工具需要 Node.js 与 npm。
- `systemcallgen`：系统调用号不可重复，自定义**建议从 1200 开始**（内核默认约 600 个，xsiipc 占 20 个）。
- ECSM 不指定 `--id` 时操作**活跃镜像源**；`pull` 的 `--imageid` 来自 `rl-ecsm show`。
- 已知缺陷：`rl-ecs save` 的 FTP 通路必然失败；`rl-ecsm pull` 无总截止时间（需 `timeout`）；`rl-ecsm set/update --active` 不可用。

## 13. SylixOS Platform 白名单

共 **63 项**（`createbase` 报错时打印的完整清单）。实际可用集合取决于所选 Base 与已安装工具链。

- **ARM**：`ARM_926H` `ARM_926S` `ARM_920T` `ARM_A5` `ARM_A5_SOFT` `ARM_A7` `ARM_A7_SOFT` `ARM_A8` `ARM_A8_SOFT` `ARM_A9` `ARM_A9_SOFT` `ARM_A15` `ARM_A15_SOFT` `ARM_V7A` `ARM_V7A_SOFT`
- **ARM64**：`ARM64_A53` `ARM64_A55` `ARM64_A57` `ARM64_A72` `ARM64_GENERIC`
- **MIPS**：`MIPS32` `MIPS32_SOFT` `MIPS32_R2` `MIPS32_R2_SOFT` `MIPS64_R2` `MIPS64_R2_SOFT` `MIPS64_LS3A` `MIPS64_LS3A_SOFT`
- **x86**：`x86_PENTIUM` `x86_PENTIUM_SOFT` `X86_64`
- **PPC**：`PPC_750` `PPC_750_SOFT` `PPC_464FP` `PPC_464FP_SOFT` `PPC_E500V1` `PPC_E500V1_SOFT` `PPC_E500V2` `PPC_E500V2_SOFT` `PPC_E500MC` `PPC_E500MC_SOFT` `PPC_E5500` `PPC_E5500_SOFT` `PPC_E6500` `PPC_E6500_SOFT`
- **SPARC**：`SPARC_LEON3` `SPARC_LEON3_SOFT` `SPARC_V8` `SPARC_V8_SOFT`
- **RISCV**：`RISCV_GC32` `RISCV_GC32_SOFT` `RISCV_GC64` `RISCV_GC64_SOFT`
- **LOONGARCH**：`LOONGARCH64` `LOONGARCH64_SOFT`
- **CSKY**：`CSKY_CK807` `CSKY_CK807_SOFT` `CSKY_CK810` `CSKY_CK810_SOFT` `CSKY_CK860` `CSKY_CK860_SOFT`
- **SW6B**：`SW6B` `SW6B_SOFT`

平台 → 工具链前缀/CPU/FPU 的权威映射在 `config/platforms.mk` 与所选 Base 的 `platforms.mk`；可用 `rl-utils get-toolchain <P> <n>` 查询。产品系列（`ARC1000` `AEC1000` `ARC2000` `AEC2000` `AMC2000` `ARC3000` `AEC3000` `AMC3000`）只能用于 `--product=`。

## 14. 配置文件与目录

```
<workspace>/
├── .realevo/
│   ├── config.json            # 工作空间主配置
│   ├── devicelist.json        # 设备清单
│   ├── depend_armory.json     # 工作空间依赖包
│   ├── base/                  # SylixOS Base 工程（clean 保留）
│   ├── arch/<PLATFORM>/rootfs/          # SylixOS sysroot / 部署源
│   ├── linux|openeuler/<PLATFORM>/rootfs/
│   └── package_list/          # rl-package 安装记录
├── <project>/.rlproject/{.rlconfig, params.cfg, README.md}
├── go/src/<project>/          # Go 工程特殊位置
└── rlpackage/<project>/       # rl-package package 默认输出
```

`.realevo/config.json` 关键字段：`base`、`base_type`、`mularch`（`yes`/`no`）、`debug_level`、`platforms`、`linux_toolchain`、`linux_rootfs`、`linux_native`、`linux_platforms`、`openeuler_*`、`upload.ignore`、`sylixos_min_kernel_version`、`RealEvo_Version`。

`.rlproject/.rlconfig` 关键字段：`debug_level`、`build_type`、`template`、`make_tool`、`version`、`cmakelists_dir`、`configure_dir`、`platform`、`upload.ignore`（部署黑名单）、`package.allowlist`（打包白名单）、`dependencies`、`devel_dependencies`。

用户级：`~/.realevo-stream/settings.json`（ECSM 等）、`~/.realevo-stream/*.db`（任务/上传记录）、`~/.armory/*.json`（Armory 账号，**密码明文**）、`/etc/lcsproxy/lcsproxy.conf`（License）。

已知缺陷：`rl-workspace show` 与 `rl-package` 读 `mini_kernel_version`，而写入键是 `sylixos_min_kernel_version` → 该字段读不到。

## 15. 环境变量

| 变量 | 作用 |
| --- | --- |
| `REALEVO_COMPILER_PATH` | 由 `Install.sh` 写入 `/etc/profile`：`bin` + 全部 `compiler/*-sylixos-toolchain/bin` |
| `REALEVO_HOME` | 本 Skill `cli.py` 读取的命令集根目录（默认 `/opt/acoinfo/realevo-stream`） |
| `REALEVO_SUDO_PASSWORD` | 本 Skill `cli.py` 用于 sudo 免交互预认证 |
| `REALEVO_NATIVE` | `rl-build` 传给 `sylixos-linux-tools` 的 native 布尔 |

`--quiet` 分工：`rl-workspace --quiet` 消除工具链多前缀选择；`rl-project create --quiet` 只消除多主配置文件选择（不影响平台菜单）。**不存在**通用的 `CI` / `NONINTERACTIVE` 非交互开关。
